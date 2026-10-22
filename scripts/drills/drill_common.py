"""Shared helpers for the Gate 7 hardening drills (scripts/drills/README.md).

Every drill runs against the LOCAL docker compose stack only (guarded), never prints secrets (they are read from
.env into memory), and writes its evidence to docs/evidence/drills/<date>-<drill>.md. Run from backend/ so the
backend virtualenv (httpx, psycopg, boto3, websockets) and `asseta` package are importable:

    cd backend && uv run python ../scripts/drills/<drill>.py
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
STATE_DIR = ROOT / ".drills"  # gitignored; throwaway tenant credentials (0600), removed by drill_tenant.py purge
EVIDENCE_DIR = ROOT / "docs" / "evidence" / "drills"
TIMEOUT = 30.0
CONSUMER_GROUPS = ("asseta-timeline", "asseta-notification", "asseta-intelligence")


def read_env(path: Path = ROOT / ".env") -> dict[str, str]:
    return dict(
        line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#")
    )


ENV = read_env()
API_BASE = f"http://localhost:{ENV.get('ASSETA_API_PORT', '8000')}"
API = f"{API_BASE}/api/v1"
KC = ENV.get("ASSETA_PUBLIC_KEYCLOAK_URL", "http://localhost:8080")


def guard_local() -> None:
    """Refuse to run against anything that is not the local development compose stack."""
    if ENV.get("ASSETA_ENVIRONMENT", "development") == "production":
        raise SystemExit("refusing: ASSETA_ENVIRONMENT=production")
    for url in (KC, API):
        if not url.startswith(("http://localhost", "http://127.0.0.1")):
            raise SystemExit(f"refusing: {url} is not local")
    ps = compose("ps", "--format", "json", capture=True).stdout
    if "asseta" not in ps:
        raise SystemExit("refusing: compose project 'asseta' is not running")


def superuser_dsn(db: str = "asseta") -> str:
    return (
        f"postgresql://postgres:{ENV['POSTGRES_SUPERUSER_PASSWORD']}@localhost:{ENV.get('ASSETA_PG_PORT', '5433')}/{db}"
    )


def sql(query: str, params: tuple[Any, ...] = (), db: str = "asseta") -> list[tuple[Any, ...]]:
    with psycopg.connect(superuser_dsn(db), autocommit=True) as conn:
        return list(conn.execute(query, params).fetchall())


def compose(*args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args], cwd=ROOT, text=True, capture_output=capture, check=check, timeout=600
    )


def wait_until(pred: Callable[[], bool], timeout: float, interval: float = 0.5) -> float | None:
    """Seconds until `pred()` is true, or None on timeout. Exceptions count as 'not yet'."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            if pred():
                return time.monotonic() - t0
        except Exception:  # noqa: BLE001 - dependency still coming back
            pass
        time.sleep(interval)
    return None


def readiness() -> dict[str, Any]:
    try:
        r = httpx.get(f"{API}/health/ready", timeout=10)
        body: dict[str, Any] = r.json()
        body["http_status"] = r.status_code
        return body
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "unreachable", "error": type(exc).__name__}


def ready_summary(r: dict[str, Any]) -> str:
    checks = r.get("checks") or {}
    parts = ", ".join(f"{k}={v.get('status')}" for k, v in checks.items())
    return f"HTTP {r.get('http_status', '-')} {r.get('status')} ({parts})"


def kafka_lag(group: str) -> int | None:
    """Total consumer lag for a group (kafka-consumer-groups.sh inside the broker container); None if unknown."""
    p = compose(
        "exec",
        "-T",
        "kafka",
        "/opt/kafka/bin/kafka-consumer-groups.sh",
        "--bootstrap-server",
        "localhost:9092",
        "--describe",
        "--group",
        group,
        capture=True,
        check=False,
    )
    if p.returncode != 0:
        return None
    total, seen = 0, False
    for line in p.stdout.splitlines():
        cols = line.split()
        if len(cols) >= 6 and cols[0] == group:
            seen = True
            lag = cols[5]
            total += int(lag) if lag.isdigit() else 0
    return total if seen else None


def lags() -> dict[str, int | None]:
    return {g: kafka_lag(g) for g in CONSUMER_GROUPS}


