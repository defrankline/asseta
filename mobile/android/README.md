# Asseta Android (Gate 4: offline-first Supervisor field app)

Native Android apps for Asseta: **Supervisor** (`com.asseta.supervisor`, offline-first field app) and
**Owner** (`com.asseta.owner`). Both are thin shells over shared `:core:*` modules so business rules are
never duplicated between them.

Gate 0 delivered the foundation (secure storage, encrypted DB + outbox, typed networking, Keycloak login, `/me`,
tenant selection). Gate 4 adds the Supervisor field app: device registration, bootstrap/delta sync with policy
snapshots, hour-meter capture (CameraX + bundled on-device ML Kit OCR, or manual), mandatory fresh GPS attempt,
resumable encrypted evidence upload, the outbox sync engine (WorkManager), work log, customer acknowledgement,
job START/COMPLETE, sync status screen, clock-tamper alert and device-revocation wipe. The Owner app is unchanged.
Gate 5 operations (expenses, collections, fuel, cash) are not part of this gate.

## Modules

| Module | Purpose |
| --- | --- |
| `:core:model` | Pure-Kotlin/JVM API DTOs (kotlinx.serialization): `MeResponse`, `TenantAccess`, `TenantAccessState`, `ErrorEnvelope`, strict UUID serializer, `DecimalAmount`/`Money` (decimal string on the wire; floats rejected), `ClientOperationStatus`. `sync/`: protocol v1 DTOs (`DeviceRegisterIn`, `BootstrapDto`, `ChangesDto`, `PushIn`/`PushResultDto`, `BlobStartIn`/`BlobSessionDto`, job/machine/... DTOs) and op payloads (`MeterCaptureIn`, `GpsIn`, `ActivityPayload`, `AcknowledgementPayload`, `JobTransitionPayload`), per contracts/openapi.json. |
| `:core:domain` | Pure-Kotlin field rules shared by all screens and the engine (JVM-tested): `MeterReadingParser` (port of the shared OCR spec v1), `GlyphSegmenter`/`GlyphRenderer`/`SevenSegmentDecoder`/`GeometricOcr` (glyph geometry, re-rendering, segment decoder and agreement scoring of the OCR pipeline), `OcrAssessor`/`OcrConsensus`/`PixelRedCellDetector` (text-only fallback + drum handling), `PolicySelector` (machine > tenant snapshot, expiry, offline grant), `CaptureValidator`/`ReadingValidator`/`OcrFlow` (mode, photo, recapture, decimals), `JobStateRules`, `GpsOutcome`, `OutboxTransitions` (state machine), `JobOperationPlanner` (dependency chain), `Backoff`, `ClockCheck`. |
| `:core:sync` | Data + engine (Android library): `SyncEngine` (register -> bootstrap/changes -> blob upload -> push -> changes), `OutboxPusher`, `BlobUploader`, `ServerDataWriter`, `FieldRepository` (read side), use cases `CaptureMeterReading` and `JobWorkflow`, `FieldOutbox` (single place that enqueues ops with dependencies), `EncryptedEvidenceStore`, `DeviceWipe`, `SyncWorker`/`SyncScheduler` (WorkManager). |
| `:core:security` | Android Keystore AES-256-GCM key per purpose (`KeystoreSecretCipher`), wrapped-secret file store in `noBackupFilesDir`, SQLCipher passphrase provider (32 random bytes, generated once, never regenerated silently), encrypted token store, evidence data key (`WrappedRandomKey`), device id (`DeviceIdStore`), `wipeLocalSecrets()` (deletes wrapped files and their Keystore keys). |
| `:core:database` | Room + SQLCipher (`SupportOpenHelperFactory`), schema v2. Outbox `client_operation` (+ `client_operation_dependency` for multi-parent deps, attachment gate, server result/error code) with SQL-guarded transitions; `attachment` (resumable upload state), `job`, `machine`, `reference_record`, `policy_snapshot`, `sync_state`, `meter_capture`, `work_log_entry`. `DatabaseHolder` (close + delete for the wipe). Exported schemas in `core/database/schemas/`; v1->v2 is a Room AutoMigration with a post-migrate step copying legacy `depends_on`; **no destructive fallback**. |
| `:core:network` | OkHttp/Retrofit client. Interceptors: `Authorization: Bearer`, `X-Tenant-ID`, `X-Correlation-ID` (UUID per request), `Idempotency-Key` on POST/PUT/PATCH/DELETE (an explicit key, e.g. the outbox operation id, is preserved), error envelope → `ApiException`. Base URL from `BuildConfig`. Debug-only cleartext to `10.0.2.2`/`localhost`. |
| `:core:auth` | AppAuth Authorization Code + PKCE against Keycloak realm `asseta`, public client `asseta-mobile`; the redirect scheme is supplied per app (see Configuration), never defined in core; token refresh; logout (local clear + Keycloak end-session). `SelectedTenantStore`. Keycloak and the API are authoritative; the app never authorizes locally, it only hides UI. |
| `:core:ui` | Material3 brand theme (Slate `#0F2A3D`, Amber `#F5A300`), launcher adaptive icon (vector conversion of `branding/asseta-mark.svg`), login screen, `/me` + tenant picker, `SessionViewModel` (+ forced sign-out via `SessionNotice`), `AssetaSessionApp(container, home)` (optional per-app home after tenant selection), `AssetaAppContainer` (manual DI, resettable `databaseHolder`). |
| `:app:supervisor` | `FieldGraph` (manual DI for the field app), screens (jobs, job detail, capture, acknowledgement + signature pad, sync status, clock banner), `MeterOcr` (ML Kit bundled), `ImageEnhancer`, `GpsLocator` (Fused, foreground only), `CameraCapture` (CameraX in-memory JPEG), just-in-time permission rationale. Manifest: INTERNET, CAMERA, FINE/COARSE location (no background location), backups disabled. |
| `:app:owner` | Application, `MainActivity`, manifest (INTERNET only). Unchanged in Gate 4. |

