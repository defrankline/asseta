# Offline sync protocol (v1)

Field devices (Android/iOS Supervisor apps) work fully offline and reconcile through `/api/v1/sync`. The server owns
final financial, billing and authorization state; the device owns original capture evidence (§6).

## Endpoints
| Call | Purpose |
|---|---|
| `POST /sync/devices` | Register the device for the signed-in user → device session, `offline_grant_until` |
| `GET /sync/bootstrap` (`X-Device-Id`) | Assigned jobs, machines, sites, customers, contracts, own staff record, **policy snapshots**, `cursor` |
| `GET /sync/changes?cursor=N` | Delta since cursor (+ refreshed snapshots); `has_more` paging |
| `POST /sync/push` | Batch of operations `{id, op_type, created_at_device, depends_on[], payload}` + `device_now` |
| `POST /sync/blobs` → `PUT …/chunks/{i}` → `POST …/complete` | Resumable, SHA-256-verified evidence upload |
| `GET /tenant/devices`, `POST /tenant/devices/{id}/revoke` | Owner device administration |

Operation types (v1): `METER_CAPTURE`, `JOB_ACTIVITY`, `JOB_ACKNOWLEDGEMENT`, `JOB_TRANSITION` (START/COMPLETE).
Gate 5 adds expense, collection, cash handover and fuel operations through the same dispatcher.

Accountability (DEC-030) operations, each announced by a capability in `bootstrap`/`changes` (`capabilities[]`) so a
client only queues an op the server understands:

| Op type | Capability | Payload (idempotency) | Conflict codes |
|---|---|---|---|
| `CASH_TRANSFER` | `OP_CASH_TRANSFER` | `CashTransferIn` (`client_id` required) | `DUPLICATE_TRANSFER` (rejected) |
| `CASH_TRANSFER_ACKNOWLEDGEMENT` | `OP_CASH_TRANSFER` | `{transfer_id, acknowledged, amount_received?, note?}` | `TRANSFER_ALREADY_DECIDED` |
| `CASH_FLOAT_ACKNOWLEDGEMENT` | `OP_CASH_TRANSFER` | `{entry_id, acknowledged, amount_received?, note?}` (op id) | `FLOAT_ALREADY_ACKNOWLEDGED` |
| `CASH_RETENTION_REQUEST` | `OP_CASH_RETENTION_REQUEST` | `CashRetentionIn` (`client_id` required; `staff_member_id` defaults to the caller) | `RETENTION_NOT_ALLOWED` (tenant policy `cash.retention_allowed` off), `DUPLICATE_RETENTION` |
| `HOURS_PURCHASE` | `OP_HOURS_PURCHASE` | `HoursPurchaseIn` (op id = client id) + `evidence_upload_ids` | `NO_AVAILABLE_HOURS` … |
| `HOURS_TRANSFER_REQUEST` | `OP_HOURS_TRANSFER_REQUEST` | `TransferIn` (op id = client id) | `EXCEEDS_REMAINING_HOURS` |
| `METER_BASELINE` / `METER_CORRECTION` | `OP_METER_BASELINE` / `OP_METER_CORRECTION` | `BaselineIn` / `CorrectionIn` | `BASELINE_PENDING`, `CORRECTION_PENDING` |

`CASH_RETENTION_REQUEST` needs `tenant.collection.record`; a retry with the same `client_id` returns the original
request (one effect). The result entity is the `CashRetentionDto` (status `PENDING` until someone other than the
requester decides it).

Tenant capability switches: a protocol capability that belongs to a tenant capability is **not announced** while the
tenant has it switched off (`/me` `disabled_capabilities` names the same codes), and such an operation still queued on
a device is refused as `CONFLICT` (kept for review, never applied):

| Tenant capability (policy `enabled`) | Protocol capabilities withheld | Ops refused (conflict code) |
|---|---|---|
| `ENGINE_HOURS` | `OP_METER_BASELINE`, `OP_METER_CORRECTION`, `METER_DAILY_READING` | `METER_BASELINE`, `METER_CORRECTION`, `METER_CAPTURE` of kind `DAILY` (`ENGINE_HOURS_DISABLED`) |
| `CASH_CUSTODY` | `OP_CASH_TRANSFER`, `OP_CASH_RETENTION_REQUEST` | `CASH_TRANSFER`, `CASH_TRANSFER_ACKNOWLEDGEMENT`, `CASH_FLOAT_ACKNOWLEDGEMENT`, `CASH_RETENTION_REQUEST` (`CASH_CUSTODY_DISABLED`) |
| `CUSTOMER_HOURS` | `OP_HOURS_PURCHASE`, `OP_HOURS_TRANSFER_REQUEST` | refused by the hours services (`HOURS_DISABLED`, rejected) |

