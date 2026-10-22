# Drill: Kafka broker outage and recovery under activity

* **Result:** PASS
* **Run:** 2026-10-22T18:30:17+00:00 → 2026-10-22T18:32:45+00:00 (148 s)
* **Target:** local docker compose stack (single host, single broker/node); script `scripts/drills/kafka_outage.py`

## Commands

```bash
cd backend
uv run python ../scripts/drills/kafka_outage.py --outage 60
```

## Log

Throwaway tenant `631e2fc6-da50-4fec-8b72-cda8802dd00a`; activity = 1 position / 0.5 s + 1 job create+submit / 2 s; outage 60 s.

* Baseline: HTTP 200 ok (database=ok, redis=ok, kafka=ok, keycloak=ok, object_store=ok); consumer lag {'asseta-timeline': 0, 'asseta-notification': 0, 'asseta-intelligence': 0}; tenant outbox pending 0
* `docker compose stop kafka` took 1.4 s (activity continues)
| s after stop | readiness | tenant outbox pending |
|---|---|---|
| 17 | HTTP 200 degraded (database=ok, redis=ok, kafka=down, keycloak=ok, object_store=ok) | 43 |
| 32 | HTTP 200 degraded (database=ok, redis=ok, kafka=down, keycloak=ok, object_store=ok) | 79 |
| 47 | HTTP 200 degraded (database=ok, redis=ok, kafka=down, keycloak=ok, object_store=ok) | 114 |
| 62 | HTTP 200 degraded (database=ok, redis=ok, kafka=down, keycloak=ok, object_store=ok) | 150 |

* `docker compose start kafka`: broker answering after 4.546429708003416 s; readiness kafka=ok after 0.12554229200759437 s; tenant outbox drained 9.3 s after start
* All consumer groups ['asseta-timeline', 'asseta-notification', 'asseta-intelligence'] at lag 0 and outbox empty 56 s after Kafka start (activity stopped 15 s after the outbox drained)
* Activity: job.create 201: 52, job.submit 200: 52, position 202: 211
* Outbox: 136 tenant events needed retries (max attempts 3); events published in the window 515; Kafka offset growth 651 → broker-level redeliveries 136
* Effects: {'positions_acked': 211, 'positions_lost': 0, 'positions_duplicated': 0, 'jobs_submitted': 52, 'job_events': 52, 'job_events_without_notification': 0, 'duplicate_notifications': 0, 'outbox_unpublished': 0}

## Checks

| Check | Result | Detail |
|---|---|---|
| API stayed up during the outage (all activity calls 2xx) | PASS | 0 failures [] |
| readiness reports kafka down while the broker is stopped (degraded, HTTP 200) | PASS | HTTP 200 degraded (database=ok, redis=ok, kafka=down, keycloak=ok, object_store=ok) |
| domain events accumulate in the outbox during the outage | PASS | peak 150 |
| relay drained the outbox after recovery | PASS | 9.305909958988195 |
| consumers caught up (lag 0 for timeline, notification, intelligence) | PASS | {'asseta-timeline': 0, 'asseta-notification': 0, 'asseta-intelligence': 0} |
| no acknowledged position lost | PASS | 0 |
| no position stored twice | PASS | 0 |
| every submitted job produced its JobPendingApproval event | PASS | 52/52 |
| every JobPendingApproval event notified (consumer caught up) | PASS | 0 |
| no duplicate notifications despite at-least-once delivery | PASS | 0 |
| final readiness ok | PASS | HTTP 200 ok (database=ok, redis=ok, kafka=ok, keycloak=ok, object_store=ok) |

## Not simulated

* Single broker (RF 1): no partition leader election, ISR shrink or multi-broker partial outage.
* Network partition between API and broker (the broker process was stopped cleanly); no data-dir loss.
* Consumer crash mid-batch is covered by the API/worker restart drill, not here.