## Toolchain

All versions are pinned in `gradle/libs.versions.toml`. Gradle wrapper 9.6.1, AGP 9.4.1 (built-in Kotlin),
Kotlin 2.4.21, KSP 2.3.12, compileSdk 37, targetSdk 36, minSdk 26, Java/Kotlin bytecode target 17.
Builds run on the JDK 25 installed here (Gradle daemon and compilation); no separate toolchain is needed.
Requires the Android SDK (`local.properties` → `sdk.dir`, or `ANDROID_HOME`).

## Configuration

Endpoints are Gradle properties (override with `-P` or `~/.gradle/gradle.properties`):

| Property | Default |
| --- | --- |
| `asseta.debug.apiBaseUrl` | `http://10.0.2.2:8000/` (emulator → host Docker Compose API) |
| `asseta.debug.keycloakIssuer` | `http://10.0.2.2:8080/realms/asseta` |
| `asseta.release.apiBaseUrl` / `asseta.release.keycloakIssuer` | empty; must be set to **https** URLs for release, otherwise the app fails fast on start |

Each app has its own private-use redirect scheme so that, with both apps installed, the login/logout
callback is never routed to the other app (no chooser). It is set once in the app module's
`build.gradle.kts` (`oidcRedirectScheme`), which feeds both the `OIDC_REDIRECT_SCHEME` BuildConfig field
(passed into `AuthConfig` via `AssetaAppContainer`) and AppAuth's `appAuthRedirectScheme` manifest placeholder:

| App | Redirect URI | Post-logout redirect URI |
| --- | --- | --- |
| Supervisor | `com.asseta.supervisor:/oauth2redirect` | `com.asseta.supervisor:/logout` |
| Owner | `com.asseta.owner:/oauth2redirect` | `com.asseta.owner:/logout` |

Keycloak needs the single public client `asseta-mobile` (realm `asseta`) with PKCE (S256), standard flow,
and all four URIs above registered as valid redirect / post-logout redirect URIs.
Note: the token `iss` will be `http://10.0.2.2:8080/realms/asseta` from the emulator, while the backend
defaults to `http://localhost:8080`; set Keycloak's frontend URL/hostname (or use `adb reverse tcp:8080 tcp:8080`
plus `localhost` issuer properties) so both agree.

## Commands

```bash
./gradlew assembleDebug testDebugUnitTest lint assembleAndroidTest --console=plain   # required gate
./gradlew connectedDebugAndroidTest                                                 # needs an emulator/device
```

