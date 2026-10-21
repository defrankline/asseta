# Asseta iOS (Gate 0 foundation + Gate 4 Supervisor field app)

Native SwiftUI apps **Asseta Supervisor** (`com.asseta.supervisor`) and **Asseta Owner**
(`com.asseta.owner`), iOS 17+, sharing one Swift package, `AssetaKit`. Business rules live in
AssetaKit or on the server, never in an app target. Keycloak and the Asseta API decide
authentication and authorization. The apps only use `/api/v1/me` permissions and menus to
choose what to show.

## Layout

```
mobile/ios/
  project.yml                 XcodeGen spec (the .xcodeproj is generated, not committed)
  Apps/Supervisor|Owner/      @main entry points (a few lines each)
  Apps/Shared/Assets.xcassets AppIcon (from branding/asseta-mark.svg) + AccentColor (Amber)
  Apps/SupervisorTests/       Tests hosted in the app (real Keychain, LocalStore with Keychain key,
                              revocation wipe, Vision OCR fixtures on the iOS runtime)
  Scripts/generate-app-icon.sh
  AssetaKit/                  Swift package (Swift 6 language mode, strict concurrency)
```

| Target | Responsibility |
|---|---|
| `AssetaModel` | Codable DTOs: `MeResponse` (incl. `platform_menus`, tenant `access_state`), `ErrorEnvelope`, `DecimalString` (money is decoded from a JSON string straight into `Decimal`; JSON numbers are rejected), UTC ISO-8601 coders |
| `AssetaSecurity` | `KeychainSecretStore` (data-protection keychain, `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`), `DatabaseKeyProvider` (random 256-bit key from `SecRandomCopyBytes`), `TokenStore` |
| `AssetaStore` | `EncryptedDatabase` (SQLCipher, raw key, WAL, iOS file protection), versioned `Migrator` (`user_version` + `schema_migration`), the `client_operation` outbox and `ClientOperationRepository` |
| `AssetaNetwork` | `APIClient`: `Authorization: Bearer`, `X-Tenant-ID`, a fresh `X-Correlation-ID` per request, and `Idempotency-Key` on mutations (a mutation can't be built without one). Decodes the error envelope into `APIError`. Retries once after a 401 by refreshing the token |
| `AssetaAuth` | OIDC Authorization Code + PKCE (S256) against realm `asseta`, public client `asseta-mobile`. Each app has its own redirect scheme, set in its app target (see Configuration). The callback must match that app's scheme and path. Checks the discovered issuer, `state` and the ID-token `iss/aud/azp/exp/nonce`. Shares one token refresh between concurrent callers and logs out on `invalid_grant`. Being offline does not end the session. Logout calls the Keycloak end-session endpoint with the refresh token and always wipes local tokens |
| `AssetaAppShell` | Brand, `AppConfiguration` (from Info.plist), `SessionModel` (state machine), and the login, `/me` and tenant-picker views shared by both apps. The browser step uses SwiftUI `WebAuthenticationSession` with an **ephemeral** session |
| `AssetaCapture` | Gate 4 capture: shared-spec OCR text parser (`MeterReadingParser`), Vision OCR pipeline (`MeterOCR`, `GlyphSegmenter`, `GlyphRenderer`, `SevenSegmentDecoder`), capture rules and the recapture state machine (`CaptureRules`), one-shot GPS (`LocationCapturer`, pure `GpsAttempt`), protected evidence files with SHA-256 (`EvidenceStore`) |
| `AssetaSync` | Gate 4 offline sync: Keychain device id, `/sync` client with `X-Device-Id`, `SyncEngine` (register → bootstrap → upload → push → pull), push outcome state machine, resumable `BlobUploader`, policy snapshot selection and capture gate, clock tamper monitor, backoff, `FieldRecorder` (outbox ops + dependency chain), `FieldDirectory` (read side), `DeviceWipe` |
| `AssetaField` | Gate 4 Supervisor SwiftUI screens (iOS only): jobs, job detail, meter capture with AVFoundation camera, work log, acknowledgement with PencilKit signature, sync status; `NWPathMonitor` and `BGAppRefreshTask` triggers |
| `AssetaTestSupport` | Test doubles (`MockTransport`, `MockURLProtocol`, fixtures). Not a product |

### Local schema (versioned migrations in `AssetaStore/Migrations.swift`)

| Version | Name | Content |
|---|---|---|
| 1 | `create_client_operation_outbox` | Gate 0 outbox |
| 2 | `outbox_sync_protocol` | Rebuilds `client_operation` (SQLite cannot alter CHECKs): adds `CONFLICT`, `error_code`, `server_result_json`, `next_attempt_at`; ACKED now requires the stored server result (push results carry the entity, not a revision; `server_revision` keeps the entity `version` when present). Adds `client_operation_dependency` (several parents, sent as `depends_on[]`), `local_attachment` (upload queue with session id, chunk size, received chunk indexes) and `operation_attachment` |
| 3 | `sync_state_entities_policies` | `sync_kv` (cursor, registration, offline grant, backoff, clock reference), `sync_entity` (server-owned JSON by tenant/type/id with `revision` + `version`), `policy_snapshot` |
| 4 | `finance_receipts_cash_custody` | Non-destructive rebuild (row copy; child table renamed before its parent so `foreign_keys=ON` holds) of `local_attachment` (purpose `EXPENSE_RECEIPT`) and `operation_attachment` (field `receipt_upload_ids`); new `cash_custody_balance` (server custody per staff/currency, replaced on every bootstrap/changes response, older lists ignored). Expense categories live in `sync_entity` (`expense_category`) |

`EncryptedDatabase.transaction` nests as savepoints, so composed repository calls stay atomic.

### Outbox state machine (`client_operation`)

Statuses: `PENDING`, `SENT`, `ACKED`, `FAILED` (server REJECTED), `CONFLICT`, `QUARANTINED`. Legal changes:
`PENDING→SENT`, `QUARANTINED→SENT` (re-send), `SENT→ACKED|FAILED|CONFLICT|QUARANTINED|PENDING`,
`FAILED→PENDING` (user retry only), `PENDING|FAILED→QUARANTINED`. Nothing else, enforced in the repository.

| Push result | Local effect |
|---|---|
| `ACKED` | `ACKED`, server result stored |
| `DUPLICATE` | Replays the stored outcome: no error → `ACKED`; `SUBSCRIPTION_READ_ONLY` → stays `QUARANTINED`; conflict code or `server_state` → `CONFLICT`; other code → `FAILED` |
| `DEFERRED` | Back to `PENDING`, retried after 10 s |
| `CONFLICT` | `CONFLICT` with `server_state`; never auto-overwritten or auto-retried; evidence kept |
| `REJECTED` | `FAILED`, error code shown; evidence kept; user may retry |
| `QUARANTINED` | `QUARANTINED` ("held: subscription read-only"), re-sent every 15 min until applied |
| no result / network error / 5xx / 429 | Whole batch back to `PENDING`; engine backoff `min(15 min, 2 s·2^(n-1))·U[0.5,1)` persisted in `sync_kv` |

`readyToSend` returns PENDING (and due QUARANTINED) operations whose dependencies are all ACKED and
whose evidence files are all uploaded, oldest first. On launch every `SENT` row returns to
`PENDING` (same ids → server answers `DUPLICATE`), so termination mid-push is safe.

## Gate 4: Supervisor field app

Protocol: [`docs/offline-sync.md`](../../docs/offline-sync.md); DTOs: `contracts/openapi.json`.

- **Device identity.** A random UUID in the Keychain (`asseta.device.id.v1`, this-device-only), sent as `X-Device-Id` on every `/sync` call. First sync per tenant: `POST /sync/devices {device_id, platform:"IOS", app_version}` → `GET /sync/bootstrap` → `GET /sync/changes?cursor=` (cursor persisted, `has_more` paged).
- **Server-owned data** is stored as the server's JSON. Bootstrap replaces the tenant's cache; deltas upsert by id where the incoming `revision` (the response cursor) and, when present, the entity `version` are not older — the DTOs carry no `sync_revision` field, so this is the equivalent ordering. Local progress (e.g. a START waiting in the outbox) is overlaid for display (`JobProgress`), never written into server data.
- **Policy snapshots** (`METER_CAPTURE`): the `machine:<id>` snapshot if present, else `tenant`. New captures are blocked with "Connect to refresh rules…" when there is no snapshot, it is past `valid_until`, or past `offline_grant_until`. Expiry uses `max(wall clock, server time + monotonic elapsed)`, so winding the clock back does not revive expired rules. The offline grant is extended from server time after each successful contact, mirroring the server's `touch`. Every capture sends the snapshot's `policy_version_ids`.
- **Capture flow.** OPENING on an APPROVED job, CLOSING on an IN_PROGRESS one. The mode comes from the snapshot and cannot be changed in the UI. AUTOMATIC: in-app AVFoundation photo → on-device Vision OCR → value + confidence for confirmation. An edited value is sent as the reading while `ocr_value`/`ocr_raw_text` are kept, so the server records a manual correction. Below `min_ocr_confidence` the app asks for a recapture up to `max_recapture_attempts` times, then allows manual entry and keeps the photo and OCR output. MANUAL: numeric entry limited to the meter's decimal places; photo required when `manual_photo_required`. Capture id = one UUID per capture; capture time = device time of the photo, or of the save for a manual reading without a photo.
- **GPS.** Every capture starts a fresh CoreLocation attempt (`kCLLocationAccuracyBest`, updates for up to 20 s, best fresh fix wins, stops at ≤ 10 m). Only fixes newer than the attempt count. The real result is recorded: `FIX` (lat, lon, accuracy, timestamp, provider `corelocation`) or `NO_FIX`/`TIMEOUT`/`PERMISSION_DENIED`/`DISABLED` with no coordinates, and it is shown before saving. The when-in-use permission is requested when the first capture screen opens. There is no background location.
- **Evidence.** Original JPEG bytes (`fileDataRepresentation`, never re-encoded) and signature PNGs are stored in Application Support/AssetaEvidence (excluded from backup, `NSFileProtectionComplete`) with SHA-256 (CryptoKit). The file is re-hashed before upload. Upload flow: `POST /sync/blobs` → `PUT` of the chunk indexes that are not in `received_chunks` (state persisted after each chunk) → `POST complete`. `COMPLETE` writes the `attachment_id` into the waiting operation payloads in the same transaction. Already-known content completes immediately. `CHECKSUM_MISMATCH`, an expired session or an unknown session restarts the upload. `UPLOAD_INCOMPLETE` re-sends the chunks.
- **Dependencies.** opening capture → START → (work log entries, closing capture) → acknowledgement → COMPLETE. COMPLETE depends on the closing capture, the acknowledgement and every work log entry. A capture or acknowledgement is never sent before its file has an `attachment_id`.
- **Revocation.** `DEVICE_REVOKED` (or details `WIPE_LOCAL_DATA`) from any sync call wipes the SQLCipher database files and their Keychain key, the OAuth tokens and all evidence files, then returns to the login screen with an explanation. The device id is kept on purpose: a wiped phone stays the same revoked device and cannot re-register as a new one.
- **Clock tamper alert.** Each server response stores `server_time` + `CLOCK_MONOTONIC_RAW` (keeps counting in sleep, unaffected by clock changes) + `kern.bootsessionuuid`. A reboot (boot id change or monotonic reset) invalidates the reference. If the wall clock deviates by more than 300 s from `server_time + elapsed`, a banner is shown. The server's `clock_skew_alert` is shown too. Captures always carry the true device time.
- **When sync runs.** On launch, when the app returns to the foreground, when `NWPathMonitor` reports connectivity again, after each recorded action, when the backoff window ends while the app is open, on pull-to-refresh and "Sync now". Background sync uses `BGAppRefreshTask` (`com.asseta.supervisor.sync`) only as iOS allows; continuous background sync is not promised. Protected evidence files cannot be read while the phone is locked, so their upload waits for the next unlocked sync.
- **Sync status screen**: counts, last sync, next retry, offline grant, and lists of rejected (error code, retry), conflict (server state), held (read-only subscription) and waiting items (including "waiting for earlier item/upload").

### On-device OCR

Vision's `VNRecognizeTextRequest` (`.accurate`, no language correction) runs fully on device; the app makes no network OCR call.
Vision reports ~1.0 confidence even for wrong reads of segmented displays, so it is not used as
the score. The pipeline:

1. Median filter, Otsu polarity, adaptive local threshold, connected components, column merge for 7-segment pieces, row chaining, deskew when the row is tilted more than 1.5°.
2. Decimal point from geometry (a small mark on the baseline between glyphs). The **mechanical drum tenths wheel** is found by colour: the right-most glyph sitting on a saturated red cell, with the neighbouring cell not red. It is passed to the shared parser as a separate tenths token, so `20264.1` is not merged into `202641`.
3. The row is re-rendered as clean glyphs in three layouts. Each layout is read by Vision and must give exactly one character per glyph. A deterministic 7-segment decoder gives an independent second opinion.
4. The text is parsed with the shared spec (`MeterReadingParser`, a port of `ocr_parse.py`). The confidence is a heuristic agreement score, documented in `MeterOCR.swift`; it is not calibrated.

Results on `contracts/fixtures/ocr` (24 synthetic images; real samples are still required, EXT-05):

| Runtime | must_read correct with confidence ≥ 0.85 | confident wrong reads (≥ 0.85, wrong value) |
|---|---|---|
| macOS `swift test` | 17/17 (1.00) | 0 |
| iOS 26 Simulator (app-hosted test) | 17/17 (1.00) | 0 |

Of the `fallback_ok` images, `lcd_7seg__blur` is read wrongly but at 0.60, so the app asks for a recapture. `lcd_7seg__glare` and `lcd_7seg__noise` are read correctly but at 0.60 because the full-frame read conflicts with them. The other four are read correctly at ≥ 0.92.

## Gate 5: field finance (Supervisor)

Screens on the home list under **Money & fuel**, shown by `/me` permissions (`tenant.expense.write`, `tenant.collection.record`): **Record expense**, **Record cash collection**, **Hand over cash**, **Fuel event** and **My cash**. Every picker over synced data (categories, customers, jobs, machines) is a searchable sheet with a text filter (`SearchablePicker.swift`). Money, litres, prices and readings are parsed strictly into `Decimal` (`DecimalInput`) and sent as decimal strings.

- **Expense policy offline** (`FinanceRules.swift`): the tenant `EXPENSE_CAPTURE` snapshot gates the screen like meter captures (expiry, offline grant, trusted time). Receipt photo required when amount > `receipt_required_above` or in a foreign currency; GPS `FIX` with accuracy ≤ `gps_max_accuracy_m` when `gps_required`; above `auto_approve_limit` (or foreign) the form explains that a manager must approve. The recorder re-checks before writing to the outbox; the server re-checks everything.
- **Outbox**: `EXPENSE`, `CASH_COLLECTION`, `CASH_HANDOVER`, `FUEL_EVENT`, each with a device `client_id` fixed per form (exactly-once alongside the op id). Receipts are encrypted evidence files uploaded with purpose `EXPENSE_RECEIPT`; the expense is gated on every receipt upload and `COMPLETE` appends the upload session id to `receipt_upload_ids`. `DEFERRED ATTACHMENT_PENDING` is retried after 10 s, `RECEIPT_NOT_FOUND` is a rejection, `DUPLICATE_PAYMENT_REFERENCE` a conflict; all other outcomes as in the table above.
- **Synced data**: `expense_categories` (inactive ones hidden; deltas carry `is_active=false`), customers (likewise), and `cash_custody` (current balance per currency).
- **My cash**: the synced balance (as of the last sync) with pending handovers/spending from the server, kept apart from local unsynced collections/expenses/handovers, which are marked unverified; rejected/conflicting items are listed but not counted.

## Pinned toolchain and dependencies

- Xcode 26.6, Swift 6.3.3. The package uses swift-tools 6.0 and the Swift 6 language mode.
- [SQLCipher.swift](https://github.com/sqlcipher/SQLCipher.swift) **4.19.0** (`exact:`), the official Zetetic binary XCFramework. Its checksum is pinned in that package's manifest. Exact resolution is recorded in `AssetaKit/Package.resolved`.
- XcodeGen 2.46.0 and librsvg 2.63.3 (`rsvg-convert`) via Homebrew. These are build tools only.
- No other third-party code. Auth uses `AuthenticationServices` and `CryptoKit` from the system.

## Commands

```sh
# Package unit tests on macOS
cd mobile/ios/AssetaKit && swift test

# Package tests on the iOS Simulator
xcodebuild test -scheme AssetaKit-Package -destination 'platform=iOS Simulator,name=iPhone 17 Pro'

# Apps
cd mobile/ios
xcodegen generate
xcodebuild -project Asseta.xcodeproj -scheme AssetaSupervisor -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
xcodebuild -project Asseta.xcodeproj -scheme AssetaOwner      -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build

# Keychain, wipe and on-iOS Vision OCR tests hosted in the app (needs the app's default local signing)
xcodebuild -project Asseta.xcodeproj -scheme AssetaSupervisor -destination 'platform=iOS Simulator,name=iPhone 17 Pro' test

# Regenerate the app icon after changing branding/asseta-mark.svg
Scripts/generate-app-icon.sh
```

`swift test` reads the shared fixtures in place (`contracts/fixtures/ocr/parse_cases.json`, `manifest.json`,
`images/`) via `#filePath`, so they cannot drift from what Android and the backend use. It prints
the per-image OCR report. The sync engine tests run the real `URLSessionTransport` against an
in-process fake server (`MockURLProtocol` + `FakeSyncServer`, which mirrors the backend
push/blob semantics).

An unsigned `swift test` binary can't use the data-protection keychain
(`errSecMissingEntitlement`), so the real-Keychain test **skips** there. It runs for real in
`AssetaSupervisorTests`. The Simulator doesn't implement Data Protection classes, so the
file-protection assertion runs on physical devices only.

## Configuration

`AssetaAPIBaseURL`, `AssetaOIDCIssuer`, `AssetaOIDCRedirectURI` and
`AssetaOIDCPostLogoutRedirectURI` come from build settings in `project.yml`. AssetaKit hard-codes
none of them.

| App | `ASSETA_OIDC_SCHEME` | Redirect | Post-logout redirect |
|---|---|---|---|
| Supervisor | `com.asseta.supervisor` | `com.asseta.supervisor:/oauth2redirect` | `com.asseta.supervisor:/logout` |
| Owner | `com.asseta.owner` | `com.asseta.owner:/oauth2redirect` | `com.asseta.owner:/logout` |

The app refuses to start if a redirect isn't a private-use custom scheme or if the two redirects
use different schemes.

API and issuer endpoints:

- **Debug** points at the local stack: API `http://localhost:8000`, Keycloak `http://localhost:8080/realms/asseta`. `NSAllowsLocalNetworking` permits plain HTTP to localhost and `.local` only.
- **Release** is empty on purpose. Pass real values to `xcodebuild`. If a value is missing, the app shows "Build misconfigured" instead of contacting a wrong host.

Keycloak (realm `asseta`) must have a public client `asseta-mobile` with PKCE S256 required and
standard flow on. Its valid redirect URIs must include `com.asseta.supervisor:/oauth2redirect` and
`com.asseta.owner:/oauth2redirect`. Its valid post-logout redirect URIs must include
`com.asseta.supervisor:/logout` and `com.asseta.owner:/logout`.

Logout today ends the Keycloak session back-channel: it POSTs the refresh token to the
end-session endpoint, so no browser opens. The post-logout URI is configured and validated for a
browser-based RP-initiated logout, which can be added if needed. The browser session is
ephemeral, so no SSO cookie stays on the device.

Supervisor Info.plist (from `project.yml`): `NSCameraUsageDescription` and
`NSLocationWhenInUseUsageDescription` (both requested just in time), `UIBackgroundModes: fetch` and
`BGTaskSchedulerPermittedIdentifiers: com.asseta.supervisor.sync`. There is no background location
and no photo library access. The Owner app's Info.plist is unchanged.

## Security notes

- The database key and tokens stay on this device. They are never backed up and are readable after the first unlock, which lets background sync work later. The database directory is excluded from backups and has `completeUntilFirstUserAuthentication` protection.
- An encryption test shows the database file has no SQLite header and no plaintext, and that it can't be read without the key or with a wrong key.
- The browser session is ephemeral, so no Keycloak SSO cookie stays on the device after sign-out.
- Evidence files use `NSFileProtectionComplete`. The database uses `completeUntilFirstUserAuthentication`, so background sync can read it.
- A revocation wipe removes the database and its key, the tokens and the evidence. The device id stays.
- The app stores no permission decisions. `access_state` and the menus only change what the UI shows, and an unknown `access_state` is treated as blocked.

## Known limitations (Gate 4)

- The OCR results come from 24 synthetic images. Real dashboard photos are required before acceptance (EXT-05). The confidence values are heuristic, not calibrated probabilities.
- OCR runs Vision several times per photo: about 0.4 s per image on an Apple-silicon Mac and about 2.5 s in the Simulator. It runs off the main thread with a progress indicator.
- Background sync only runs while the app process is alive with a tenant open (the tenant selection is not persisted). If iOS launches the app cold in the background, there is no session to sync. Foreground and reconnect sync are the reliable paths.
- Signing out keeps unsynced items encrypted on the phone, and they sync after the next sign-in. The UI warns about this before sign-out.
- The Simulator has no camera. The capture screen says so, and AUTOMATIC capture has to be tested on a device.
- Field finance: the tenant base currency is only known from the synced custody (one currency). When it is unknown, an explicitly typed currency is treated as foreign offline (receipt + approval), and the server decides. "My cash" counts only unsynced local items as unverified; an item ACKED in a cycle whose pull then failed is not shown until the next pull refreshes the server balance.
- A cash collection has no job field on the server; the chosen job pre-selects the customer and is written into the note.
