# Drill: Queue backlog recovery (timeline + notification workers stopped during a burst)

* **Result:** PASS
* **Run:** 2026-10-22T18:40:29+00:00 → 2026-10-22T18:43:53+00:00 (205 s)
* **Target:** local docker compose stack (single host, single broker/node); script `scripts/drills/queue_backlog.py`

## Commands

```bash
cd backend
uv run python ../scripts/drills/queue_backlog.py --positions 2000 --jobs 60
```

## Log

Throwaway tenant `631e2fc6-da50-4fec-8b72-cda8802dd00a`; burst of 2000 positions over 100 machines and 60 job submissions while timeline-worker, notification-worker are stopped.

* Baseline lag {'asseta-timeline': 0, 'asseta-notification': 0, 'asseta-intelligence': 0}
* Burst: job.create 201: 60, job.submit 200: 60, position 202: 2000 in 25.5 s; tenant outbox pending 0; backlog (consumer lag) {'asseta-timeline': 2000, 'asseta-notification': 2060}
| consumer group | backlog (messages) | catch-up (s) | ≈ msg/s |
|---|---|---|---|
| asseta-notification | 2060 | 12 | 169.0 |
| asseta-timeline | 2000 | 145 | 13.8 |

* Recovery total 161 s; effects {'positions_acked': 2000, 'positions_lost': 0, 'positions_duplicated': 0, 'jobs_submitted': 60, 'job_events': 60, 'job_events_without_notification': 0, 'duplicate_notifications': 0, 'outbox_unpublished': 0}; final lag {'asseta-timeline': 0, 'asseta-notification': 0, 'asseta-intelligence': 0}

## Checks

| Check | Result | Detail |
|---|---|---|
| backlog built while workers stopped | PASS | {'asseta-timeline': 2000, 'asseta-notification': 2060} |
| notification worker caught up | PASS | 12.18731774999469 |
| timeline worker caught up | PASS | 144.61345679200895 |
| API answered every burst request | PASS | 0 failures |
| no acknowledged position lost or duplicated | PASS | {'positions_acked': 2000, 'positions_lost': 0, 'positions_duplicated': 0, 'jobs_submitted': 60, 'job_events': 60, 'job_events_without_notification': 0, 'duplicate_notifications': 0, 'outbox_unpublished': 0} |
| every job event notified exactly once | PASS | {'positions_acked': 2000, 'positions_lost': 0, 'positions_duplicated': 0, 'jobs_submitted': 60, 'job_events': 60, 'job_events_without_notification': 0, 'duplicate_notifications': 0, 'outbox_unpublished': 0} |
| final readiness ok | PASS |  |

## Not simulated

* Multi-hour backlogs / topic retention expiry (default 7 days; a worker down longer than retention would lose its backlog — the outbox keeps every event and can be re-published).
* Scaling consumers horizontally: topics are auto-created with 1 partition, so one consumer per group.
* Dead-letter handling: a poison message is retried forever (not committed) — not exercised here.