`testDebugUnitTest` covers the pure-JVM `:core:model` and `:core:domain` too (aliases of their `test` tasks). Room
DAO, migration and sync-engine tests run under Robolectric on plain SQLite (SQLCipher's native library is
device-only); the engine tests drive the real `SyncEngine` over HTTP against `FakeSyncServer` (MockWebServer
dispatcher emulating the backend sync semantics). The OCR parser test reads `contracts/fixtures/ocr/parse_cases.json`
in place (Gradle passes the path); the instrumented OCR test mounts `contracts/fixtures/ocr` read-only as test
assets. Nothing is copied.

Instrumented tests: `EncryptedDatabaseTest` (SQLCipher at rest), `DeviceWipeTest` (real Keystore: evidence
encrypted at rest; wipe removes DB, keys, tokens, files; device id kept), `MeterOcrFixtureTest` (ML Kit over all 24
fixture images + the shared parse cases on the device runtime). Emulator note: a locked AVD user breaks ML Kit
(credential-encrypted storage); use an AVD without a screen lock.

## Sync protocol client (docs/offline-sync.md)

- **Device identity**: random UUID in Keystore-protected storage (`DeviceIdStore`), sent as `X-Device-Id` on every
  `/api/v1/sync/` call (`DeviceIdInterceptor`); the tenant is explicit per sync call. Each run first calls
  `POST /sync/devices` (idempotent server-side; refreshes `offline_grant_until`), then `GET /sync/bootstrap` once
  (no cursor yet) or `GET /sync/changes?cursor=` pages (bounded), persisting the cursor in the same transaction as
  the data. Server rows are upserted by `(id, version)` (newer or equal wins; the DTOs carry `version`, not
  `sync_revision`); bootstrap drops cached jobs no longer delivered.
- **Policy snapshots** are stored per `(policy_type, scope_key)`. A capture uses `machine:<id>` else `tenant`; it is
  blocked ("Connect to refresh rules. ...") when no snapshot, `now > valid_until`, or past `offline_grant_until`.
  Every capture sends the snapshot's `policy_version_ids`.
- **Outbox** (`client_operation`): ops `METER_CAPTURE`, `JOB_ACTIVITY`, `JOB_ACKNOWLEDGEMENT`, `JOB_TRANSITION`
  (`{job_id, action}`) with the chain opening capture -> START -> activities/closing -> acknowledgement -> COMPLETE
  (`JobOperationPlanner`; FAILED/CONFLICT parents are skipped so a re-capture becomes the parent). An op is
  dispatchable when PENDING/QUARANTINED, every dependency is ACKED locally, and its evidence attachment has a server
  `attachment_id` (written into the never-sent payload in the same transaction as the upload completion).
  Push: bounded batches (25, halved on `BATCH_TOO_LARGE`) with `device_now`; outcomes per `OutboxTransitions`:
  ACKED/DUPLICATE -> ACKED (result stored), DEFERRED -> PENDING, CONFLICT -> CONFLICT (server_state kept, never
  resent), REJECTED -> FAILED (error code shown, not resent), QUARANTINED -> held and resent later. A DUPLICATE
  replays the server's *stored* outcome, so DUPLICATE + `SUBSCRIPTION_READ_ONLY` stays QUARANTINED and DUPLICATE +
  another error maps to CONFLICT (with server_state) / FAILED. Network/5xx/408/429 -> batch back to PENDING, retry
  via WorkManager (network constraint) after exponential backoff with equal jitter (15 s base, 30 min cap, persisted
  failure streak). SENT rows left by a killed process return to PENDING at the next run (idempotent resend).
- **Evidence**: original JPEG bytes from CameraX (in memory, never written unencrypted) and signature PNGs are
  stored AES-256-GCM encrypted (`EncryptedEvidenceStore`, data key wrapped by a Keystore key) in `noBackupFilesDir`;
  SHA-256 of the original bytes; resumable upload (`POST /sync/blobs` -> missing `PUT chunks` -> `complete`), the
  session, chunk size and confirmed chunks are persisted after each chunk; `CHECKSUM_MISMATCH`/expired/unknown
  session -> new session; known content completes immediately.
- **DEVICE_REVOKED** (any sync call): cancel work, close + delete the database, delete evidence and cache files,
  destroy the DB key, evidence key and tokens (files + Keystore keys), clear the tenant, and show the explanation on
  the login screen (persisted `SessionNotice`, so it also works when the wipe happened in background sync). The
  device id is kept so the revocation sticks.
