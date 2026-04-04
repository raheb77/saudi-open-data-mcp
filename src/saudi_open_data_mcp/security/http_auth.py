"""Minimal internal bearer-token auth for the HTTP serving path."""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from secrets import compare_digest
from typing import Any

from pydantic import SecretStr
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from saudi_open_data_mcp.observability import get_logger, get_metrics, log_event

LOGGER = get_logger(__name__)


class HTTPAuthCapability(StrEnum):
    """Minimal internal HTTP capability model."""

    READ = "read"
    REFRESH = "refresh"
    MATERIALIZE = "materialize"


ALL_HTTP_AUTH_CAPABILITIES = frozenset(HTTPAuthCapability)
READ_RESOURCE_URIS = frozenset(
    {
        "resource://catalog",
        "resource://observability",
    }
)
READ_TOOL_NAMES = frozenset(
    {
        "dataset_metadata",
        "dataset_health",
        "download_dataset",
        "query_dataset",
        "search_datasets",
    }
)
REFRESH_TOOL_NAMES = frozenset({"preview_dataset"})
MATERIALIZE_TOOL_NAMES = frozenset({"materialize_hot_set"})
ALL_CAPABILITY_MAPPED_TOOL_NAMES = (
    READ_TOOL_NAMES | REFRESH_TOOL_NAMES | MATERIALIZE_TOOL_NAMES
)
READ_MCP_METHODS = frozenset(
    {
        "resources/list",
        "resources/read",
        "tools/list",
        "prompts/list",
        "prompts/get",
    }
)
CapabilityCollection = (
    frozenset[HTTPAuthCapability]
    | set[HTTPAuthCapability]
    | tuple[HTTPAuthCapability, ...]
)


class HTTPBearerAuthMiddleware:
    """Reject HTTP requests without the configured bearer token and capability."""

    def __init__(
        self,
        app,
        *,
        bearer_token: SecretStr | str,
        capabilities: CapabilityCollection,
    ) -> None:
        self.app = app
        self._bearer_token = require_http_bearer_token(bearer_token)
        self._capabilities = require_http_auth_capabilities(capabilities)

    def __repr__(self) -> str:
        """Return a masked middleware repr without exposing the bearer token."""

        return (
            f"{type(self).__name__}("
            f"bearer_token={self._bearer_token!r}, "
            f"capabilities={sorted(capability.value for capability in self._capabilities)!r}"
            f")"
        )

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        metrics = get_metrics()
        metrics.increment("http.auth.requests")
        request = Request(scope)
        presented_token = _extract_bearer_token(
            request.headers.get("authorization"),
        )

        if presented_token is None:
            metrics.increment("http.auth.rejected")
            metrics.increment("http.auth.rejected.missing")
            log_event(
                LOGGER,
                logging.WARNING,
                "http.auth.rejected",
                path=scope.get("path"),
                reason="missing_bearer_token",
            )
            await _unauthorized_response("missing bearer token")(scope, receive, send)
            return

        if not compare_digest(
            presented_token,
            self._bearer_token.get_secret_value(),
        ):
            metrics.increment("http.auth.rejected")
            metrics.increment("http.auth.rejected.invalid")
            log_event(
                LOGGER,
                logging.WARNING,
                "http.auth.rejected",
                path=scope.get("path"),
                reason="invalid_bearer_token",
            )
            await _unauthorized_response("invalid bearer token")(scope, receive, send)
            return

        metrics.increment("http.auth.accepted")
        request_body, replay_receive = await _buffer_http_request_body(receive)
        authz_decision = _authorization_decision(scope, request_body)
        if (
            authz_decision.required_capability is not None
            and authz_decision.required_capability not in self._capabilities
        ):
            metrics.increment("http.authz.rejected")
            metrics.increment("http.authz.rejected.insufficient_capability")
            log_event(
                LOGGER,
                logging.WARNING,
                "http.authz.rejected",
                path=scope.get("path"),
                mcp_method=authz_decision.mcp_method,
                target=authz_decision.target,
                required_capability=authz_decision.required_capability.value,
                granted_capabilities=sorted(
                    capability.value for capability in self._capabilities
                ),
            )
            await _forbidden_response(
                f"insufficient capability: {authz_decision.required_capability.value}"
            )(scope, replay_receive, send)
            return
        if authz_decision.coverage_error is not None:
            log_event(
                LOGGER,
                logging.ERROR,
                "http.authz.coverage_missing",
                path=scope.get("path"),
                mcp_method=authz_decision.mcp_method,
                target=authz_decision.target,
                message=authz_decision.coverage_error,
            )
            await _internal_error_response(authz_decision.coverage_error)(
                scope,
                replay_receive,
                send,
            )
            return

        await self.app(scope, replay_receive, send)


def build_http_auth_middleware(
    bearer_token: SecretStr | str | None,
    capabilities: (
        frozenset[HTTPAuthCapability]
        | set[HTTPAuthCapability]
        | tuple[HTTPAuthCapability, ...]
        | None
    ) = None,
) -> list[ASGIMiddleware]:
    """Build the HTTP auth middleware list for the official serving path."""

    return [
        ASGIMiddleware(
            HTTPBearerAuthMiddleware,
            bearer_token=require_http_bearer_token(bearer_token),
            capabilities=require_http_auth_capabilities(
                capabilities
                if capabilities is not None
                else ALL_HTTP_AUTH_CAPABILITIES
            ),
        )
    ]


