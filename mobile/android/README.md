# Asseta Android (Gate 0 foundation)

Native Android apps for Asseta: **Supervisor** (`com.asseta.supervisor`, offline-first field app) and
**Owner** (`com.asseta.owner`). Both are thin shells over shared `:core:*` modules so business rules are
never duplicated between them.

Gate 0 delivers only the foundation: secure storage, encrypted database with the outbox table, typed
networking, Keycloak login, `GET /api/v1/me` and tenant selection. Jobs, meter capture, the sync engine,
camera/OCR, GPS and maps arrive in Gates 3, 4 and 7.

## Modules

| Module | Purpose |
| --- | --- |
| `:core:model` | Pure-Kotlin/JVM API DTOs (kotlinx.serialization): `MeResponse`, `TenantAccess`, `TenantAccessState`, `ErrorEnvelope`, strict UUID serializer, `DecimalAmount`/`Money` (decimal string on the wire; floats rejected), `ClientOperationStatus`. |
| `:core:security` | Android Keystore AES-256-GCM key per purpose (`KeystoreSecretCipher`), wrapped-secret file store in `noBackupFilesDir`, SQLCipher passphrase provider (32 random bytes, generated once, never regenerated silently), encrypted token store. |
| `:core:database` | Room + SQLCipher (`SupportOpenHelperFactory`). `client_operation` outbox table + DAO (idempotent enqueue, dependency-aware bounded dispatch, SENT→ACKED only with server revision, FAILED/QUARANTINED visibility). Exported schemas in `core/database/schemas/`, explicit migrations in `AssetaMigrations`, **no destructive fallback**. |
| `:core:network` | OkHttp/Retrofit client. Interceptors: `Authorization: Bearer`, `X-Tenant-ID`, `X-Correlation-ID` (UUID per request), `Idempotency-Key` on POST/PUT/PATCH/DELETE (an explicit key, e.g. the outbox operation id, is preserved), error envelope → `ApiException`. Base URL from `BuildConfig`. Debug-only cleartext to `10.0.2.2`/`localhost`. |
| `:core:auth` | AppAuth Authorization Code + PKCE against Keycloak realm `asseta`, public client `asseta-mobile`; the redirect scheme is supplied per app (see Configuration), never defined in core; token refresh; logout (local clear + Keycloak end-session). `SelectedTenantStore`. Keycloak and the API are authoritative; the app never authorizes locally, it only hides UI. |
| `:core:ui` | Material3 brand theme (Slate `#0F2A3D`, Amber `#F5A300`), launcher adaptive icon (vector conversion of `branding/asseta-mark.svg`), login screen, `/me` + tenant picker, `SessionViewModel`, `AssetaAppContainer` (manual DI). |
| `:app:supervisor`, `:app:owner` | Application, `MainActivity`, manifest (INTERNET only, backups disabled), per-app OIDC redirect scheme (`OIDC_REDIRECT_SCHEME` BuildConfig field + AppAuth `appAuthRedirectScheme` manifest placeholder). |

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
./gradlew assembleDebug testDebugUnitTest lint   # required gate
./gradlew assembleAndroidTest                    # compiles instrumented tests (SQLCipher at-rest test)
./gradlew connectedDebugAndroidTest              # needs an emulator/device
```

`testDebugUnitTest` covers `:core:model` too (alias of its JVM `test` task). The Room DAO tests run under
Robolectric on plain SQLite because SQLCipher's native library is device-only; encryption at rest is verified by
`core/database/src/androidTest/.../EncryptedDatabaseTest.kt`.

## Rules for later gates

- Every schema change: bump `AssetaDatabase.VERSION`, commit the new `schemas/*.json`, add a migration + test.
- Outbox operation `id` is the server `Idempotency-Key`; pass it explicitly on the request.
- Never mark an operation synced before a durable server ACK (`markAcked` requires `SENT`).
- Money is `DecimalAmount`/`Money` (decimal strings); never `Double`/`Float`.
- Add Android permissions (camera, location) only with the feature that needs them.
- Files stay under 500 lines.
