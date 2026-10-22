"""Drill (b): telemetry load check on the throwaway drill tenant (create it first with drill_tenant.py).

    cd backend && uv run python ../scripts/drills/telemetry_load.py [--fixes 30] [--threads 20]

Phase A — real gateway path: every drill device sends `--fixes` OsmAnd messages (60 s apart, every 7th pair swapped =
out-of-order) to Traccar's device port 5055; Traccar forwards each position to Asseta. Then each device uploads 3
*late* fixes (75 min old, as after a coverage gap) and re-sends 2 already-sent fixes (duplicates).
Phase B — direct gateway-authenticated path (`POST /telemetry/traccar` with the gateway key, as Traccar does) at
`--threads` concurrency, `--fixes` per device 15 s apart with the same out-of-order mix.

Measured: client send rate and server ingest rate per phase; per-position latency send → `machine_position_event`
(received_at); latency send → `machine_latest_position` showing each machine's newest fix (sampled every 0.25 s);
timeline-worker Kafka lag and tenant outbox backlog until drained; exact set comparison of sent vs stored
(device, event_time) pairs (no loss), duplicates rejected as DUPLICATE (no double storage), late flags.
"""

from __future__ import annotations

import argparse
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import httpx
from drill_common import (
    API_BASE,
    ENV,
    Evidence,
    guard_local,
    kafka_lag,
    load_state,
    now_utc,
    outbox_pending,
    pct,
    sql,
    wait_until,
)

from asseta.tools.gps_simulator import Fix, delivery_order, route, traccar_payload

TRACCAR = f"http://localhost:{ENV.get('ASSETA_TRACCAR_OSMAND_PORT', '5055')}"


def osmand_params(device: str, fix: Fix) -> dict[str, str | float | int]:
    return {
        "id": device,
        "lat": fix.lat,
        "lon": fix.lon,
        "timestamp": int(fix.time.timestamp()),
        "speed": round(fix.speed_kmh / 1.852, 4),
        "bearing": fix.course,
        "accuracy": fix.accuracy_m or 0,
        "valid": "true",
        "ignition": "true",
    }


def track(i: int, start: datetime, n: int, interval: int) -> list[Fix]:
    lat, lon = -6.80 - i * 0.002, 39.20 + i * 0.002
    fixes = route([(lat, lon), (lat + 0.02, lon + 0.02)], start, 20.0, interval, dwell_points=n)[:n]
    return [Fix(f.time.replace(microsecond=0), f.lat, f.lon, f.speed_kmh, f.course) for f in fixes]


class LatestWatcher(threading.Thread):
    """Samples machine_latest_position and records when each machine first shows its expected newest fix."""

    def __init__(self, tenant_id: str, expected: dict[str, datetime]):
        super().__init__(daemon=True)
        self.tenant_id, self.expected = tenant_id, expected
        self.seen: dict[str, float] = {}
        self.stop = threading.Event()

    def run(self) -> None:
        while not self.stop.is_set() and len(self.seen) < len(self.expected):
            rows = sql(
                "SELECT machine_id::text, event_time FROM machine_latest_position WHERE tenant_id = %s",
                (self.tenant_id,),
            )
            t = time.time()
            for mid, et in rows:
                if mid not in self.seen and mid in self.expected and et >= self.expected[mid]:
                    self.seen[mid] = t
            time.sleep(0.25)


class LagSampler(threading.Thread):
    def __init__(self, tenant_id: str):
        super().__init__(daemon=True)
        self.tenant_id = tenant_id
        self.samples: list[tuple[float, int | None, int]] = []
        self.stop = threading.Event()

    def run(self) -> None:
        while not self.stop.is_set():
            self.samples.append((time.time(), kafka_lag("asseta-timeline"), outbox_pending(self.tenant_id)))
            time.sleep(1.0)


def stored(tenant_id: str, since: datetime) -> dict[tuple[str, int], tuple[datetime, bool]]:
    rows = sql(
        "SELECT t.external_id, p.event_time, p.received_at, p.is_late FROM machine_position_event p "
        "JOIN tracker t ON t.id = p.tracker_id WHERE p.tenant_id = %s AND p.event_time >= %s",
        (tenant_id, since),
    )
    return {(r[0], int(r[1].timestamp())): (r[2], bool(r[3])) for r in rows}


