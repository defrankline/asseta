"""Drill (f): queue backlog recovery (throwaway drill tenant).

    cd backend && uv run python ../scripts/drills/queue_backlog.py [--positions 2000] [--jobs 60]

The timeline and notification workers are stopped; a burst of `--positions` tracker positions (8 concurrent
senders, gateway path) and `--jobs` job submissions (each → JobPendingApproval → one owner notification) builds a
Kafka backlog. The workers are started again and the catch-up of each consumer group to lag 0 is timed; then
every acknowledged position is checked stored once, every job event notified once, and the drill machines' latest
positions/timeline reflect the newest fixes.
"""

from __future__ import annotations

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
from drill_activity import Activity, verify_effects
from drill_common import (
    API,
    ENV,
    Evidence,
    compose,
    guard_local,
    kafka_lag,
    lags,
    load_state,
    now_utc,
    outbox_pending,
    readiness,
    wait_until,
)

from asseta.tools.gps_simulator import Fix, traccar_payload

STOPPED = ("timeline-worker", "notification-worker")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", type=int, default=2000)
    ap.add_argument("--jobs", type=int, default=60)
    a = ap.parse_args()
    guard_local()
    state = load_state()
    tid = state["tenant_id"]
    ev = Evidence("queue-backlog", "Queue backlog recovery (timeline + notification workers stopped during a burst)")
    ev.say(
        f"Throwaway tenant `{tid}`; burst of {a.positions} positions over {len(state['machines'])} machines and "
        f"{a.jobs} job submissions while {', '.join(STOPPED)} are stopped."
    )
    ev.say("")
    ev.say(f"* Baseline lag {lags()}")
    compose("stop", *STOPPED, capture=True)
    act = Activity(state)  # used for its bookkeeping + verify_effects; driven manually below
    machines = state["machines"]
    base = int(time.time()) - 3 * 3600 + 7200  # event times inside the assignment window, unique per (device, s)
    lock = threading.Lock()

    def send(i: int) -> None:
        m = machines[i % len(machines)]
        sec = base + i // len(machines) * 2 + 1
        t = now_utc().replace(microsecond=0) - timedelta(seconds=int(time.time()) - sec)
        fix = Fix(t, -6.81 + (i % 97) / 10000, 39.27 + (i % 89) / 10000, 4.0, 45.0)
        with httpx.Client(timeout=30) as c:
            try:
                r = c.post(
                    f"{API}/telemetry/traccar",
                    json=traccar_payload(m["device"], fix),
                    headers={"X-Asseta-Gateway-Key": ENV["ASSETA_TRACCAR_GATEWAY_KEY"]},
                )
                status: int | str = r.status_code
            except httpx.HTTPError as exc:
                status = type(exc).__name__
        if act._record("position", status):  # noqa: SLF001 - shared bookkeeping
            with lock:
                act.positions[(m["device"], int(t.timestamp()))] = time.time()

    t0 = time.monotonic()
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(send, range(a.positions)))
    with httpx.Client(timeout=30) as c:
        for _ in range(a.jobs):
            act.job(c)
    burst_s = time.monotonic() - t0
    time.sleep(5)  # let the relay publish
    backlog = {g: kafka_lag(g) for g in ("asseta-timeline", "asseta-notification")}
    ev.say(
        f"* Burst: {act.summary()} in {burst_s:.1f} s; tenant outbox pending {outbox_pending(tid)}; "
        f"backlog (consumer lag) {backlog}"
    )
    ev.check("backlog built while workers stopped", all((v or 0) > 0 for v in backlog.values()), str(backlog))
    t1 = time.monotonic()
    compose("start", *STOPPED, capture=True)
    t_notif = wait_until(lambda: kafka_lag("asseta-notification") == 0, 1800, 2.0)
    t_timeline = wait_until(lambda: kafka_lag("asseta-timeline") == 0, 3600, 2.0)
    total = time.monotonic() - t1
    rate_tl = (backlog["asseta-timeline"] or 0) / t_timeline if t_timeline else float("nan")
    rate_nt = (backlog["asseta-notification"] or 0) / t_notif if t_notif else float("nan")
    ev.table(
        ["consumer group", "backlog (messages)", "catch-up (s)", "≈ msg/s"],
        [
            [
                "asseta-notification",
                backlog["asseta-notification"],
                f"{t_notif:.0f}" if t_notif else "timeout",
                f"{rate_nt:.1f}",
            ],
            [
                "asseta-timeline",
                backlog["asseta-timeline"],
                f"{t_timeline:.0f}" if t_timeline else "timeout",
                f"{rate_tl:.1f}",
            ],
        ],
    )
    ev.check("notification worker caught up", t_notif is not None, f"{t_notif}")
    ev.check("timeline worker caught up", t_timeline is not None, f"{t_timeline}")
    eff = verify_effects(state, act)
    ev.say(f"* Recovery total {total:.0f} s; effects {eff}; final lag {lags()}")
    ev.check("API answered every burst request", not act.failures, f"{len(act.failures)} failures")
    ev.check(
        "no acknowledged position lost or duplicated",
        eff["positions_lost"] == 0 and eff["positions_duplicated"] == 0,
        str(eff),
    )
    ev.check(
        "every job event notified exactly once",
        eff["job_events"] == eff["jobs_submitted"] == a.jobs
        and eff["job_events_without_notification"] == 0
        and eff["duplicate_notifications"] == 0,
        str(eff),
    )
    ev.check("final readiness ok", readiness().get("status") == "ok", "")
    ev.write(
        not_simulated=[
            "Multi-hour backlogs / topic retention expiry (default 7 days; a worker down longer than retention "
            "would lose its backlog — the outbox keeps every event and can be re-published).",
            "Scaling consumers horizontally: topics are auto-created with 1 partition, so one consumer per group.",
            "Dead-letter handling: a poison message is retried forever (not committed) — not exercised here.",
        ],
        commands=[
            "cd backend",
            f"uv run python ../scripts/drills/queue_backlog.py --positions {a.positions} --jobs {a.jobs}",
        ],
    )


if __name__ == "__main__":
    main()
