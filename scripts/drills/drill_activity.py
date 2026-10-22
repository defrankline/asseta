"""Background domain activity on the throwaway drill tenant, used by the disruption drills.

Each tick posts one tracker position through the gateway-authenticated ingestion path (→ PositionStored outbox
event → timeline worker, notification worker live channel) and every `job_every` ticks creates a job and submits it
(→ JobPendingApproval → notification worker inbox row for the owner). Every call's outcome is recorded so a drill
can prove "API stayed up" and verify that each accepted effect reached the consumers exactly once.
"""

from __future__ import annotations

import random
import threading
import time
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from drill_common import API, ENV, Session, now_utc, sql

from asseta.tools.gps_simulator import Fix, traccar_payload


class Activity(threading.Thread):
    def __init__(self, state: dict[str, Any], interval: float = 0.5, job_every: int = 4, machines: int = 20):
        super().__init__(daemon=True)
        self.state, self.interval, self.job_every = state, interval, job_every
        self.machines = state["machines"][:machines]
        self.session = Session(state)
        self.stop_flag = threading.Event()
        self.lock = threading.Lock()
        self.outcomes: Counter[str] = Counter()
        self.failures: list[tuple[float, str, str]] = []
        self.positions: dict[tuple[str, int], float] = {}  # (device, epoch s) -> sent at
        self.jobs: list[str] = []
        self.started_at = now_utc()
        self._sec = int(time.time()) - 600  # event times advance 1 s per position: unique per device, never future

    def _record(self, kind: str, status: int | str) -> bool:
        ok = isinstance(status, int) and 200 <= status < 300
        with self.lock:
            self.outcomes[f"{kind} {status}"] += 1
            if not ok:
                self.failures.append((time.time(), kind, str(status)))
        return ok

    def position(self, c: httpx.Client) -> None:
        m = random.choice(self.machines)
        self._sec += 1
        t = now_utc().replace(microsecond=0) - timedelta(seconds=int(time.time()) - self._sec)
        fix = Fix(t, -6.8 + random.random() / 100, 39.28 + random.random() / 100, 5.0, 90.0)
        try:
            r = c.post(
                f"{API}/telemetry/traccar",
                json=traccar_payload(m["device"], fix),
                headers={"X-Asseta-Gateway-Key": ENV["ASSETA_TRACCAR_GATEWAY_KEY"]},
            )
            status: int | str = r.status_code
        except httpx.HTTPError as exc:
            status = type(exc).__name__
        if self._record("position", status):
            self.positions[(m["device"], int(t.timestamp()))] = time.time()

    def job(self, c: httpx.Client) -> None:
        m = random.choice(self.machines)
        tag = uuid.uuid4().hex[:8]
        try:
            r = c.post(
                f"{API}/tenant/jobs",
                headers=self.session.headers(),
                json={
                    "contract_id": self.state["contract_id"],
                    "job_number": f"DRL-{tag}",
                    "machine_id": m["machine_id"],
                    "planned_start": now_utc().isoformat(),
                    "hourly_rate": "50000",
                },
            )
            if not self._record("job.create", r.status_code):
                return
            jid = r.json()["id"]
            r = c.post(
                f"{API}/tenant/jobs/{jid}/transitions", headers=self.session.headers(), json={"action": "SUBMIT"}
            )
            if self._record("job.submit", r.status_code):
                self.jobs.append(jid)
        except httpx.HTTPError as exc:
            self._record("job", type(exc).__name__)

    def run(self) -> None:
        n = 0
        with httpx.Client(timeout=15) as c:
            while not self.stop_flag.is_set():
                t0 = time.monotonic()
                self.position(c)
                n += 1
                if n % self.job_every == 0:
                    self.job(c)
                time.sleep(max(0.0, self.interval - (time.monotonic() - t0)))

    def stop(self) -> None:
        self.stop_flag.set()
        self.join(timeout=30)

    def summary(self) -> str:
        return ", ".join(f"{k}: {v}" for k, v in sorted(self.outcomes.items()))


def verify_effects(state: dict[str, Any], act: Activity) -> dict[str, Any]:
    """Exactly-once checks over everything the activity got a 2xx for."""
    tid = state["tenant_id"]
    earliest = min((k[1] for k in act.positions), default=int(act.started_at.timestamp()))
    since = datetime.fromtimestamp(earliest - 60, UTC)  # every event time the activity produced
    stored = {
        (r[0], int(r[1].timestamp())): r[2]
        for r in sql(
            "SELECT t.external_id, p.event_time, count(*) FROM machine_position_event p JOIN tracker t "
            "ON t.id = p.tracker_id WHERE p.tenant_id = %s AND p.event_time >= %s GROUP BY 1, 2",
            (tid, since),
        )
    }
    lost = [k for k in act.positions if k not in stored]
    dup_pos = sum(1 for k in act.positions if stored.get(k, 0) > 1)
    pending_events = sql(
        "SELECT o.id::text FROM outbox_event o WHERE o.tenant_id = %s AND o.event_type = 'JobPendingApproval' "
        "AND o.payload->>'job_id' = ANY(%s)",
        (tid, act.jobs),
    )
    event_ids = [r[0] for r in pending_events]
    notif = sql(
        "SELECT source_event_id::text, recipient_user_id::text, count(*) FROM notification WHERE tenant_id = %s "
        "AND source_event_id::text = ANY(%s) GROUP BY 1, 2",
        (tid, event_ids),
    )
    dup_notif = sum(1 for r in notif if r[2] > 1)
    notified = {r[0] for r in notif}
    unpublished = sql("SELECT count(*) FROM outbox_event WHERE tenant_id = %s AND published_at IS NULL", (tid,))[0][0]
    return {
        "positions_acked": len(act.positions),
        "positions_lost": len(lost),
        "positions_duplicated": dup_pos,
        "jobs_submitted": len(act.jobs),
        "job_events": len(event_ids),
        "job_events_without_notification": len(set(event_ids) - notified),
        "duplicate_notifications": dup_notif,
        "outbox_unpublished": int(unpublished),
    }
