"""Minimal audit logging helpers for important internal MCP operations."""

from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator

from .logging import get_logger, log_event

AUDIT_LOGGER = get_logger("saudi_open_data_mcp.audit")
_AUDIT_CONTEXT: ContextVar["AuditContext | None"] = ContextVar(
    "saudi_open_data_mcp_audit_context",
    default=None,
)


@dataclass(frozen=True)
class AuditContext:
    """Best-effort request-scoped audit context."""

    transport: str | None = None
    actor_type: str | None = None
    actor_token_fingerprint: str | None = None
    actor_capabilities: tuple[str, ...] = ()
    request_id: str | None = None
    rpc_request_id: str | int | None = None
    path: str | None = None

    def as_log_fields(self) -> dict[str, Any]:
        """Return audit-safe structured fields for the current context."""

        fields: dict[str, Any] = {}
        if self.transport is not None:
            fields["transport"] = self.transport
        if self.actor_type is not None:
            fields["actor_type"] = self.actor_type
        if self.actor_token_fingerprint is not None:
            fields["actor_token_fingerprint"] = self.actor_token_fingerprint
        if self.actor_capabilities:
            fields["actor_capabilities"] = self.actor_capabilities
        if self.request_id is not None:
            fields["request_id"] = self.request_id
        if self.rpc_request_id is not None:
            fields["rpc_request_id"] = self.rpc_request_id
        if self.path is not None:
            fields["path"] = self.path
        return fields


def build_token_fingerprint(token: str) -> str:
    """Return a short stable fingerprint for audit logs without exposing the token."""

    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


@contextmanager
def audit_context(
    *,
    transport: str | None = None,
    actor_type: str | None = None,
    actor_token_fingerprint: str | None = None,
    actor_capabilities: tuple[str, ...] = (),
    request_id: str | None = None,
    rpc_request_id: str | int | None = None,
    path: str | None = None,
) -> Iterator[None]:
    """Bind request-scoped audit context for nested operation logs."""

    token: Token[AuditContext | None] = _AUDIT_CONTEXT.set(
        AuditContext(
            transport=transport,
            actor_type=actor_type,
            actor_token_fingerprint=actor_token_fingerprint,
            actor_capabilities=actor_capabilities,
            request_id=request_id,
            rpc_request_id=rpc_request_id,
            path=path,
        )
    )
    try:
        yield
    finally:
        _AUDIT_CONTEXT.reset(token)


def log_audit_event(
    operation: str,
    *,
    result_status: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit one structured audit event enriched with current request context."""

    payload = {
        "operation": operation,
        "result_status": result_status,
    }
    context = _AUDIT_CONTEXT.get()
    if context is not None:
        payload.update(context.as_log_fields())
    payload.update(
        {
            key: value
            for key, value in fields.items()
            if value is not None
        }
    )
    log_event(
        AUDIT_LOGGER,
        level,
        f"audit.{operation}",
        **payload,
    )
