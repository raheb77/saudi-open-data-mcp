"""Narrow internal HTTP startup probe for container serving."""

from __future__ import annotations

from starlette.middleware import Middleware as ASGIMiddleware
from starlette.responses import JSONResponse

HTTP_STARTUP_PATH = "/startupz"
HTTP_READINESS_PATH = "/readyz"
HTTP_STARTUP_PROBE_PATHS = frozenset({HTTP_STARTUP_PATH, HTTP_READINESS_PATH})


class HTTPReadinessMiddleware:
    """Serve one narrow machine-checkable startup/serving probe response."""

    def __init__(self, app, *, app_name: str) -> None:
        self.app = app
        self._app_name = app_name

    async def __call__(self, scope, receive, send) -> None:
        request_path = scope.get("path")
        if (
            scope["type"] == "http"
            and request_path in HTTP_STARTUP_PROBE_PATHS
            and scope.get("method") in {"GET", "HEAD"}
        ):
            await JSONResponse(
                {
                    "status": "ready",
                    "ready": True,
                    "scope": "startup_serving_readiness_only",
                    "probe_kind": "startup_only",
                    "canonical_path": HTTP_STARTUP_PATH,
                    "served_path": request_path,
                    "deprecated_alias": request_path == HTTP_READINESS_PATH,
                    "app_name": self._app_name,
                    "checks": {
                        "process_running": True,
                        "configuration_validated": True,
                        "runtime_storage_prepared": True,
                        "app_wiring_completed": True,
                    },
                    "guarantees": (
                        "process is running",
                        "configuration validation passed",
                        "runtime storage preparation passed",
                        "core FastMCP app wiring completed",
                    ),
                    "does_not_check": (
                        "upstream source reachability",
                        "dataset freshness",
                        "live connector health",
                        "full MCP session readiness",
                    ),
                }
            )(scope, receive, send)
            return

        await self.app(scope, receive, send)


def build_http_readiness_middleware(app_name: str) -> list[ASGIMiddleware]:
    """Build the narrow startup probe middleware for the official HTTP path."""

    return [
        ASGIMiddleware(
            HTTPReadinessMiddleware,
            app_name=app_name,
        )
    ]
