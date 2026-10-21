"""Correlation-ID propagation (request header -> context var -> logs, audit, outbox, responses)."""

import uuid
from contextvars import ContextVar

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "x-correlation-id"
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    value = _correlation_id.get()
    return value or str(uuid.uuid4())


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


def _valid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


class CorrelationIdMiddleware:
    """Pure ASGI middleware so the context var is visible to handlers and exception handlers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(HEADER.encode(), b"").decode()
        cid = incoming if incoming and _valid(incoming) else str(uuid.uuid4())
        token = _correlation_id.set(cid)
        structlog.contextvars.bind_contextvars(correlation_id=cid)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((HEADER.encode(), cid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            structlog.contextvars.unbind_contextvars("correlation_id")
            _correlation_id.reset(token)
