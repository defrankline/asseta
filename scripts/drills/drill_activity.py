"""Background domain activity on the throwaway drill tenant, used by the disruption drills.

Each tick posts one tracker position through the gateway-authenticated ingestion path (→ PositionStored outbox
event → timeline worker, notification worker live channel) and every `report_every` ticks the owner submits an
opening machine report on the next drill machine (→ MachineReportSubmitted → notification worker inbox row for the
drill manager, the other approver). The manager rejects a machine's waiting report before its next one (one report per
machine waits for a decision). Every call's outcome is recorded so a drill can prove "API stayed up" and verify that
each accepted effect reached the consumers exactly once.
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
    def __init__(self, state: dict[str, Any], interval: float = 0.5, report_every: int = 4, machines: int = 20):
        super().__init__(daemon=True)
        self.state, self.interval, self.report_every = state, interval, report_every
        self.machines = state["machines"][:machines]
        self.session = Session(state)
        self.stop_flag = threading.Event()
        self.lock = threading.Lock()
        self.outcomes: Counter[str] = Counter()
        self.failures: list[tuple[float, str, str]] = []
        self.positions: dict[tuple[str, int], float] = {}  # (device, epoch s) -> sent at
        self.reports: list[str] = []
        self.waiting: dict[str, str] = {}  # machine id -> its report waiting for a decision
        self._next = 0
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

    def report(self, c: httpx.Client) -> None:
        """An opening machine report (a manual DAILY reading, no lines) on the next drill machine, as the owner."""
        m = self.machines[self._next % len(self.machines)]
        self._next += 1
        try:
            waiting = self.waiting.pop(m["machine_id"], None)
            if waiting:  # one report per machine waits for a decision: the manager rejects the earlier one
                r = c.post(
                    f"{API}/tenant/machine-reports/{waiting}/reject",
                    headers=self.session.headers("manager"),
                    json={"reason": "Drill: superseded"},
                )
                if not self._record("report.reject", r.status_code):
                    self.waiting[m["machine_id"]] = waiting
                    return
            at = now_utc()
            r = c.post(
                f"{API}/tenant/machine-reports",
                headers=self.session.headers(),
                json={
                    "id": str(uuid.uuid4()),
                    "machine_id": m["machine_id"],
                    "opening": True,
                    "lines": [],
                    "capture": {
                        "id": str(uuid.uuid4()),
                        "machine_id": m["machine_id"],
                        "kind": "DAILY",
                        "capture_mode": "MANUAL",
                        "reading": "100.0",
                        "gps": {
                            "status": "FIX",
                            "latitude": -6.8,
                            "longitude": 39.28,
                            "accuracy_m": 6.0,
                            "captured_at": at.isoformat(),
                            "provider": "fused",
                        },
                        "device_id": "drill-device",
                        "captured_at": at.isoformat(),
                    },
                },
            )
            if self._record("report.submit", r.status_code):
                self.reports.append(r.json()["id"])
                self.waiting[m["machine_id"]] = r.json()["id"]
        except httpx.HTTPError as exc:
            self._record("report", type(exc).__name__)

    def run(self) -> None:
        n = 0
        with httpx.Client(timeout=15) as c:
            while not self.stop_flag.is_set():
                t0 = time.monotonic()
                self.position(c)
                n += 1
                if n % self.report_every == 0:
                    self.report(c)
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
        "SELECT o.id::text FROM outbox_event o WHERE o.tenant_id = %s AND o.event_type = 'MachineReportSubmitted' "
        "AND o.payload->>'report_id' = ANY(%s)",
        (tid, act.reports),
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
        "reports_submitted": len(act.reports),
        "report_events": len(event_ids),
        "report_events_without_notification": len(set(event_ids) - notified),
        "duplicate_notifications": dup_notif,
        "outbox_unpublished": int(unpublished),
    }
