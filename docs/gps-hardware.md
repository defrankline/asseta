# GPS / telematics hardware and commissioning

**Status:** software path verified with a *simulated* device through a real Traccar 6.10.0 gateway
(`backend/scripts/compose_smoke.py`). **Physical device commissioning: `HARDWARE_VALIDATION_BLOCKED`** — requires a
customer-provided supported tracker, SIM/data plan and installation (track.md EXT-02).

## Architecture
```
tracker --(vendor protocol)--> Traccar gateway --(JSON forward + X-Asseta-Gateway-Key)--> POST /api/v1/telemetry/traccar
   -> TraccarAdapter -> TelemetryObservation -> ingestion (quarantine/dedupe/event-time) -> PostGIS
   -> outbox -> Kafka asseta.telemetry.position -> timeline worker (geofences, states, alerts)
```
* Asseta never parses binary device protocols itself; Traccar does (DEC-003). New vendors = new adapter producing
  `TelemetryObservation`; downstream modules do not change.
* Gateway authentication: one shared secret `ASSETA_TRACCAR_GATEWAY_KEY` configures Traccar's forward header and is
  provisioned in Asseta (hash only) by `asseta-bootstrap`. Rotate by changing the secret and restarting both.

## Traccar configuration (Compose `telemetry` profile)
| Setting (env) | Value | Why |
|---|---|---|
| `FORWARD_TYPE` / `FORWARD_JSON` | `json` / `true` | Position forwarding as JSON |
| `FORWARD_URL` | `http://api:8000/api/v1/telemetry/traccar` | Asseta ingest |
| `FORWARD_HEADER` | `X-Asseta-Gateway-Key: <secret>` | Gateway authentication |
| `FORWARD_RETRY_ENABLE` | `true` | Traccar retries while Asseta is unavailable |
| `DATABASE_REGISTER_UNKNOWN` | `true` **dev only** | Production: register devices in Traccar explicitly |

Device ports: OsmAnd 5055 is exposed for the simulator. Expose only the protocol ports of approved tracker models,
behind the deployment firewall; Traccar's web UI (8082) must not be public.

## Commissioning a physical tracker (per device)
1. **Model approved** — platform owner creates the tracker model (`POST /platform/tracker-models`) with the
   *declared* capability matrix from vendor documentation.
2. **Install** — wire ignition sense (if IGNITION declared), constant power, antenna with sky view; record SIM ICCID/MSISDN.
3. **Gateway** — device configured to the Traccar server/port for its protocol; device identifier = IMEI.
4. **Register in Asseta** — tenant registers the tracker (`external_id` = IMEI) → state `REGISTERED`.
5. **Enroll + assign** — the machine must be an enrolled billable asset (DEC-014); assign as primary tracker.
6. **Verify reporting** — first valid report flips the tracker to `VERIFIED_REPORTING`. Capabilities become
   *verified* only when observed in real data (e.g. toggle ignition → IGNITION verified).
7. **Acceptance evidence** (record in track.md): positions on the fleet map with sane accuracy; ignition ON/OFF
   transitions match the machine; power-cut/battery behaviour if declared; buffered upload after a coverage gap
   arrives with original fix times (late data appears in history, not as current position); geofence exit test.

Declared but never-verified capabilities stay unverified and are **not** used for status claims (e.g. engine status
shows `UNKNOWN` without verified ignition).

## Simulator (not hardware validation)
`uv run asseta-gps-simulator --device 352000000000001 --traccar http://localhost:5055 --points 20` sends OsmAnd
messages to Traccar (IMEI-shaped ids match Traccar's default `\w{3,15}` registration rule). Tests use the same
generator directly (`asseta.tools.gps_simulator`), including duplicates, out-of-order and delayed delivery.
