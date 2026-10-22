"""Drill (c): Kafka outage during activity (throwaway drill tenant; create it with drill_tenant.py first).

    cd backend && uv run python ../scripts/drills/kafka_outage.py [--outage 60]

Background activity (drill_activity.py: positions + job submissions) runs throughout. Kafka is stopped for
`--outage` seconds: the API must keep answering 2xx (readiness `degraded`, kafka down), domain events must
accumulate in the transactional outbox. Kafka is started again: measured are broker recovery, outbox drain and the
lag of the timeline, notification and intelligence consumer groups back to 0. Then exactly-once is verified: every
acknowledged position stored once, every submitted job's JobPendingApproval event produced its notification once,
and Kafka-level redeliveries (offset growth minus events published) are reported — consumers must absorb them.
"""

from __future__ import annotations

import argparse
import time

from drill_activity import Activity, verify_effects
from drill_common import (
    CONSUMER_GROUPS,
    Evidence,
    compose,
    guard_local,
    kafka_lag,
    lags,
    load_state,
    now_utc,
    outbox_pending,
    readiness,
    ready_summary,
    sql,
    wait_until,
)


def log_end_total() -> int | None:
    """Sum of LOG-END-OFFSET over the asseta.* topics (via the notification group, which subscribes to all)."""
    p = compose(
        "exec",
        "-T",
        "kafka",
        "/opt/kafka/bin/kafka-consumer-groups.sh",
        "--bootstrap-server",
        "localhost:9092",
        "--describe",
        "--group",
        "asseta-notification",
        capture=True,
        check=False,
    )
    vals = [
        int(c[4])
        for c in (line.split() for line in p.stdout.splitlines())
        if len(c) >= 6 and c[0] == "asseta-notification" and c[4].isdigit()
    ]
    return sum(vals) if vals else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outage", type=int, default=60)
    a = ap.parse_args()
    guard_local()
    state = load_state()
    tid = state["tenant_id"]
    ev = Evidence("kafka-outage", "Kafka broker outage and recovery under activity")
    ev.say(f"Throwaway tenant `{tid}`; activity = 1 position / 0.5 s + 1 job create+submit / 2 s; outage {a.outage} s.")
    ev.say("")
    base_lags = lags()
    ev.say(
        f"* Baseline: {ready_summary(readiness())}; consumer lag {base_lags}; tenant outbox pending "
        f"{outbox_pending(tid)}"
    )
    off0, t_win0 = log_end_total(), now_utc()
    act = Activity(state)
    act.start()
    time.sleep(15)
    t_stop = time.monotonic()
    compose("stop", "kafka", capture=True)
    ev.say(f"* `docker compose stop kafka` took {time.monotonic() - t_stop:.1f} s (activity continues)")
    samples = []
    while time.monotonic() - t_stop < a.outage:
        time.sleep(10)
        r = readiness()
        samples.append((round(time.monotonic() - t_stop), ready_summary(r), outbox_pending(tid)))
    ev.table(["s after stop", "readiness", "tenant outbox pending"], [list(s) for s in samples])
    peak_pending = max(s[2] for s in samples)
    fails_during = [f for f in act.failures if f[0] >= time.time() - a.outage - 10]
    ev.check(
        "API stayed up during the outage (all activity calls 2xx)",
        not fails_during,
        f"{len(fails_during)} failures {fails_during[:3]}",
    )
    last = samples[-1][1]
    ev.check(
        "readiness reports kafka down while the broker is stopped (degraded, HTTP 200)",
        "kafka=down" in last and "HTTP 200" in last,
        last,
    )
    ev.check("domain events accumulate in the outbox during the outage", peak_pending > 0, f"peak {peak_pending}")

    t_start = time.monotonic()
    compose("start", "kafka", capture=True)
    t_broker = wait_until(lambda: kafka_lag("asseta-timeline") is not None, 180, 1.0)
    t_ready = wait_until(lambda: "kafka=ok" in ready_summary(readiness()), 180, 1.0)
    t_drain = wait_until(lambda: outbox_pending(tid) == 0, 600, 1.0)
    ev.say(
        f"* `docker compose start kafka`: broker answering after {t_broker} s; readiness kafka=ok after "
        f"{t_ready} s; tenant outbox drained {t_drain if t_drain is None else round(t_drain, 1)} s after start"
    )
    time.sleep(15)  # keep producing for a while after recovery
    act.stop()
    t_lags = wait_until(lambda: all((v or 0) == 0 for v in lags().values()) and outbox_pending(tid) == 0, 900, 3.0)
    total_recovery = time.monotonic() - t_start
    ev.say(
        f"* All consumer groups {list(CONSUMER_GROUPS)} at lag 0 and outbox empty "
        f"{total_recovery:.0f} s after Kafka start (activity stopped 15 s after the outbox drained)"
    )
    ev.check("relay drained the outbox after recovery", t_drain is not None, f"{t_drain}")
    ev.check("consumers caught up (lag 0 for timeline, notification, intelligence)", t_lags is not None, str(lags()))
    time.sleep(3)
    eff = verify_effects(state, act)
    off1 = log_end_total()
    published = sql("SELECT count(*) FROM outbox_event WHERE published_at >= %s", (t_win0,))[0][0]
    redelivered = (off1 - off0 - published) if off0 is not None and off1 is not None else None
    retried = sql(
        "SELECT count(*), coalesce(max(attempts), 0) FROM outbox_event WHERE tenant_id = %s AND "
        "created_at >= %s AND attempts > 0",
        (tid, t_win0),
    )[0]
    ev.say(f"* Activity: {act.summary()}")
    ev.say(
        f"* Outbox: {retried[0]} tenant events needed retries (max attempts {retried[1]}); events published in "
        f"the window {published}; Kafka offset growth {None if off0 is None or off1 is None else off1 - off0} "
        f"→ broker-level redeliveries {redelivered}"
    )
    ev.say(f"* Effects: {eff}")
    ev.check("no acknowledged position lost", eff["positions_lost"] == 0, str(eff["positions_lost"]))
    ev.check("no position stored twice", eff["positions_duplicated"] == 0, str(eff["positions_duplicated"]))
    ev.check(
        "every submitted job produced its JobPendingApproval event",
        eff["job_events"] == eff["jobs_submitted"],
        f"{eff['job_events']}/{eff['jobs_submitted']}",
    )
    ev.check(
        "every JobPendingApproval event notified (consumer caught up)",
        eff["job_events_without_notification"] == 0,
        str(eff["job_events_without_notification"]),
    )
    ev.check(
        "no duplicate notifications despite at-least-once delivery",
        eff["duplicate_notifications"] == 0,
        str(eff["duplicate_notifications"]),
    )
    ev.check("final readiness ok", readiness().get("status") == "ok", ready_summary(readiness()))
    ev.write(
        not_simulated=[
            "Single broker (RF 1): no partition leader election, ISR shrink or multi-broker partial outage.",
            "Network partition between API and broker (the broker process was stopped cleanly); no data-dir loss.",
            "Consumer crash mid-batch is covered by the API/worker restart drill, not here.",
        ],
        commands=["cd backend", f"uv run python ../scripts/drills/kafka_outage.py --outage {a.outage}"],
    )


if __name__ == "__main__":
    main()
