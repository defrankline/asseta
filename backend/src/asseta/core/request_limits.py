"""Whole-request body size limit (security finding F-6).

Handlers cap what they read (images at `max_image_bytes`, sync chunks at their declared size), but multipart bodies
are spooled and JSON bodies parsed before those caps apply. This pure ASGI middleware refuses a body above
`max_request_bytes` first: a declared Content-Length over the limit is answered without reading the body, and a
body without one (chunked) is counted as it streams and cut off at the limit. The reverse proxy enforces the same
bound (`client_max_body_size`, web/nginx.conf); this guard also covers clients that reach the API directly.
"""

import contextlib

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from asseta.core.errors import PayloadTooLarge, error_response


class _BodyTooLarge(Exception):
    """Raised from `receive` to stop the app reading; the middleware answers 413 instead."""


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None  # malformed: the server rejects it; the streaming count below still applies
    return None


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return
        declared = _declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            await self._refuse(scope, receive, send)
            return

        received = 0
        exceeded = started = False

        async def bounded_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if exceeded:
                return  # whatever the app made of the aborted read (e.g. a 400 parse error) is replaced by 413
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        with contextlib.suppress(_BodyTooLarge):  # propagated when the app did not turn it into its own error
            await self.app(scope, bounded_receive, guarded_send)
        if exceeded and not started:
            await self._refuse(scope, receive, send)

    async def _refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        exc = PayloadTooLarge(f"Request body exceeds the {self.max_bytes} byte limit")
        response = error_response(exc.status_code, exc.code, exc.message)
        response.headers["Connection"] = "close"  # the unread remainder of the body is not drained
        await response(scope, receive, send)