Job meter readings (OPENING/CLOSING), cash collections and remittances are never withheld.

## Guarantees
* **Idempotency:** the device-generated operation id is the key (`client_operation`). A retry returns the stored
  outcome (`DUPLICATE`); the same id with different content is `OPERATION_ID_REUSED`. Domain ids (capture id,
  activity/ack `client_id`) are also device-generated, so even a direct API retry cannot double-apply.
* **Dependency order:** an operation whose `depends_on` are not yet `ACKED` returns `DEFERRED` and is not stored;
  the device re-sends it. (Upload evidence before the capture that references it.)
* **No silent last-write-wins:** state conflicts (e.g. START on a job cancelled server-side) return `CONFLICT`
  with `server_state`; validation failures return `REJECTED` with a code. Both are stored for audit and shown to the
  user; the device keeps its original evidence.
* **Synced only after ACK:** devices mark an operation synced only on `ACKED`/`DUPLICATE`; `DEFERRED`, network errors
  and 5xx keep it pending with exponential backoff.
* **Suspension:** for a READ_ONLY tenant, pushes are `QUARANTINED` (stored, not applied) and are applied when the
  device re-sends them after reactivation — never discarded.
* **Policy snapshots:** captures carry `policy_version_ids` of the snapshot the device enforced offline; the server
  validates against that snapshot and records both stamps. Snapshots expire (`DEVICE_SYNC.snapshot_validity_hours`).
  The snapshot must have been issued to the sending device and be valid at `captured_at`. If not, the capture is
  still accepted, but held `PROVISIONAL` with a `POLICY_SNAPSHOT_UNVERIFIED` exception for review (security.md F-8).
* **Clock:** every push reports `device_now`; the server returns `clock_offset_s` and `clock_skew_alert`; captures
  record device time and server receive time; future-dated captures raise `CLOCK_SKEW`.
* **Delta pull:** global `sync_revision` sequence bumped by trigger; each pull re-reads a 500-revision lookback so
  late-committing transactions are never missed (clients upsert by id).

## Failure matrix
| Failure | Behaviour | Evidence |
|---|---|---|
| Network flap / lost response | Retry whole batch → `DUPLICATE` per op, one effect | `test_sync.py::…exactly_once` |
| Out-of-order delivery | Children `DEFERRED` until parents `ACKED` | same |
| Long offline period | Captures validated against the device snapshot; offline grant bounded by `offline_grant_hours`; late GPS attaches by event time | `test_jobs_meter.py`, `test_trackers_ingestion.py` |
| Lost / stolen phone | Owner revokes → `DEVICE_REVOKED` + `WIPE_LOCAL_DATA`; re-registration refused | `test_sync.py::…revocation` |
| Expired/revoked device session | Same as above; Keycloak token revocation also applies | — |
| Tenant data reset before go-live ([runbook §11](operating-runbook.md#11-reset-a-tenants-data-before-go-live)) | Every session revoked with the reset reason → `DEVICE_REVOKED` + `WIPE_LOCAL_DATA`; the phone may register again, and a re-registered session that has not bootstrapped is told to wipe on its first pull/upload/push, so erased data never comes back | `test_reset_tenant_data.py` |
| Suspended subscription | `QUARANTINED`, applied after reactivation | `test_sync.py::…quarantine…` |
| Job reassigned/cancelled/machine changed | `CONFLICT` with `server_state`; delta pull delivers the new job state | `test_sync.py` |
| GPS disabled / denied | Capture records the failed attempt; SOFT → PROVISIONAL + exception, HARD → REJECTED | `test_jobs_meter.py` |
| Kafka down | Sync unaffected (outbox queues events) | `test_kafka_live.py::…retry` |
| Object store down | Blob completion returns 503; chunks stay staged; device retries complete | adapter raises `DependencyUnavailable` |
| Upload interrupted / corrupted | Resume by missing chunk indexes; checksum mismatch restarts upload | `test_sync.py::…resumable…` |
| Tracker backlog (buffered GPS) | Accepted by event time within replay window; timeline replayed | `test_trackers_ingestion.py` |

## Known trade-offs
* Chunks are staged in PostgreSQL (≤10 MB evidence objects); move to S3 multipart if object sizes grow.
* Delta pull returns supervisor-relevant entities only; owners use the Owner app's read-only snapshots (Gate 7).
