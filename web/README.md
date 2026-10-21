# Asseta web console

React 19 + Vite 8 + TypeScript 5.9 (strict, `noUncheckedIndexedAccess`) admin console for the
Platform console (platform scopes) and the Tenant console (tenant scopes). Node 24, npm.

## Commands

| Command                           | Purpose                                                                                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `npm ci`                          | Install exact pinned versions from `package-lock.json`                                                                                     |
| `npm run dev`                     | Dev server on http://localhost:5173 (proxies `/api` to `VITE_DEV_API_PROXY_TARGET`, default http://localhost:8000)                         |
| `npm run lint`                    | ESLint (typescript-eslint `strictTypeChecked`, no `any`, no `@ts-ignore`, max 500 lines/file, no direct `axios` imports outside `src/api`) |
| `npm run typecheck`               | `tsc --noEmit`                                                                                                                             |
| `npm test -- --run`               | Vitest + Testing Library (single run; omit `--run` for watch)                                                                              |
| `npm run build`                   | Typecheck + production build to `dist/`                                                                                                    |
| `npm run format` / `format:check` | Prettier                                                                                                                                   |
| `npm run gen:api`                 | Generate `src/api/generated/schema.ts` from `../contracts/openapi.json` (openapi-typescript)                                               |

All gates (`lint`, `typecheck`, `test -- --run`, `build`, `format:check`) must pass before merging.

## Configuration

