<p align="center"><img src="branding/asseta-logo.svg" alt="Asseta" height="56"></p>

# Asseta — Release 1

AI-native, offline-first, multi-tenant heavy-equipment rental, utilization and fraud-control SaaS.
Scope is **frozen** in [`prompt.md`](prompt.md); progress and evidence live in [`track.md`](track.md);
everything else goes to [`backlog.md`](backlog.md).

| Path | What |
|---|---|
| `backend/` | Python 3.13 / FastAPI modular monolith + workers (SQLAlchemy 2.1, Alembic, PostGIS, Kafka outbox) |
| `web/` | React 19 + strict TypeScript admin console (MUI, Tailwind, Formik/Yup, Axios, keycloak-js) |
| `mobile/android/` | Kotlin/Compose Supervisor + Owner apps (Room + SQLCipher, AppAuth) |
| `mobile/ios/` | SwiftUI Supervisor + Owner apps (AssetaKit, SQLCipher, ASWebAuthenticationSession) |
| `contracts/openapi.json` | Versioned API contract (generated; CI fails on drift) |
| `infra/` | PostGIS image + DB role init, Keycloak realm import + login theme, MLflow image |
| `docs/` | Architecture, ADRs, security, API conventions, offline sync, GPS commissioning, runbook, model governance, release acceptance |

## Quickstart (local stack)

```bash
cp .env.example .env            # replace every CHANGE_ME (e.g. openssl rand -base64 32); gateway key >= 24 chars
docker compose --profile telemetry up -d --build
# postgres+postgis, keycloak, kafka, redis, minio, mlflow, mailpit, traccar (telemetry profile),
# one-shot migrate + mlflow-db-init, api, web and the workers: outbox-relay, timeline-, connectivity-,
# intelligence-, notification-worker, notification-scheduler, billing-scheduler
docker compose ps                                # migrate/mlflow-db-init Exited (0); the rest Up / healthy
curl -s localhost:8000/api/v1/health/ready      # every dependency "ok"
cd backend && uv run python scripts/compose_smoke.py ../.env   # end-to-end smoke (login → onboard → Traccar → Kafka → mandate)
```

The smoke test needs the `telemetry` profile (it sends simulated OsmAnd fixes to Traccar on port 5055); it creates a
throwaway "Smoke Test" tenant, which can be removed with `scripts/purge_tenants.py` (see the runbook).

Console: http://localhost:5173 · API docs: http://localhost:8000/api/v1/docs · Keycloak: http://localhost:8080 ·
MLflow: http://localhost:5500 · Mailpit (dev e-mail): http://localhost:8025 · Traccar UI: http://localhost:8082.
Optional demo tenant: `cd backend && uv run python scripts/demo_seed.py ../.env ../.demo/credentials.json`
([runbook §9](docs/operating-runbook.md#9-local-demo-baseline-dev-only-destructive)).

Users are created in Keycloak (authoritative for authentication **and** authorization). To bootstrap the first
platform owner, create a user in realm `asseta` and add it to group `/platform/platform-owner`
([docs/security.md](docs/security.md)); in production use `scripts/create-platform-owner.sh`.

## Production (https://asseta.co.tz)

Shared-server deployment behind host nginx + certbot: `compose.prod.yaml`, `deploy/` (nginx site templates, console
build) and `scripts/*-live.sh`. Step by step, including secrets, the first platform owner, backups, rollback and
tracker ports: [docs/deployment-live.md](docs/deployment-live.md).

```bash
scripts/generate-production-secrets.sh && $EDITOR .env.production   # fill LETSENCRYPT_EMAIL (+ SMTP/SMS/push later)
scripts/deploy-live.sh                                              # every update: same command
scripts/create-platform-owner.sh you@example.com "First" "Last"
```

## Developing and testing

Backend tests need a PostgreSQL 18 + PostGIS on `localhost:5432` with database `asseta_test` and roles
`asseta_owner`/`asseta_app` (password = role name), created exactly as in `.github/workflows/ci.yml`
("Create least-privilege roles and test database"); override with `ASSETA_DATABASE_URL` /
`ASSETA_MIGRATION_DATABASE_URL`. `scripts/ci-local.sh` runs the same gates as CI.

```bash
cd backend && uv sync && uv run pytest        # migrations are applied by the test session
uv run ruff check src tests migrations scripts && uv run mypy src tests scripts
ASSETA_IT_KEYCLOAK_URL=http://localhost:8080 ASSETA_IT_KAFKA=localhost:29192 uv run pytest -m integration
cd web && npm ci && npm run lint && npm run typecheck && npm test -- --run && npm run build
cd mobile/android && ./gradlew assembleDebug testDebugUnitTest lint
cd mobile/ios && xcodegen generate && (cd AssetaKit && swift test)
```

After changing API DTOs: `cd backend && uv run python scripts/export_openapi.py && cd ../web && npm run gen:api`.

## Documentation

[Architecture](docs/architecture.md) · [ADRs](docs/adr/) · [API conventions](docs/api.md) ·
[Offline sync](docs/offline-sync.md) · [GPS hardware commissioning](docs/gps-hardware.md) ·
[Security](docs/security.md) · [Operating runbook](docs/operating-runbook.md) (deployment, backup/restore,
incidents, drills) · [Live deployment](docs/deployment-live.md) · [Model governance](docs/model-governance.md) · [OCR metrics](docs/ml-ocr-metrics.md) ·
[Release 1 acceptance](docs/release1-acceptance.md)