def outbox_pending(tenant_id: str | None = None) -> int:
    q = "SELECT count(*) FROM outbox_event WHERE published_at IS NULL"
    rows = sql(q + " AND tenant_id = %s", (tenant_id,)) if tenant_id else sql(q)
    return int(rows[0][0])


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[int(p) - 1]


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass
class Evidence:
    """Markdown evidence file: commands, timings, results, PASS/FAIL, what is not simulated."""

    drill: str
    title: str
    lines: list[str] = field(default_factory=list)
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    started: datetime = field(default_factory=now_utc)

    def say(self, text: str = "") -> None:
        print(text, flush=True)
        self.lines.append(text)

    def table(self, header: list[str], rows: list[list[Any]]) -> None:
        self.lines.append("| " + " | ".join(header) + " |")
        self.lines.append("|" + "---|" * len(header))
        for r in rows:
            self.lines.append("| " + " | ".join(str(c) for c in r) + " |")
        self.lines.append("")
        for r in rows:
            print("  " + " | ".join(str(c) for c in r), flush=True)

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)
        return ok

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def write(self, not_simulated: list[str], commands: list[str]) -> Path:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        path = EVIDENCE_DIR / f"{self.started.date().isoformat()}-{self.drill}.md"
        ended = now_utc()
        verdict = "PASS" if self.passed else "FAIL"
        out = [
            f"# Drill: {self.title}",
            "",
            f"* **Result:** {verdict}",
            f"* **Run:** {self.started.isoformat(timespec='seconds')} → {ended.isoformat(timespec='seconds')} "
            f"({(ended - self.started).total_seconds():.0f} s)",
            "* **Target:** local docker compose stack (single host, single broker/node); script "
            f"`scripts/drills/{self.drill.replace('-', '_')}.py`",
            "",
            "## Commands",
            "",
            "```bash",
            *commands,
            "```",
            "",
            "## Log",
            "",
            *self.lines,
            "",
            "## Checks",
            "",
            "| Check | Result | Detail |",
            "|---|---|---|",
            *[f"| {n} | {'PASS' if ok else 'FAIL'} | {d} |" for n, ok, d in self.checks],
            "",
            "## Not simulated",
            "",
            *[f"* {x}" for x in not_simulated],
            "",
        ]
        path.write_text("\n".join(out))
        print(f"evidence: {path.relative_to(ROOT)} ({verdict})", flush=True)
        return path


# ---------------------------------------------------------------- throwaway tenant (created by drill_tenant.py)


class Session:
    """Password-grant tokens for the throwaway users via the throwaway confidential client (cached ~3 min)."""

    def __init__(self, state: dict[str, Any]):
        self.state = state
        self._tokens: dict[str, tuple[float, str]] = {}

    def token(self, who: str) -> str:
        cached = self._tokens.get(who)
        if cached and time.monotonic() - cached[0] < 180:
            return cached[1]
        user = self.state["users"][who]
        r = httpx.post(
            f"{KC}/realms/asseta/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": self.state["client_id"],
                "client_secret": self.state["client_secret"],
                "username": user["email"],
                "password": user["password"],
                "scope": "openid",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        tok = str(r.json()["access_token"])
        self._tokens[who] = (time.monotonic(), tok)
        return tok

    def headers(self, who: str = "owner", idempotent: bool = True) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.token(who)}"}
        if who != "platform":
            h["X-Tenant-ID"] = self.state["tenant_id"]
        if idempotent:
            h["Idempotency-Key"] = str(uuid.uuid4())
        return h

    def call(self, method: str, path: str, who: str = "owner", **kw: Any) -> httpx.Response:
        return httpx.request(method, f"{API}{path}", headers=self.headers(who), timeout=TIMEOUT, **kw)


def state_path() -> Path:
    return STATE_DIR / "tenant.json"


def load_state() -> dict[str, Any]:
    p = state_path()
    if not p.exists():
        raise SystemExit("no throwaway drill tenant: run `uv run python ../scripts/drills/drill_tenant.py create`")
    data: dict[str, Any] = json.loads(p.read_text())
    return data


def save_state(data: dict[str, Any]) -> None:
    STATE_DIR.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(state_path(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)


def expect(r: httpx.Response, status: int, what: str) -> dict[str, Any]:
    """Raises with the server's error code only (never the request, which carries a token)."""
    if r.status_code != status:
        try:
            err = r.json().get("error", {})
            code = f"{err.get('code', '')} {err.get('message', '')}"
        except ValueError:
            code = ""
        raise RuntimeError(f"{what}: HTTP {r.status_code} {code}".strip())
    body: dict[str, Any] = r.json() if r.content else {}
    return body