Copy `.env.example` to `.env.local`. Variables: `VITE_KEYCLOAK_URL` (default http://localhost:8080),
`VITE_KEYCLOAK_REALM` (`asseta`), `VITE_KEYCLOAK_CLIENT_ID` (`asseta-web`, public PKCE client),
`VITE_API_BASE_URL` (`/api/v1`), `VITE_DEV_API_PROXY_TARGET` (dev only), `VITE_MAP_STYLE_URL`.
The Keycloak client must allow redirect URI `http://localhost:5173/*` and web origin
`http://localhost:5173`; silent SSO uses `public/silent-check-sso.html`.

## Architecture

- `src/api` — the only place that touches Axios. `client.ts` holds the single instance and
  interceptors: `Authorization: Bearer`, `X-Correlation-ID` (fresh UUID v4 per request),
  `X-Tenant-ID` when a call passes `tenantScoped: true`, `Idempotency-Key` (required on
  POST/PUT/PATCH/DELETE; create one per user intent with `newIdempotencyKey()` and reuse it on
  retry). Every failure becomes a typed `ApiError` parsed from the error envelope; 401 triggers
  re-login. Services (`api/services/*`) validate responses at runtime with Yup.
- `src/auth` — keycloak-js (`check-sso`, PKCE S256, silent refresh 30 s before expiry, logout).
- `src/session` — `SessionProvider` loads `GET /me`, holds the console mode (Platform or a tenant),
  effective permissions and the tenant `access_state`. Platform and tenant permissions never mix.
  BLOCKED tenants grant nothing client-side; READ_ONLY tenants show a banner and expose
  `isReadOnly` for hiding mutating actions. The API remains authoritative.
- `src/access` — `RequirePermission` (route guard → `/403`) and `<Can>`; both deny by default
  (no session, empty requirement or missing code ⇒ denied). Every feature route must be wrapped.
  Exceptions: My access (own `/me` data), 403, 404.
- `src/components` — reusable atoms: `FormDialog`, `StepperFormDialog` (ends with Review; use for
  forms with more than 3 fields), `ConfirmDialog`, `FormikTextField`, `DateTimeField` (UTC ISO in/out,
  displays in a given IANA zone), `ServerDataTable` (server page/sort/filter + debounced search),
  `AsyncAutocomplete`, `MapView` (MapLibre), `PageHeader`, `EmptyState`, `ErrorState`, `LoadingState`.
  Toasts via `useNotify()`.

## Frontend conventions: dropdowns (non-negotiable)

**Never use `TextField select` + `MenuItem` (or `FormikSelectField`) for options that come from
the backend.** Tenants, platform staff, roles, machines, categories, operating areas, customers,
contracts, jobs, job sites, staff, tracker models, trackers, geofences — anything fetched — use the
shared, generic, debounced server-search autocompletes:

- `components/data/AsyncAutocomplete` (single, holds the option object; list-page filters),
  `components/data/AsyncMultiAutocomplete` (multi, chips).
- `components/forms/FormikAsyncIdAutocomplete` — Formik field that **stores the id** but shows and
  searches by label; `resolveOption(id)` loads the label of an id already in an edit form;
  `onOptionChange` exposes the picked record (e.g. for the Review step).
  `components/forms/FormikAsyncAutocomplete` stores the option object instead.
- `fetchOptions(query, signal)` must pass the typed text to the API as its search parameter (`q`)
  and request one page (`LOOKUP_PAGE_SIZE`); never fetch everything and filter in the browser.
  Domain pickers live in `pages/tenant/shared/{lookups.ts,lookupPickers.tsx,pickers.tsx,MachinePicker.tsx}`
  and `pages/platform/shared/platformLookups.ts`. "No matches", "Searching…" and request errors
  are shown by the shared component.

Static enums defined in code (status, kind, method, scope, cadence, currency, outcome…) may use
`FormikSelectField` / `StaticSelectFilter` / a select, and `FormikAutocompleteField` takes static
string lists (e.g. timezones). Their option arrays are **module-level ALL_CAPS constants**
(`STATUS_OPTIONS`), or a static lookup keyed by state (`STATE_TARGET_OPTIONS[state]`).

ESLint enforces this (`eslint/dropdownRules.js`, `no-restricted-syntax`): it fails on a `<MenuItem>`
rendered inside `.map()` whose receiver is not an ALL_CAPS constant, and on
`<FormikSelectField|StaticSelectFilter options={x}>` where `x` is not one. The guard has a test
(`src/test/dropdownLintGuard.test.ts`). A disable comment needs a `--` justification and is only for
non-form navigation or code-defined data (today: the header tenant switcher over the user's own
`/me` contexts, which shows a search box above 8 entries, and the policy field enum inputs).

## MUI + Tailwind coexistence

Chosen strategy: **CSS cascade layers, no Tailwind preflight**. `src/index.css` declares
`@layer theme, base, mui, components, utilities;` and imports only Tailwind's `theme` and
`utilities` (preflight is omitted; MUI `CssBaseline` is the reset). MUI/Emotion styles are emitted
into `@layer mui` via `<StyledEngineProvider enableCssLayer>`, so Tailwind utilities override MUI
without `!important`. Use Tailwind for layout/spacing, MUI for components and theming.

## API types

DTOs are aliases of the generated contract types (`src/api/generated/schema.ts`, from
`../contracts/openapi.json` via `npm run gen:api`) declared in `src/api/types.ts`; no hand-written
duplicates. Services in `src/api/services/*` validate responses at runtime with Yup schemas typed
against those aliases (`billingSchemas.ts` for platform billing/tenancy), so contract drift fails
`npm run typecheck`.

## Platform console (Gate 1)

Routes (each wrapped in `RequirePermission`; menus come from `/me` `platform_menus`):
`/platform` dashboard (`platform.dashboard.read`), `/platform/tenants` and
`/platform/tenants/:tenantId` (`platform.tenant.read`; subscription section needs
`platform.subscription.read`), `/platform/invoices` (`platform.invoice.read`), `/platform/payments`
(`platform.payment.read`), `/platform/system` (`platform.system.read`). Actions are hidden with `<Can>`.

- **Money** is a 4-dp decimal string end to end. `src/utils/money.ts` formats, rounds and compares
  with BigInt (never floats) using the currency's minor units (TZS/USD/KES/EUR 2, UGX 0); form
  inputs stay strings and are sent as strings. Amounts in different currencies are never summed.
- **Idempotency:** dialogs are mounted only while open and use `useIdempotencyKey()`: one key per
  open, reused when the same payload is retried, rotated when the payload changes (the API rejects a
  reused key with a different body).
- Generic pieces: `MoneyText`, `StatusChip`, `KeyValueGrid`, `CopyButton` (`components/display`),
  `StaticTable`, `AsyncContent`, `FormikSelectField`, `FormikDateField` (MUI DatePicker, ISO date),
  `FormikAutocompleteField`; `useAsyncResource` for loading/error/reload state.

## Tenant console (Gate 2)

Routes match the backend tenant menu paths (menus come from `/me` tenant menus) and are wrapped in
`RequirePermission`; pages are lazy-loaded (`src/routes/lazyPages.ts`) so MapLibre is its own chunk.
Mutating actions use `<CanMutate>` / `useCanMutate()` — permission **and** tenant not READ_ONLY.

| Route                             | Read permission        | Actions                                                               |
| --------------------------------- | ---------------------- | --------------------------------------------------------------------- |
| `/tenant/fleet`                   | `tenant.fleet.read`    | —                                                                     |
| `/tenant/machines`, `/:machineId` | `tenant.machine.read`  | `tenant.machine.write`, `tenant.billing.enroll`, `tenant.staff.write` |
| `/tenant/staff`                   | `tenant.staff.read`    | `tenant.staff.write`                                                  |
| `/tenant/trackers`                | `tenant.tracker.read`  | `tenant.tracker.write`                                                |
| `/tenant/geofences`               | `tenant.geofence.read` | `tenant.geofence.write`                                               |
| `/tenant/alerts`                  | `tenant.fleet.read`    | `tenant.fleet.alert_manage`                                           |
| `/tenant/policies`                | `tenant.policy.read`   | `tenant.policy.manage`                                                |
| `/tenant/subscription`            | `tenant.billing.read`  | — (read-only)                                                         |

- **Services:** one per resource in `src/api/services` (`machineService`, `staffService`,
  `trackerService`, `fleetService`, `geofenceService`, `alertService`, `policyService`,
  `tenantBillingService`); all calls are `tenantScoped` (`X-Tenant-ID`) via `tenantRequest.ts`, and
  responses are Yup-validated (`fleetSchemas`, `trackerSchemas`, `geoSchemas`, built from `schemaKit`).
- **Time:** instants are UTC ISO from the API and shown with `formatInstantIn(…, tz)` where
  `tz = useDisplayTimeZone()`. `/me` does not expose the tenant timezone yet, so this is the browser
  zone; positions always show an age (`AgeText`, `formatAge`, ticking via `useNow`).
- **Never stale as live:** `components/fleet/connectivity.ts#markerStyle` styles a marker as live only
  for `connectivity === 'LIVE' && is_live`; everything else is "last known" (hollow / faded / greyed)
  and labelled so. Status is four independent dimensions (`StatusDimensions`), `UNKNOWN` shown
  explicitly.
- **Map:** `MapView` provides the loaded map to children (`MapContext`): `GeoJsonLayer` (declarative
  source + layers, in-place `setData`), `FitBounds`, `useMapClick`, `FleetMarkersLayer`, and
  `DrawPolygonControl` (plain MapLibre click handlers; polygon rings are closed by `closeRing`,
  corridors are a LineString + width). Tests mock `maplibre-gl` at the module boundary with
  `src/test/maplibreMock.ts` (fire `lastMap().click(lon, lat)` / `clickLayer(id, props)`).
- **Formik note:** Formik passes `''` to Yup as `undefined`; optional strings use `.default('')` /
  `.ensure()` rather than `.defined()`.

## Tenant console (Gate 3: jobs and hour-meter evidence)

| Route                     | Read permission        | Actions                                                                                                                           |
| ------------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `/tenant/customers`       | `tenant.customer.read` | `tenant.customer.write` (customers, contracts, rate-card versions)                                                                |
| `/tenant/jobs`, `/:jobId` | `tenant.job.read`      | create/SUBMIT `tenant.job.write`; APPROVE/CANCEL `tenant.job.approve`; START/COMPLETE, work log, acknowledgement `tenant.job.log` |
| (job) Readings & evidence | `tenant.meter.read`    | console reading `tenant.meter.capture`                                                                                            |
| (job) Meter resets        | —                      | request `tenant.meter.capture`; decide `tenant.meter.approve`                                                                     |
| `/tenant/exceptions`      | `tenant.meter.read`    | review `tenant.meter.review`                                                                                                      |
| `/tenant/policies`        | `tenant.policy.read`   | TRACKING, METER_CAPTURE, HIRE_BILLING versions with `tenant.policy.manage`                                                        |

- **Services:** `customerService`, `jobService`, `meterService` (schemas in `jobSchemas`, `meterSchemas`).
- **Hours:** `HoursComparison` always shows meter hours, non-billable hours and billable hours separately;
  meter (engine) hours are never presented as billable hours. Decimal strings are shown as sent.
- **Evidence components** (`components/meter`): `CaptureStateChip`, `GpsEvidence`, `TrackerComparison`
  (shows "No tracker position within comparison window" when not compared), `CaptureLocationMap`,
  `EvidenceKeyValues` + `exceptionText.ts` (neutral, per-type explanations: exceptions "require review",
  never a verdict), `AttachmentUpload`, `AttachmentPhoto` (fetches the short-lived URL on demand).
- **Console reading** (fallback; mobile apps are the primary capture path): the capture `id` is a UUID
  generated once per dialog open (retries replay, never duplicate); `utils/geolocation.ts` attempts one
  fresh browser fix and submits its real outcome (`FIX` with coordinates/accuracy/fix time, or
  `PERMISSION_DENIED` / `TIMEOUT` / `NO_FIX` / `DISABLED` with no coordinates). The effective
  METER_CAPTURE policy (required mode for this reading) is shown before submitting. No OCR runs in
  the console.
- **Retry safety:** work-log entries and acknowledgements carry a `client_id` UUID fixed per dialog open.
- **Lists:** rate-card versions per category (`listRateCards`; newest first, labelled In force /
  Scheduled / Superseded), the machine's meter resets (`listMeterResets`; approvers pick a PENDING
  reset — Decide is disabled on resets the user requested, and SEGREGATION_OF_DUTIES from the server is
  still shown) and job acknowledgements (`listJobAcknowledgements`) all come from the API.
- **Photos and maps:** capture photos, reset evidence and signatures open through `AttachmentPhoto`
  (getAttachmentUrl, fetched on demand); the SHA-256 is shown as secondary info. `CaptureLocationMap`
  draws the phone fix and the tracker position at the same time (each with its accuracy) and the
  allowed-distance ring.
