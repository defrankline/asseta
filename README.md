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
| `infra/` | PostGIS image, Keycloak realm import |
| `docs/` | Architecture, ADRs, security, API conventions, runbook |

## Quickstart (local stack)

```bash
cp .env.example .env            # replace every CHANGE_ME (e.g. openssl rand -base64 32)
docker compose up -d --build    # postgres+postgis, keycloak, kafka, redis, minio, migrate, api, outbox-relay, web
curl -s localhost:8000/api/v1/health/ready      # every dependency "ok"
cd backend && uv run python scripts/compose_smoke.py ../.env   # end-to-end smoke (login → onboard → Kafka)
```

Console: http://localhost:5173 · API docs: http://localhost:8000/api/v1/docs · Keycloak: http://localhost:8080.
Traccar (Gate 2) is in the `telemetry` profile: `docker compose --profile telemetry up -d`.

Users are created in Keycloak (authoritative for authentication **and** authorization). To bootstrap the first
platform owner, create a user in realm `asseta` and add it to group `/platform/platform-owner`
([docs/security.md](docs/security.md)).

## Developing and testing

```bash
cd backend && uv sync && uv run alembic upgrade head && uv run pytest        # needs local Postgres+PostGIS
uv run ruff check src tests migrations scripts && uv run mypy src tests scripts
ASSETA_IT_KEYCLOAK_URL=http://localhost:8080 ASSETA_IT_KAFKA=localhost:29192 uv run pytest -m integration
cd web && npm ci && npm run lint && npm run typecheck && npm test -- --run && npm run build
cd mobile/android && ./gradlew assembleDebug testDebugUnitTest lint
cd mobile/ios && xcodegen generate && (cd AssetaKit && swift test)
```

After changing API DTOs: `cd backend && uv run python scripts/export_openapi.py && cd ../web && npm run gen:api`.
