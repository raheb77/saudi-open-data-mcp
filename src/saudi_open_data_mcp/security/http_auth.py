"""Minimal internal bearer-token auth for the HTTP serving path."""

from __future__ import annotations

import logging
from secrets import compare_digest

from pydantic import SecretStr
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from saudi_open_data_mcp.observability import get_logger, get_metrics, log_event

LOGGER = get_logger(__name__)


class HTTPBearerAuthMiddleware:
    """Reject HTTP requests that do not present the configured bearer token."""

    def __init__(self, app, *, bearer_token: SecretStr | str) -> None:
        self.app = app
        self._bearer_token = require_http_bearer_token(bearer_token)

    def __repr__(self) -> str:
        """Return a masked middleware repr without exposing the bearer token."""

        return f"{type(self).__name__}(bearer_token={self._bearer_token!r})"

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
        await self.app(scope, receive, send)


def build_http_auth_middleware(
    bearer_token: SecretStr | str | None,
) -> list[ASGIMiddleware]:
    """Build the HTTP auth middleware list for the official serving path."""

    return [
        ASGIMiddleware(
            HTTPBearerAuthMiddleware,
            bearer_token=require_http_bearer_token(bearer_token),
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


def _extract_bearer_token(authorization_header: str | None) -> str | None:
    """Parse a standard Authorization bearer header."""

    if authorization_header is None:
        return None

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _unauthorized_response(message: str) -> JSONResponse:
    """Return the standard unauthorized response payload."""

    return JSONResponse(
        {"error": message},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )
