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

All four gates (`lint`, `typecheck`, `test -- --run`, `build`) must pass before merging.

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