def require_http_bearer_token(
    bearer_token: SecretStr | str | None,
) -> SecretStr:
    """Return the configured HTTP bearer token or fail clearly."""

    secret = (
        bearer_token
        if isinstance(bearer_token, SecretStr)
        else SecretStr(bearer_token or "")
    )
    if not secret.get_secret_value():
        raise ValueError(
            "run-http requires HTTP_AUTH_TOKEN to be set for internal bearer auth"
        )

    return secret


def require_http_auth_capabilities(
    capabilities: (
        frozenset[HTTPAuthCapability | str]
        | set[HTTPAuthCapability | str]
        | tuple[HTTPAuthCapability | str, ...]
        | None
    ),
) -> frozenset[HTTPAuthCapability]:
    """Return the configured HTTP capabilities or fail clearly."""

    if capabilities is None:
        raise ValueError("run-http requires at least one HTTP auth capability")

    resolved = frozenset(HTTPAuthCapability(capability) for capability in capabilities)
    if not resolved:
        raise ValueError("run-http requires at least one HTTP auth capability")
    return resolved


def _extract_bearer_token(authorization_header: str | None) -> str | None:
    """Parse a standard Authorization bearer header."""

    if authorization_header is None:
        return None

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


class _AuthorizationDecision:
    """Capability requirement derived from the current MCP HTTP request."""

    def __init__(
        self,
        *,
        mcp_method: str | None,
        target: str | None,
        required_capability: HTTPAuthCapability | None,
        coverage_error: str | None = None,
    ) -> None:
        self.mcp_method = mcp_method
        self.target = target
        self.required_capability = required_capability
        self.coverage_error = coverage_error


async def _buffer_http_request_body(receive) -> tuple[bytes, Any]:
    """Buffer the current request body and return a replayable receive function."""

    messages: list[dict[str, Any]] = []
    body_parts: list[bytes] = []

    while True:
        message = await receive()
        messages.append(message)
        if message["type"] != "http.request":
            break

        body_parts.append(message.get("body", b""))
        if not message.get("more_body", False):
            break

    async def replay_receive() -> dict[str, Any]:
        if messages:
            return messages.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    return b"".join(body_parts), replay_receive


def _authorization_decision(
    scope,
    request_body: bytes,
) -> _AuthorizationDecision:
    """Return the required capability for the current MCP request, if any."""

    if scope.get("method") != "POST" or not request_body:
        return _AuthorizationDecision(
            mcp_method=None,
            target=None,
            required_capability=None,
        )

    try:
        message = json.loads(request_body)
    except json.JSONDecodeError:
        return _AuthorizationDecision(
            mcp_method=None,
            target=None,
            required_capability=None,
        )

    if not isinstance(message, dict):
        return _AuthorizationDecision(
            mcp_method=None,
            target=None,
            required_capability=None,
        )

    method = message.get("method")
    if not isinstance(method, str):
        return _AuthorizationDecision(
            mcp_method=None,
            target=None,
            required_capability=None,
        )

    if method in READ_MCP_METHODS:
        target = None
        params = message.get("params")
        if isinstance(params, dict):
            uri = params.get("uri")
            if isinstance(uri, str):
                target = uri
        if method == "resources/read" and isinstance(target, str):
            if target not in READ_RESOURCE_URIS:
                return _AuthorizationDecision(
                    mcp_method=method,
                    target=target,
                    required_capability=None,
                    coverage_error=f"authorization coverage missing for resource: {target}",
                )
        return _AuthorizationDecision(
            mcp_method=method,
            target=target,
            required_capability=HTTPAuthCapability.READ,
        )

    if method != "tools/call":
        return _AuthorizationDecision(
            mcp_method=method,
            target=None,
            required_capability=None,
        )

    params = message.get("params")
    if not isinstance(params, dict):
        return _AuthorizationDecision(
            mcp_method=method,
            target=None,
            required_capability=None,
        )

    tool_name = params.get("name")
    if not isinstance(tool_name, str):
        return _AuthorizationDecision(
            mcp_method=method,
            target=None,
            required_capability=None,
        )

    return _AuthorizationDecision(
        mcp_method=method,
        target=tool_name,
        required_capability=_required_capability_for_tool_name(tool_name),
        coverage_error=(
            None
            if tool_name in ALL_CAPABILITY_MAPPED_TOOL_NAMES
            else f"authorization coverage missing for tool: {tool_name}"
        ),
    )


def _required_capability_for_tool_name(
    tool_name: str,
) -> HTTPAuthCapability | None:
    """Return the required capability for a known tool name."""

    if tool_name in READ_TOOL_NAMES:
        return HTTPAuthCapability.READ
    if tool_name in REFRESH_TOOL_NAMES:
        return HTTPAuthCapability.REFRESH
    if tool_name in MATERIALIZE_TOOL_NAMES:
        return HTTPAuthCapability.MATERIALIZE
    return None


def _unauthorized_response(message: str) -> JSONResponse:
    """Return the standard unauthorized response payload."""

    return JSONResponse(
        {"error": message},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden_response(message: str) -> JSONResponse:
    """Return the standard forbidden response payload."""

    return JSONResponse(
        {"error": message},
        status_code=403,
    )


def _internal_error_response(message: str) -> JSONResponse:
    """Return the standard internal coverage-failure response payload."""

    return JSONResponse(
        {"error": message},
        status_code=500,
    )
