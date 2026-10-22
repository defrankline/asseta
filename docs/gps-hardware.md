# GPS / telematics hardware and commissioning guide

**Status:** the software path is verified end to end with a *simulated* device through a real Traccar 6.10.0 gateway
(`backend/scripts/compose_smoke.py` → `TELEMETRY OK`; track.md evidence log 2026-10-21). **Physical device
commissioning: `HARDWARE_VALIDATION_BLOCKED`** — it needs a customer-provided supported tracker, SIM/data plan and
installation (track.md EXT-02 / EXT-02a). See [What HARDWARE_VALIDATION_BLOCKED means](#what-hardware_validation_blocked-means).

## Architecture

```
tracker --(vendor protocol)--> Traccar gateway --(JSON forward + X-Asseta-Gateway-Key)--> POST /api/v1/telemetry/traccar
   -> TraccarAdapter -> TelemetryObservation -> IngestionService (auth, quarantine, dedupe, event-time) -> PostGIS
   -> outbox -> Kafka asseta.telemetry.position -> timeline-worker (geofences, states, alerts)
   connectivity-worker (60 s sweeps: LIVE/RECENT/STALE/OFFLINE, stale/offline alerts, partition top-up)
```

* Asseta never parses binary device protocols; Traccar does (DEC-003). A new vendor = a new adapter producing the
  vendor-neutral `TelemetryObservation` (`backend/src/asseta/modules/telemetry/observation.py`); downstream modules do
  not change.
* Traccar attribute mapping (`modules/telemetry/traccar.py`): `fixTime` → event time; `latitude/longitude/altitude`,
  `speed` (knots → km/h), `course`, `accuracy`; attributes `sat`, `ignition`, `hours` (engine hours, ms), `totalDistance`
  / `odometer`, `fuel`, `power` (external V), `batteryLevel`, `motion`, `alarm`. Anything else is kept in `extra`.
  Values a device does not send stay `NULL` — nothing is invented.

## Supported protocols

| What | Status |
|---|---|
| Traccar 6.10.0 gateway, JSON position forwarding | **Verified** (Compose `telemetry` profile, `compose_smoke.py`, drills) |
| OsmAnd protocol (port 5055) from `asseta.tools.gps_simulator` | **Verified with a simulator only** |
| Any other Traccar protocol (Teltonika, Queclink, Concox/GT06, Meitrack, …) | Supported by Traccar itself; reaches Asseta through the same forward. **Not verified on hardware** — each model needs the commissioning acceptance below |

Only **platform-approved tracker models** may be registered by tenants: the platform owner creates the model with its
protocol and *declared* capability matrix (`POST /api/v1/platform/tracker-models`, permission
`platform.tracker_model.manage`); tenants pick from `GET /api/v1/tenant/tracker-models`.

### Exposing a device protocol port

Traccar listens on one port per protocol (see the Traccar protocol list; e.g. OsmAnd 5055, Teltonika 5027, GT06 5023).
In `compose.yaml` only 8082 (web UI) and 5055 (OsmAnd) are published, both bound to `127.0.0.1`. For a real device:

1. Add the protocol's port to the `traccar` service `ports:` — bound to the public interface of the gateway host
   (e.g. `"0.0.0.0:5027:5027"` and `"0.0.0.0:5027:5027/udp"` if the device uses UDP), in a `compose.override.yaml`.
2. Open only that port in the firewall / security group. Traccar's web UI (8082) must never be public.
3. Production: set `DATABASE_REGISTER_UNKNOWN=false` (DEC-017) and register each device in Traccar explicitly
   (Traccar UI or API, identifier = IMEI) so unknown devices are not even accepted by the gateway. Asseta still
   quarantines devices unknown to a tenant (`UNKNOWN_DEVICE`) either way.

## Gateway key (Traccar ↔ Asseta authentication)

* One shared secret `ASSETA_TRACCAR_GATEWAY_KEY` (≥ 24 characters; e.g. `openssl rand -base64 32`) is used both as
  Traccar's `FORWARD_HEADER: X-Asseta-Gateway-Key: <secret>` and by `asseta-bootstrap`
  (`backend/src/asseta/tools/bootstrap.py`, run by the `migrate` service), which stores **only the SHA-256 hash** in
  `telemetry_gateway` (name `traccar-primary`). A shorter/unset key skips provisioning with a warning.
* Requests without the header → 401; unknown or inactive key → 401 (`modules/telemetry/router.py::ingest_traccar`).
* **Rotation:** change the value in `.env`, then `docker compose up -d migrate traccar` (bootstrap re-hashes the new
  key; Traccar restarts with the new header). Traccar retries forwards (`FORWARD_RETRY_ENABLE=true`) so positions
  received during the switch are re-sent.
* **Emergency revocation (leaked key):** `POST /api/v1/platform/telemetry-gateways/{id}/deactivate` with a reason
  (permission `platform.gateway.manage`) refuses the key immediately; ingestion history is kept. Additional gateways
  (one key each, shown once) can be created with `POST /api/v1/platform/telemetry-gateways`.

## Commissioning a physical tracker (per device)

| # | Step | Who / call |
|---|---|---|
| 1 | **Approve the model** with the declared capability matrix from vendor documentation (`GNSS`, `ACCURACY`, `IGNITION`, `ENGINE_HOURS`, `FUEL_LEVEL`, `EXTERNAL_POWER`, `BATTERY`, `TAMPER`, `MOTION`, `ODOMETER`, `OFFLINE_BUFFERING`) | Platform owner: `POST /api/v1/platform/tracker-models` |
| 2 | **Install**: constant power, ignition sense wired if `IGNITION` declared, antenna with sky view; record SIM ICCID/MSISDN and carrier | Installer |
| 3 | **Configure the device** to the gateway host + protocol port; device identifier = IMEI; reporting interval per tenant needs (the TRACKING policy thresholds below assume ≤ 5 min while moving) | Installer (vendor tool / SMS commands) |
| 4 | **Register in Asseta**: `external_id` = IMEI (globally unique per adapter — a tenant cannot claim another tenant's device), label, optional `sim_iccid`, `sim_msisdn`, `carrier`, `credentials_ref` → state `REGISTERED` | Tenant (`tenant.tracker.write`): `POST /api/v1/tenant/trackers` |
| 5 | **Enroll** the machine as a billable asset (DEC-014: telemetry is processed only for machines with an active enrollment on the event date) | Tenant: `POST /api/v1/tenant/billing/enrollments` `{machine_id, effective_from}` |
| 6 | **Assign** as primary tracker (one open primary per machine; swap with `replace_existing_primary: true`) | Tenant: `POST /api/v1/tenant/trackers/{id}/assign` `{machine_id, effective_from, is_primary, reason}` |
| 7 | **Verify reporting**: the first authenticated, assigned, valid report flips the tracker to `VERIFIED_REPORTING` | `GET /api/v1/tenant/trackers/{id}`; fleet map `GET /api/v1/tenant/fleet/map` |
| 8 | **Verify capabilities**: each declared capability becomes *verified* only when observed in real data (`verified_at`, `last_observed_at` per capability) — e.g. toggle ignition → `IGNITION` verified | `GET /api/v1/tenant/trackers/{id}` (capabilities) |
| 9 | **Record acceptance evidence** (checklist below) in track.md | Platform owner + installer |

Declared but never-verified capabilities stay unverified and are **not** used for status claims: engine status is
`UNKNOWN` without verified ignition (`tests/api/test_geospatial.py::test_fleet_map_status_dimensions_staleness_and_history`).
Tracker lifecycle: `POST /tenant/trackers/{id}/unassign`, `POST /tenant/trackers/{id}/state` (`SUSPENDED`/`RETIRED`).

## Time handling, late and buffered data

* Positions are stored by **event time** (`fixTime`), not upload time. A buffered upload after a coverage gap is
  attached to the machine assignment and enrollment valid *at event time*, marked `is_late` when older than the
  latest position, and **never overwrites** the latest position; the timeline worker replays the machine from the
  event time and supersedes (never deletes) affected alerts (DEC-016;
  `tests/api/test_trackers_ingestion.py::test_tracker_swap_keeps_one_billable_asset_and_attaches_late_data_by_event_time`,
  `tests/api/test_geospatial.py::test_geofence_exit_with_tolerance_and_late_data_replay`).
* Exact duplicates `(tracker, event_time)` are counted as `duplicates`, not stored twice.
* TRACKING policy (seed defaults in `modules/policy/schemas.py`, tenant/machine overridable, versioned):
  `live_max_age_seconds` 300, `stale_after_seconds` 1800, `offline_after_seconds` 21600,
  `max_position_accuracy_m` 100 (worse → `LOW_ACCURACY`, kept as evidence, excluded from geofence decisions),
  `max_plausible_speed_kmh` 120 (→ `IMPLAUSIBLE_JUMP`), `future_timestamp_tolerance_seconds` 300,
  `max_replay_age_days` 30, `low_power_voltage` (off by default).

## Quarantine reasons and troubleshooting

Quarantined input is stored with its raw payload and a reason, never attributed to a machine. Review:
`GET /api/v1/tenant/telemetry/ingestion-events?status=QUARANTINED` (tenant, `tenant.tracker.read`) or, as system,
`SELECT quarantine_reason, count(*) FROM tracker_ingestion_event WHERE status='QUARANTINED' GROUP BY 1;`

| Symptom / reason | Meaning | Fix |
|---|---|---|
| Traccar log shows forward 401 | Gateway key mismatch or gateway deactivated | Same secret in `.env` for both; `docker compose up -d migrate traccar`; check `GET /platform/telemetry-gateways` |
| Nothing in Traccar at all | Device not reaching the gateway | APN/SIM data, server host/port/protocol on the device, firewall, `docker compose logs traccar` |
| `MALFORMED` | Payload not a valid Traccar position | Check the Traccar version/forward format (`FORWARD_TYPE=json`) |
| `UNKNOWN_DEVICE` | IMEI not registered to any tenant | Step 4 (check `external_id` = what Traccar shows as uniqueId) |
| `TRACKER_INACTIVE` | Tracker `SUSPENDED`/`RETIRED` | Reactivate via `/state` if intended |
| `UNASSIGNED` | No machine assignment at the *event time* | Step 6; `effective_from` must precede the fixes |
| `NOT_ENROLLED` | Machine not billable-enrolled on the event date (DEC-014) | Step 5 |
| `CLOCK_FUTURE` | Event time > now + tolerance | Device clock/GNSS time; check device timezone settings (must send UTC) |
| `TOO_OLD` | Older than `max_replay_age_days` | Expected for very old buffers; raise the policy only deliberately |
| `ACCEPTED_NO_FIX` | Report without a valid fix | Proves communication only; check antenna/sky view |
| Positions with `LOW_ACCURACY` / `IMPLAUSIBLE_JUMP` | Poor GNSS or multipath | Antenna placement; review policy thresholds |
| Engine always `UNKNOWN` | `IGNITION` never observed | Wire ignition sense; toggle ignition; verify capability |
| Map shows STALE/OFFLINE | No reports within thresholds | Power/coverage; the map deliberately never shows stale data as live |

## Simulator (not hardware validation)

`cd backend && uv run asseta-gps-simulator --device 352000000000001 --traccar http://localhost:5055 --points 20` sends
OsmAnd messages to Traccar (IMEI-shaped ids match Traccar's default `\w{3,15}` registration rule). Direct mode
(`--asseta http://localhost:8000 --gateway-key …`) bypasses Traccar. Tests use the same generator
(`asseta.tools.gps_simulator`) including duplicates, out-of-order and delayed delivery
(`tests/unit/test_gps_simulator.py`, `tests/api/test_trackers_ingestion.py`). Simulator results are never evidence
of hardware compatibility.

## What HARDWARE_VALIDATION_BLOCKED means

prompt.md §10 *field hardware criterion*: R1 software must include a fully tested Traccar integration and a
demonstrable simulated device (done); **real-device commissioning is a separate acceptance check** that depends on
customer-provided compatible hardware, SIM, connectivity and installation. Until that has been performed and recorded,
the status is `HARDWARE_VALIDATION_BLOCKED` — not `DONE`, and no document may claim hardware certification.

### Evidence required to lift it (record per tracker model in track.md evidence log)

1. Model, firmware version, protocol and port; installer, machine asset code, IMEI (masked), SIM carrier.
2. Tracker reached `VERIFIED_REPORTING`; screenshot/API output of the fleet map with position, accuracy and
   last-seen age that match the machine's real location.
3. Each declared capability verified by observation (`verified_at` set): ignition ON/OFF transitions match the
   machine; engine hours / fuel / power / battery / tamper only if declared, each with a deliberate test.
4. Coverage-gap test: device out of coverage ≥ 15 min while moving, then back — buffered fixes arrive with original
   fix times, appear in history and do not replace the current position (`is_late`).
5. Power-cut test if `EXTERNAL_POWER`/`TAMPER` declared → low-power/tamper alert raised.
6. Geofence exit test against a real jobsite geofence → alert raised once, with tolerance respected.
7. Stale/offline: device powered off → map goes STALE then OFFLINE at the policy thresholds; recovers on power-on.
8. No quarantined rows for the device except deliberately provoked cases.

Only when all applicable items pass for at least one tracker model may EXT-02a be marked resolved for that model.
