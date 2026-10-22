# Drill: Telemetry load check (Traccar OsmAnd + direct gateway path)

* **Result:** PASS
* **Run:** 2026-10-22T18:27:49+00:00 → 2026-10-22T18:30:00+00:00 (131 s)
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

(12012 positions from earlier runs in the window are excluded from the comparison.)
* Phase A (device → Traccar 6.10.0 → Asseta): sent 3500 messages from 100 devices with 20 threads in 1.8 s (main batch 1.5 s) → client rate 1946.9 msg/s; HTTP errors: 0
* Phase A (device → Traccar 6.10.0 → Asseta): machine_latest_position showed the newest fix for 100/100 machines; latency send→latest p50 35.85 s, p95 52.05 s, max 53.88 s (0.25 s sampling)
* Phase B (direct gateway-authenticated POST): sent 3000 messages from 100 devices with 20 threads in 45.3 s (main batch 45.3 s) → client rate 66.2 msg/s; HTTP errors: 0
* Phase B (direct gateway-authenticated POST): machine_latest_position showed the newest fix for 100/100 machines; latency send→latest p50 0.40 s, p95 0.54 s, max 0.60 s (0.25 s sampling)
* Server ingest rate: Phase A 106.8 positions/s over 30.9 s; Phase B 66.3 positions/s over 45.3 s
* Latency client send → stored position (received_at): Phase A (via Traccar) p50 23.490 s, p95 30.975 s, max 34.283 s; Phase B (direct) p50 0.013 s, p95 0.039 s, max 0.196 s
* Timeline worker: peak Kafka lag 3528 messages, peak tenant outbox backlog 107; outbox + timeline lag drained 28.0 s after all positions were stored (≈ 48.5 messages/s end-to-end incl. ingestion; single partition; batched replays coalesced per machine)
* Outbox relay delay (created → published) for this run's 8502 events: p50 0.49 s, p95 0.96 s
* Stored positions: 6300 (expected 6300); all stored within 0.08123604199499823 s of the last send; run wall time 130 s

| ingestion status | reason | count | first received | last received |
|---|---|---|---|---|
| DUPLICATE | - | 200 | 2026-10-22T18:27:54+00:00 | 2026-10-22T18:28:25+00:00 |
| ACCEPTED | - | 6300 | 2026-10-22T18:27:54+00:00 | 2026-10-22T18:29:31+00:00 |

* Late (75 min old, buffered) fixes: all 300 stored at their event time; 300 flagged is_late (= older than the machine's latest at receipt; via Traccar's async forwarding a late fix can reach Asseta before that device's newer fixes, and is then correctly not flagged)

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
| timeline worker caught up (lag 0, outbox drained) within 25 min | PASS | 28.0 s |
| p95 send→stored latency (direct) < 2 s | PASS | 0.039 s |

## Not simulated

* Real cellular links, real tracker firmware buffering and Traccar's binary protocols (OsmAnd HTTP only).
* Multiple API replicas / Kafka partitions > 1 / multi-node Postgres: one container each on one laptop.
* Sustained hours-long load; this is a burst of ~6 300 positions for 100 machines.
* Latency is measured on one host clock (client and server share it); Traccar → API forwarding is async.