def run_phase(
    ev: Evidence,
    name: str,
    machines: list[dict[str, str]],
    plan: dict[str, list[Fix]],
    extra: dict[str, list[Fix]],
    sender: str,
    threads: int,
    tenant_id: str,
    gateway_key: str,
) -> dict[tuple[str, int], float]:
    """Sends `plan` (+ `extra` afterwards) per device; returns client send time per (device, epoch second)."""
    sent: dict[tuple[str, int], float] = {}
    lock = threading.Lock()
    errors: list[str] = []
    expected_latest = {m["machine_id"]: max(f.time for f in plan[m["device"]]) for m in machines}
    watcher = LatestWatcher(tenant_id, expected_latest)
    watcher.start()

    def send_device(device: str, fixes: Iterator[Fix] | list[Fix]) -> None:
        with httpx.Client(timeout=30) as c:
            for f in fixes:
                t = time.time()
                try:
                    if sender == "osmand":
                        r = c.get(TRACCAR, params=osmand_params(device, f))
                    else:
                        r = c.post(
                            f"{API_BASE}/api/v1/telemetry/traccar",
                            json=traccar_payload(device, f),
                            headers={"X-Asseta-Gateway-Key": gateway_key},
                        )
                    status = str(r.status_code) if r.status_code not in (200, 202) else ""
                except httpx.HTTPError as exc:  # e.g. ReadTimeout: counted, the run continues
                    status = type(exc).__name__
                with lock:
                    sent.setdefault((device, int(f.time.timestamp())), t)
                    if status:
                        errors.append(f"{device} {status}")

    t0 = time.time()
    with ThreadPoolExecutor(threads) as pool:
        list(pool.map(lambda m: send_device(m["device"], delivery_order(plan[m["device"]], swap_every=7)), machines))
    t_main = time.time() - t0
    if extra:
        with ThreadPoolExecutor(threads) as pool:
            list(pool.map(lambda m: send_device(m["device"], extra[m["device"]]), machines))
    t_all = time.time() - t0
    n_msgs = sum(len(v) for v in plan.values()) + sum(len(v) for v in extra.values())
    ev.say(
        f"* {name}: sent {n_msgs} messages from {len(machines)} devices with {threads} threads in {t_all:.1f} s "
        f"(main batch {t_main:.1f} s) → client rate {n_msgs / t_all:.1f} msg/s; HTTP errors: {len(errors)}"
    )
    watcher.join(timeout=120)
    watcher.stop.set()
    lat_latest = [
        watcher.seen[m["machine_id"]] - sent[(m["device"], int(expected_latest[m["machine_id"]].timestamp()))]
        for m in machines
        if m["machine_id"] in watcher.seen
    ]
    ev.say(
        f"* {name}: machine_latest_position showed the newest fix for {len(watcher.seen)}/{len(machines)} machines; "
        f"latency send→latest p50 {pct(lat_latest, 50):.2f} s, p95 {pct(lat_latest, 95):.2f} s, "
        f"max {max(lat_latest, default=float('nan')):.2f} s (0.25 s sampling)"
    )
    ev.check(f"{name}: no HTTP errors", not errors, f"{len(errors)} errors {errors[:3]}")
    ev.check(
        f"{name}: every machine's latest = newest fix",
        len(watcher.seen) == len(machines),
        f"{len(watcher.seen)}/{len(machines)}",
    )
    return sent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fixes", type=int, default=30)
    p.add_argument("--threads", type=int, default=20)
    a = p.parse_args()
    guard_local()
    state = load_state()
    tid, machines = state["tenant_id"], state["machines"]
    ev = Evidence("telemetry-load", "Telemetry load check (Traccar OsmAnd + direct gateway path)")
    gateway_key = ENV["ASSETA_TRACCAR_GATEWAY_KEY"]
    now = now_utc().replace(microsecond=0)
    since = now - timedelta(minutes=80)
    ev.say(
        f"Throwaway tenant `{tid}` (Drill 7E {state['tag']}), {len(machines)} machines each with an enrolled, "
        f"primary-assigned simulated OsmAnd tracker. {a.fixes} fixes per device per phase."
    )
    ev.say("")
    ev.say("### Results")
    ev.say("")
    base_ing = sql("SELECT count(*) FROM tracker_ingestion_event WHERE tenant_id = %s", (tid,))[0][0]
    pre = set(stored(tid, since))  # positions from earlier runs on this tenant are excluded from the comparison
    if pre:
        ev.say(f"({len(pre)} positions from earlier runs in the window are excluded from the comparison.)")

    a_start = now - timedelta(minutes=12 + a.fixes)
    plan_a = {m["device"]: track(i, a_start, a.fixes, 60) for i, m in enumerate(machines)}
    late_start = now - timedelta(minutes=75)
    late = {m["device"]: track(i, late_start, 3, 30) for i, m in enumerate(machines)}
    dups = {m["device"]: plan_a[m["device"]][:2] for m in machines}
    extra = {d: late[d] + dups[d] for d in late}
    lag = LagSampler(tid)
    lag.start()
    t_a0 = time.time()
    sent_a = run_phase(
        ev, "Phase A (device → Traccar 6.10.0 → Asseta)", machines, plan_a, extra, "osmand", a.threads, tid, gateway_key
    )
    expected_a = {(d, int(f.time.timestamp())) for d, fs in plan_a.items() for f in fs} | {
        (d, int(f.time.timestamp())) for d, fs in late.items() for f in fs
    }
    wait_until(lambda: len((set(stored(tid, since)) - pre) & expected_a) == len(expected_a - pre), 120, 1.0)

    b_start = now - timedelta(seconds=15 * a.fixes + 60)
    plan_b = {m["device"]: track(i, b_start, a.fixes, 15) for i, m in enumerate(machines)}
    sent_b = run_phase(
        ev, "Phase B (direct gateway-authenticated POST)", machines, plan_b, {}, "direct", a.threads, tid, gateway_key
    )
    expected_b = {(d, int(f.time.timestamp())) for d, fs in plan_b.items() for f in fs}
    expected = expected_a | expected_b
    t_settle = wait_until(lambda: len((set(stored(tid, since)) - pre) & expected) == len(expected - pre), 180, 1.0)
    drained = wait_until(lambda: outbox_pending(tid) == 0 and (kafka_lag("asseta-timeline") or 0) == 0, 1500, 2.0)
    t_end = time.time()
    lag.stop.set()
    lag.join(timeout=10)

    got = {k: v for k, v in stored(tid, since).items() if k not in pre}
    expected_a, expected_b = expected_a - pre, expected_b - pre
    expected = expected_a | expected_b
    missing, unexpected = expected - set(got), set(got) - expected
    lat_a = [(got[k][0].timestamp() - sent_a[k]) for k in expected_a if k in got and k in sent_a]
    lat_b = [(got[k][0].timestamp() - sent_b[k]) for k in expected_b if k in got and k in sent_b]
    rows = sql(
        "SELECT status, coalesce(quarantine_reason, ''), count(*), min(received_at), max(received_at) "
        "FROM tracker_ingestion_event WHERE tenant_id = %s AND received_at >= to_timestamp(%s) GROUP BY 1, 2",
        (tid, t_a0 - 5),
    )
    late_flags = sum(1 for k in late_keys(late) if k in got and got[k][1])
    dup_rows = sql(
        "SELECT count(*) FROM (SELECT tracker_id, event_time FROM machine_position_event WHERE tenant_id = %s "
        "GROUP BY 1, 2 HAVING count(*) > 1) d",
        (tid,),
    )[0][0]
    peak = max((s[1] or 0 for s in lag.samples), default=0)
    peak_outbox = max((s[2] for s in lag.samples), default=0)
    ob = sql(
        "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM published_at - created_at)), "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM published_at - created_at)), count(*) "
        "FROM outbox_event WHERE tenant_id = %s AND created_at >= to_timestamp(%s) AND published_at IS NOT NULL",
        (tid, t_a0 - 5),
    )[0]

    def ingest_rate(phase_keys: set[tuple[str, int]]) -> str:
        times = sorted(got[k][0].timestamp() for k in phase_keys if k in got)
        span = times[-1] - times[0] if len(times) > 1 else float("nan")
        return f"{len(times) / span:.1f} positions/s over {span:.1f} s"

    ev.say(f"* Server ingest rate: Phase A {ingest_rate(expected_a)}; Phase B {ingest_rate(expected_b)}")
    ev.say(
        f"* Latency client send → stored position (received_at): Phase A (via Traccar) p50 {pct(lat_a, 50):.3f} s, "
        f"p95 {pct(lat_a, 95):.3f} s, max {max(lat_a, default=float('nan')):.3f} s; Phase B (direct) "
        f"p50 {pct(lat_b, 50):.3f} s, p95 {pct(lat_b, 95):.3f} s, max {max(lat_b, default=float('nan')):.3f} s"
    )
    ev.say(
        f"* Timeline worker: peak Kafka lag {peak} messages, peak tenant outbox backlog {peak_outbox}; outbox + "
        f"timeline lag drained {drained:.1f} s after all positions were stored (≈ "
        f"{len(expected) / (t_end - t_a0):.1f} messages/s end-to-end incl. ingestion; single "
        "partition)"
        if drained is not None
        else "* Timeline worker did NOT drain within 1500 s"
    )
    ev.say(
        f"* Outbox relay delay (created → published) for this run's {ob[2]} events: p50 {float(ob[0] or 0):.2f} s, "
        f"p95 {float(ob[1] or 0):.2f} s"
    )
    ev.say(
        f"* Stored positions: {len(got)} (expected {len(expected)}); all stored within "
        f"{t_settle if t_settle is not None else 'n/a'} s of the last send; run wall time {t_end - t_a0:.0f} s"
    )
    ev.say("")
    ev.table(
        ["ingestion status", "reason", "count", "first received", "last received"],
        [
            [r[0], r[1] or "-", r[2], r[3].isoformat(timespec="seconds"), r[4].isoformat(timespec="seconds")]
            for r in rows
        ],
    )
    ing_total = sql("SELECT count(*) FROM tracker_ingestion_event WHERE tenant_id = %s", (tid,))[0][0] - base_ing
    dup_count = sum(r[2] for r in rows if r[0] == "DUPLICATE")
    quarantined = sum(r[2] for r in rows if r[0] == "QUARANTINED")
    ev.check("no lost positions (sent set ⊆ stored set)", not missing, f"missing {len(missing)}")
    ev.check("no unexpected positions", not unexpected, f"unexpected {len(unexpected)}")
    ev.check("no duplicate stored positions (tracker, event_time)", dup_rows == 0, f"{dup_rows} duplicated keys")
    ev.check(
        "re-sent fixes recorded as DUPLICATE",
        dup_count >= len(machines) * 2,
        f"{dup_count} DUPLICATE ingestion events for {len(machines) * 2} re-sent fixes",
    )
    latest_rows = sql(
        "SELECT t.external_id, l.event_time FROM machine_latest_position l JOIN tracker t "
        "ON t.id = l.tracker_id WHERE l.tenant_id = %s",
        (tid,),
    )
    late_as_latest = sum(1 for d, et in latest_rows if (d, int(et.timestamp())) in late_keys(late))
    ev.say(
        f"* Late (75 min old, buffered) fixes: all {len(late_keys(late))} stored at their event time; {late_flags} "
        "flagged is_late (= older than the machine's latest at receipt; via Traccar's async forwarding a late fix can "
        "reach Asseta before that device's newer fixes, and is then correctly not flagged)"
    )
    ev.check("late fixes never displaced a newer latest position", late_as_latest == 0, f"{late_as_latest}")
    ev.check("nothing quarantined", quarantined == 0, f"{quarantined}")
    ev.check(
        "every received message has an ingestion record",
        ing_total >= len(expected) + dup_count - 0,
        f"{ing_total} ingestion events",
    )
    ev.check(
        "timeline worker caught up (lag 0, outbox drained) within 25 min",
        drained is not None,
        f"{drained:.1f} s" if drained is not None else "timeout",
    )
    ev.check("p95 send→stored latency (direct) < 2 s", pct(lat_b, 95) < 2.0, f"{pct(lat_b, 95):.3f} s")
    ev.write(
        not_simulated=[
            "Real cellular links, real tracker firmware buffering and Traccar's binary protocols (OsmAnd HTTP only).",
            "Multiple API replicas / Kafka partitions > 1 / multi-node Postgres: one container each on one laptop.",
            "Sustained hours-long load; this is a burst of ~6 300 positions for 100 machines.",
            "Latency is measured on one host clock (client and server share it); Traccar → API forwarding is async.",
        ],
        commands=[
            "cd backend",
            "uv run python ../scripts/drills/drill_tenant.py create --machines 100",
            f"uv run python ../scripts/drills/telemetry_load.py --fixes {a.fixes} --threads {a.threads}",
        ],
    )


def late_keys(late: dict[str, list[Fix]]) -> set[tuple[str, int]]:
    return {(d, int(f.time.timestamp())) for d, fs in late.items() for f in fs}


if __name__ == "__main__":
    main()