- **Clock**: last server time + `elapsedRealtime` at receipt are persisted; the banner warns when the wall clock
  deviates by > 300 s (or the server reported `clock_skew_alert`). Device time is still recorded and sent as-is.

## Capture rules (enforced in the use case, shown in the UI)

OPENING on an APPROVED job, CLOSING on an IN_PROGRESS job (including a locally queued START). The required mode is
the snapshot's `opening_mode`/`closing_mode`. AUTOMATIC: camera photo + on-device OCR -> recognised value and
confidence for confirmation; editing it is a manual correction (OCR value/raw text kept, edited reading sent);
below `min_ocr_confidence` the user must retake until `max_recapture_attempts` recaptures are used, then may enter
the value manually (photo + OCR kept). MANUAL: numeric entry at the meter's decimal places; photo when
`manual_photo_required`. Every capture makes its own fresh GPS attempt (Fused, high accuracy, 20 s, max update age
0; re-attempted if older than 90 s at capture time) and records FIX or NO_FIX/TIMEOUT/PERMISSION_DENIED/DISABLED
without coordinates. Capture id: UUID generated once per capture screen visit.

## OCR accuracy (bundled ML Kit Latin 16.0.1, API 35 arm64 emulator, 2026-10-21)

Pipeline (same algorithm as iOS `MeterOCR`; pure parts in `:core:domain`, JVM-tested): ML Kit's own confidence is
high even for wrong reads of segmented displays, so it is not the score. The photo is segmented into glyphs (median
filter, Otsu polarity, adaptive threshold, connected components, column merge, row chaining, deskew above 1.5 deg);
the decimal point comes from geometry and the drum tenths wheel from a red cell. The three most prominent rows are
re-rendered as clean glyphs in three layouts, each read by ML Kit, and every layout must give exactly one character
per glyph. A deterministic seven-segment decoder is a second opinion. ML Kit reads an upright seven-segment `7` as
`1`: when the only difference to the decoder is such a too-wide `1`, italic renders of the row are also read, and the
decoder's digits are used only if one of those reads matches them exactly. Scores (`GeometricOcr`): unanimous 0.92
(+0.05 with full-frame agreement), 2 of 3 layouts 0.70, else 0.50; capped at 0.60 for a suspicious `1`, a decoder
conflict or a full-frame conflict, and at 0.50 for an ambiguous dot or another same-size row with a different number.
Without a geometric read the text-only assessment is used, capped at 0.40. These are heuristic agreement scores, not
calibrated probabilities; any disagreement keeps a read below 0.85, so the app asks for a recapture.

`MeterOcrFixtureTest` over the 24 images of `contracts/fixtures/ocr/manifest.json` ("confident" = >= 0.85), identical
over three runs:

| Metric | Result |
| --- | --- |
| Confident wrong reads (all 24) | **0** (hard assertion) |
| must_read accepted correct (confident and right) | **17/17 = 1.00** (manifest target 0.90 asserted; regression floor 1.0) |
| By style (must_read) | lcd_7seg 3/3, mechanical_drum 4/4, backlit_amber 5/5, plain_digital 5/5 |
| fallback_ok accepted correct | 5/7 |

Of the `fallback_ok` images, `lcd_7seg__blur` is read wrongly (`41213.3`) at 0.50 and `lcd_7seg__noise` gets no
geometric read, so the text-only read (`212.5`, wrong) is capped at 0.35; both lead to a recapture. The other five are
read correctly at >= 0.92. The fixtures are synthetic; real samples are still required (EXT-05).

## Rules for later gates

- Every schema change: bump `AssetaDatabase.VERSION`, commit the new `schemas/*.json`, add a migration + test.
- Outbox operation `id` is the server `Idempotency-Key`; pass it explicitly on the request.
- Never mark an operation synced before a durable server ACK (`markAcked` requires `SENT`).
- Money is `DecimalAmount`/`Money` (decimal strings); never `Double`/`Float`.
- Add Android permissions only with the feature that needs them; never background location.
- New field operations go through `FieldOutbox.enqueue` (dependencies) and `OutboxTransitions` (outcomes).
- Files stay under 500 lines.
