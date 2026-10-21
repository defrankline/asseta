# Asseta iOS (Gate 0 foundation)

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
  Apps/SupervisorTests/       Tests hosted in the app (real Keychain, LocalStore with Keychain key)
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
| `AssetaTestSupport` | Test doubles (`MockTransport`, fixtures). Not a product |

### Outbox (`client_operation`)

Columns: `id` (UUID PK, also the idempotency key), `tenant_id`, `op_type`, `entity_type`,
`entity_id`, `payload_json` (must be valid JSON), `depends_on` (FK to the same table, same
tenant), `created_at_device` (UTC ms), `status`, `attempt_count`, `last_error`, `server_revision`.

The repository only allows these status changes:
`PENDING→SENT→ACKED`, `SENT→FAILED→PENDING`, `PENDING/SENT/FAILED→QUARANTINED`.
`ACKED` requires a `server_revision`, and a CHECK constraint enforces that too. `readyToSend`
returns PENDING operations whose dependency is ACKED, oldest first. SENT does not count as
synced. The sync engine (retry/backoff, batching, conflicts, attachments) belongs to Gate 4.

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

# Keychain and file tests hosted in the app (needs the app's default local signing)
xcodebuild -project Asseta.xcodeproj -scheme AssetaSupervisor -destination 'platform=iOS Simulator,name=iPhone 17 Pro' test

# Regenerate the app icon after changing branding/asseta-mark.svg
Scripts/generate-app-icon.sh
```

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

Info.plist has no privacy usage descriptions yet. Camera, location and photos strings will be
added with the features that use them in Gates 3, 4 and 7.

## Security notes

- The database key and tokens stay on this device. They are never backed up and are readable after the first unlock, which lets background sync work later. The database directory is excluded from backups and has `completeUntilFirstUserAuthentication` protection.
- An encryption test shows the database file has no SQLite header and no plaintext, and that it can't be read without the key or with a wrong key.
- The browser session is ephemeral, so no Keycloak SSO cookie stays on the device after sign-out.
- The app stores no permission decisions. `access_state` and the menus only change what the UI shows, and an unknown `access_state` is treated as blocked.
