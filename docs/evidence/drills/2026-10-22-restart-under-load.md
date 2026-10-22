# Drill: API and worker restarts under activity, WebSocket reconnect

* **Result:** PASS
* **Run:** 2026-10-22T18:32:53+00:00 → 2026-10-22T18:36:21+00:00 (208 s)
* **Target:** local docker compose stack (single host, single broker/node); script `scripts/drills/restart_under_load.py`

## Commands

```bash
cd backend
uv run python ../scripts/drills/restart_under_load.py
```

## Log

Throwaway tenant `631e2fc6-da50-4fec-8b72-cda8802dd00a`; activity = 1 position / 0.5 s + job create+submit / 2 s; 1 WebSocket client.

| service | restart (s) | API ready after (s) | WS reconnect (s) | entity.changed msgs in next 15 s | status |
|---|---|---|---|---|---|
| api | 2.1 | 3.8 | 6.8 | 51 | Up 19 seconds (healthy) |
| outbox-relay | 0.7 | - | - | 65 | Up 15 seconds |
| timeline-worker | 1.4 | - | - | 60 | Up 15 seconds |
| notification-worker | 1.5 | - | - | 67 | Up 15 seconds |
| intelligence-worker | 1.8 | - | - | 63 | Up 15 seconds |
| connectivity-worker | 0.8 | - | - | 64 | Up 15 seconds |
| notification-scheduler | 2.0 | - | - | 68 | Up 15 seconds |
| billing-scheduler | 1.0 | - | - | 67 | Up 15 seconds |
| timeline-worker (SIGKILL) | 4.0 | - | - | 38 | Up 15 seconds |

* Activity: job RemoteProtocolError: 3, job.create 201: 78, job.submit 200: 78, position 202: 316, position RemoteProtocolError: 11
* Activity call failures (expected only while the API process restarts): 14; WebSocket disconnects 2, auth_ok 2, entity.changed received 672
* Effects: {'positions_acked': 316, 'positions_lost': 0, 'positions_duplicated': 0, 'jobs_submitted': 78, 'job_events': 78, 'job_events_without_notification': 0, 'duplicate_notifications': 0, 'outbox_unpublished': 0}

## Checks

| Check | Result | Detail |
|---|---|---|
| WebSocket client authenticated (auth_ok) | PASS |  |
| api: running after restart | PASS | Up 19 seconds (healthy) |
| api: healthy again | PASS | 3.8257943330099806 |
| WebSocket client reconnected after api restart | PASS | 6.789471864700317 |
| outbox-relay: running after restart | PASS | Up 15 seconds |
| timeline-worker: running after restart | PASS | Up 15 seconds |
| notification-worker: running after restart | PASS | Up 15 seconds |
| live entity.changed messages resume after notification-worker restart | PASS | 67 in 15 s |
| intelligence-worker: running after restart | PASS | Up 15 seconds |
| connectivity-worker: running after restart | PASS | Up 15 seconds |
| notification-scheduler: running after restart | PASS | Up 15 seconds |
| billing-scheduler: running after restart | PASS | Up 15 seconds |
| timeline-worker (SIGKILL): running after restart | PASS | Up 15 seconds |
| outbox drained and consumer lag 0 after all restarts | PASS | 35.257973291998496 s; {'asseta-timeline': 0, 'asseta-notification': 0, 'asseta-intelligence': 0} |
| no acknowledged position lost / duplicated | PASS | lost 0, dup 0 |
| no lost outbox events: every submitted job produced its event and notification | PASS | 78/78 events, 0 without notification |
| no duplicate notifications | PASS | 0 |
| final readiness ok | PASS | HTTP 200 ok (database=ok, redis=ok, kafka=ok, keycloak=ok, object_store=ok) |
| all compose services up | PASS | api Up 3 minutes (healthy); billing-scheduler Up About a minute; connectivity-worker Up About a minute; intelligence-worker Up 2 minutes; kafka Up 4 minutes; keycloak Up 5 hours (healthy); mailpit Up About an hour (healthy); minio Up 34 hours; mlflow Up 7 hours (healthy); notification-scheduler Up About a minute; notification-worker Up 2 minutes; outbox-relay Up 2 minutes; postgres Up 34 hours (healthy); redis Up 36 minutes; timeline-worker Up 57 seconds; traccar Up 43 minutes; web Up About an hour |

## Not simulated

* Multiple API replicas behind a load balancer (zero-downtime rolling restart); one API container here, so requests during its restart fail and the client/Traccar retries.
* Host reboot / Docker daemon restart; OOM kills other than the explicit SIGKILL of the timeline worker.
* Mobile clients: their outbox retry is covered by the sync tests; only a WebSocket client is scripted.
