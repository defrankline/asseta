"""Security findings F-6 (request size) and F-7 (statement_timeout).

F-6: the API refuses bodies above `max_request_bytes` with 413 PAYLOAD_TOO_LARGE in the standard envelope, both for
a declared Content-Length (not read at all) and for a chunked body (cut off while streaming); images up to
`max_image_bytes` and sync chunks still go through. F-7: the app engine carries a statement_timeout, and a cancelled
statement is a retryable 503 QUERY_TIMEOUT, not a 500. Rate limiting (F-5) lives in web/nginx.conf and is verified
live (docs/security.md).
"""

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from asseta.core.config import get_settings
from asseta.core.correlation import CorrelationIdMiddleware
from asseta.core.db import get_engine, get_session
from asseta.core.errors import install_error_handlers
from asseta.core.request_limits import RequestSizeLimitMiddleware
from tests.support.api import Api
from tests.support.jobs import setup_job

LIMIT = 1000


class _Body(BaseModel):
    note: str


def _mini_app() -> FastAPI:
    """A tiny app with the production middleware and error handlers, and a small limit."""
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=LIMIT)
    app.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(app)

    @app.post("/raw")
    async def raw(request: Request) -> dict[str, int]:
        return {"received": len(await request.body())}

    @app.post("/json")
    def parsed(body: _Body) -> dict[str, int]:
        return {"received": len(body.note)}

    @app.get("/slow")
    def slow(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
        session.execute(text("SET LOCAL statement_timeout = '50ms'"))
        session.execute(text("SELECT pg_sleep(2)"))
        return {"status": "unreachable"}

    return app


def _chunks(total: int, size: int = 100) -> Iterator[bytes]:
    for _ in range(total // size):
        yield b"x" * size


def _is_too_large(r: Response) -> None:
    assert r.status_code == 413, r.text
    error = r.json()["error"]
    assert error["code"] == "PAYLOAD_TOO_LARGE" and error["details"] == []
    assert error["correlation_id"] == r.headers["x-correlation-id"]


def test_request_size_limit_by_declared_length_and_while_streaming() -> None:
    client = TestClient(_mini_app())
    assert client.post("/raw", content=b"x" * LIMIT).json() == {"received": LIMIT}  # at the limit: fine
    _is_too_large(client.post("/raw", content=b"x" * (LIMIT + 1)))  # declared Content-Length
    _is_too_large(client.post("/json", json={"note": "y" * LIMIT}))  # JSON is refused before it is parsed

    # Chunked transfer (no Content-Length): counted as it streams, cut off at the limit.
    chunked = client.post("/raw", content=_chunks(LIMIT * 5))
    assert "content-length" not in chunked.request.headers
    _is_too_large(chunked)
    _is_too_large(client.post("/json", content=_chunks(LIMIT * 5), headers={"content-type": "application/json"}))
    assert client.post("/raw", content=_chunks(LIMIT)).json() == {"received": LIMIT}


def test_api_refuses_oversized_bodies_but_accepts_full_size_images(api: Api) -> None:
    c = setup_job(api, "Size Co", "SIZE-1")
    limit = get_settings().max_request_bytes
    assert limit >= get_settings().max_image_bytes + 64 * 1024  # room for multipart framing
    headers = c.owner.headers(True, None)
    _is_too_large(api.client.post("/api/v1/tenant/customers", headers=headers, content=b"{" + b" " * limit))
    _is_too_large(
        api.client.post(
            "/api/v1/tenant/attachments",
            headers=headers,
            files={"file": ("big.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * limit, "image/jpeg")},
            data={"purpose": "METER_PHOTO"},
        )
    )
    # An image of exactly max_image_bytes (the handler's own cap) still uploads through the global limit.
    image = b"\xff\xd8\xff\xe0" + uuid.uuid4().bytes + b"\x00" * (get_settings().max_image_bytes - 20)
    r = api.client.post(
        "/api/v1/tenant/attachments",
        headers=headers,
        files={"file": ("full.jpg", image, "image/jpeg")},
        data={"purpose": "METER_PHOTO"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["size_bytes"] == get_settings().max_image_bytes


def test_app_engine_carries_statement_timeout() -> None:
    expected = get_settings().db_statement_timeout_ms
    assert expected == 30000  # default (F-7); 0 would disable it
    with get_engine().connect() as conn:
        assert conn.execute(text("SHOW statement_timeout")).scalar_one() == "30s"


def test_cancelled_statement_is_a_retryable_503() -> None:
    r = TestClient(_mini_app()).get("/slow")
    assert r.status_code == 503, r.text
    assert r.json()["error"]["code"] == "QUERY_TIMEOUT"
