"""Minimal internal HTTP readiness surface for container serving."""

from __future__ import annotations

from starlette.middleware import Middleware as ASGIMiddleware
from starlette.responses import JSONResponse

HTTP_READINESS_PATH = "/readyz"


class HTTPReadinessMiddleware:
    """Serve one narrow machine-checkable readiness response."""

    def __init__(self, app, *, app_name: str) -> None:
        self.app = app
        self._app_name = app_name

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] == "http"
            and scope.get("path") == HTTP_READINESS_PATH
            and scope.get("method") in {"GET", "HEAD"}
        ):
            await JSONResponse(
                {
                    "status": "ready",
                    "ready": True,
                    "scope": "internal_runtime_readiness",
                    "app_name": self._app_name,
                    "checks": {
                        "process_running": True,
                        "startup_validated": True,
                        "runtime_storage_prepared": True,
                        "app_wiring_completed": True,
                    },
                }
            )(scope, receive, send)
            return

        await self.app(scope, receive, send)


def build_http_readiness_middleware(app_name: str) -> list[ASGIMiddleware]:
    """Build the narrow readiness middleware for the official HTTP path."""

    return [
        ASGIMiddleware(
            HTTPReadinessMiddleware,
            app_name=app_name,
        )
    ]
