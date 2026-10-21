"""Liveness/readiness. Readiness reports each dependency; DB failure => 503, others => degraded."""

from collections.abc import Callable
from typing import Literal

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from asseta.core.config import get_settings
from asseta.core.db import get_engine

router = APIRouter(prefix="/api/v1/health", tags=["health"])


class CheckResult(BaseModel):
    status: Literal["ok", "down"]
    detail: str | None = None


class ReadinessDto(BaseModel):
    status: Literal["ok", "degraded", "down"]
    checks: dict[str, CheckResult]


def _db() -> CheckResult:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT postgis_version()"))
    return CheckResult(status="ok")


def _redis() -> CheckResult:
    import redis

    s = get_settings()
    redis.Redis.from_url(s.redis_url, socket_timeout=s.http_timeout_seconds).ping()
    return CheckResult(status="ok")


def _kafka() -> CheckResult:
    from confluent_kafka.admin import AdminClient

    s = get_settings()
    AdminClient({"bootstrap.servers": s.kafka_bootstrap}).list_topics(timeout=s.http_timeout_seconds)
    return CheckResult(status="ok")


def _keycloak() -> CheckResult:
    s = get_settings()
    resp = httpx.get(s.jwks_url, timeout=s.http_timeout_seconds)
    resp.raise_for_status()
    return CheckResult(status="ok")


def _object_store() -> CheckResult:
    s = get_settings()
    resp = httpx.get(f"{s.s3_endpoint}/minio/health/ready", timeout=s.http_timeout_seconds)
    resp.raise_for_status()
    return CheckResult(status="ok")


CHECKS: dict[str, Callable[[], CheckResult]] = {
    "database": _db,
    "redis": _redis,
    "kafka": _kafka,
    "keycloak": _keycloak,
    "object_store": _object_store,
}


@router.get("/live", operation_id="getLiveness")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=ReadinessDto, operation_id="getReadiness")
def ready() -> JSONResponse:
    results: dict[str, CheckResult] = {}
    for name, check in CHECKS.items():
        try:
            results[name] = check()
        except Exception as exc:  # report, never crash the probe
            results[name] = CheckResult(status="down", detail=type(exc).__name__)
    if results["database"].status == "down":
        overall: Literal["ok", "degraded", "down"] = "down"
    else:
        overall = "ok" if all(r.status == "ok" for r in results.values()) else "degraded"
    body = ReadinessDto(status=overall, checks=results)
    return JSONResponse(status_code=503 if overall == "down" else 200, content=body.model_dump())
