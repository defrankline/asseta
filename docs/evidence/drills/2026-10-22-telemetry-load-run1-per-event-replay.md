# Drill: Telemetry load check (Traccar OsmAnd + direct gateway path)

> **Superseded run, kept for the record.** This run (after the ingestion-lock fixes, before the timeline-worker coalescing fix) passed, but the timeline worker needed 824 s to drain 5 894 messages (≈ 7/s, one replay per message). After batching + per-machine coalescing the same load drained in 28 s — see [2026-10-22-telemetry-load.md](2026-10-22-telemetry-load.md). Two earlier attempts the same day hung the API and wrote no evidence file; they are described in [README.md](README.md).

* **Result:** PASS
* **Run:** 2026-10-22T18:09:32+00:00 → 2026-10-22T18:25:13+00:00 (941 s)
* **Target:** local docker compose stack (single host, single broker/node); script `scripts/drills/telemetry_load.py`

## Commands

```bash
cd backend
uv run python ../scripts/drills/drill_tenant.py create --machines 100
uv run python ../scripts/drills/telemetry_load.py --fixes 30 --threads 20
```

## Log

Throwaway tenant `631e2fc6-da50-4fec-8b72-cda8802dd00a` (Drill 7E 97b194), 100 machines each with an enrolled, primary-assigned simulated OsmAnd tracker. 30 fixes per device per phase.

### Results

(6047 positions from earlier runs in the window are excluded from the comparison.)
* Phase A (device → Traccar 6.10.0 → Asseta): sent 3500 messages from 100 devices with 20 threads in 2.0 s (main batch 1.7 s) → client rate 1779.3 msg/s; HTTP errors: 0
* Phase A (device → Traccar 6.10.0 → Asseta): machine_latest_position showed the newest fix for 100/100 machines; latency send→latest p50 -1.06 s, p95 -0.35 s, max -0.34 s (0.25 s sampling)
* Phase B (direct gateway-authenticated POST): sent 3000 messages from 100 devices with 20 threads in 51.5 s (main batch 51.5 s) → client rate 58.2 msg/s; HTTP errors: 0
* Phase B (direct gateway-authenticated POST): machine_latest_position showed the newest fix for 100/100 machines; latency send→latest p50 0.43 s, p95 0.58 s, max 0.62 s (0.25 s sampling)
* Server ingest rate: Phase A 78.3 positions/s over 42.1 s; Phase B 58.3 positions/s over 51.4 s
* Latency client send → stored position (received_at): Phase A (via Traccar) p50 24.005 s, p95 40.434 s, max 45.770 s; Phase B (direct) p50 0.016 s, p95 0.045 s, max 0.124 s
* Timeline worker: peak Kafka lag 5894 messages, peak tenant outbox backlog 99; outbox + timeline lag drained 823.8 s after all positions were stored (≈ 6.7 messages/s end-to-end; one replay per message before the coalescing fix; single partition)
* Outbox relay delay (created → published) for this run's 8128 events: p50 0.53 s, p95 0.96 s
* Stored positions: 6300 (expected 6300); all stored within 0.047113166001508944 s of the last send; run wall time 940 s

| ingestion status | reason | count | first received | last received |
|---|---|---|---|---|
| ACCEPTED | - | 6300 | 2026-10-22T18:09:37+00:00 | 2026-10-22T18:11:28+00:00 |
| DUPLICATE | - | 200 | 2026-10-22T18:09:37+00:00 | 2026-10-22T18:10:18+00:00 |

* Late (75 min old, buffered) fixes: all 300 stored at their event time; 300 flagged is_late (older than the machine's latest *at receipt*; through Traccar's async forwarding some late fixes reach Asseta before that device's newer fixes, so the flag is correctly unset)

## Checks

| Check | Result | Detail |
|---|---|---|
| Phase A (device → Traccar 6.10.0 → Asseta): no HTTP errors | PASS | 0 errors [] |
| Phase A (device → Traccar 6.10.0 → Asseta): every machine's latest = newest fix | PASS | 100/100 |
| Phase B (direct gateway-authenticated POST): no HTTP errors | PASS | 0 errors [] |
| Phase B (direct gateway-authenticated POST): every machine's latest = newest fix | PASS | 100/100 |
| no lost positions (sent set ⊆ stored set) | PASS | missing 0 |
| no unexpected positions | PASS | unexpected 0 |
| no duplicate stored positions (tracker, event_time) | PASS | 0 duplicated keys |
| re-sent fixes recorded as DUPLICATE | PASS | 200 DUPLICATE ingestion events for 200 re-sent fixes |
| late fixes never displaced a newer latest position | PASS | 0 |
| nothing quarantined | PASS | 0 |
| every received message has an ingestion record | PASS | 6500 ingestion events |
| timeline worker caught up (lag 0, outbox drained) within 25 min | PASS | 823.8 s |
| p95 send→stored latency (direct) < 2 s | PASS | 0.045 s |

## Not simulated

* Real cellular links, real tracker firmware buffering and Traccar's binary protocols (OsmAnd HTTP only).
* Multiple API replicas / Kafka partitions > 1 / multi-node Postgres: one container each on one laptop.
* Sustained hours-long load; this is a burst of ~6 300 positions for 100 machines.
* Latency is measured on one host clock (client and server share it); Traccar → API forwarding is async.
