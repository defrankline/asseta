"""Test harness: real PostgreSQL/PostGIS (asseta_test), migrations applied as owner, API runs as the
non-privileged asseta_app role so RLS is genuinely exercised."""

import json
import os

os.environ.setdefault("ASSETA_DATABASE_URL", "postgresql+psycopg://asseta_app:asseta_app@localhost:5432/asseta_test")
os.environ.setdefault(
    "ASSETA_MIGRATION_DATABASE_URL", "postgresql+psycopg://asseta_owner:asseta_owner@localhost:5432/asseta_test"
)
os.environ["ASSETA_KEYCLOAK_URL"] = "http://keycloak.test"

from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from asseta.core.config import get_settings
from asseta.main import create_app
from asseta.modules.identity.tokens import OidcTokenVerifier
from asseta.modules.policy.schemas import SEED_DEFAULTS, PolicyType
from tests.support.api import Api
from tests.support.idp import InMemoryIdp
from tests.support.tokens import AUDIENCE, ISSUER, StaticKeyProvider, TokenFactory

SEED_POLICY = """INSERT INTO entitlement_policy (id, tenant_id, version, effective_from, grace_days, suspend_after_days,
  past_due_access, suspended_access, cancelled_access, reason, created_at) VALUES (gen_random_uuid(), NULL, 1,
  DATE '2000-01-01', 7, 30, 'FULL', 'READ_ONLY', 'READ_ONLY', 'Seeded platform default', now())"""
KEEP = {"currency", "entitlement_policy", "alembic_version", "spatial_ref_sys"}


@pytest.fixture(scope="session")
def owner_engine() -> Iterator[Engine]:
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.attributes["url"] = get_settings().migration_database_url
    command.upgrade(cfg, "head")
    engine = create_engine(get_settings().migration_database_url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_db(owner_engine: Engine) -> None:
    with owner_engine.begin() as conn:
        tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars()
        names = [t for t in tables if t not in KEEP]
        conn.execute(text(f"TRUNCATE {', '.join(names)} CASCADE"))  # cascades into entitlement_policy (FK)
        conn.execute(text("SELECT set_config('app.scope', 'system', true)"))
        conn.execute(text("DELETE FROM entitlement_policy"))
        conn.execute(text(SEED_POLICY))
        conn.execute(text("DELETE FROM policy_version"))
        conn.execute(
            text(
                "INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,"
                " values, reason, created_at, source) VALUES (gen_random_uuid(), 'TRACKING', 'PLATFORM', NULL, NULL, 1,"
                " TIMESTAMPTZ '2000-01-01 00:00:00+00', CAST(:v AS jsonb), 'Seeded platform default', now(), 'migration')"
            ),
            {"v": json.dumps(SEED_DEFAULTS[PolicyType.TRACKING])},
        )


class MutableClock:
    def __init__(self, today: date):
        self.now = datetime.combine(today, time(9, 0), UTC)

    def set(self, d: date) -> None:
        self.now = datetime.combine(d, time(9, 0), UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock(date(2026, 11, 1))


@pytest.fixture
def tokens() -> TokenFactory:
    return TokenFactory()


@pytest.fixture
def idp() -> InMemoryIdp:
    return InMemoryIdp()


@pytest.fixture
def client(tokens: TokenFactory, idp: InMemoryIdp, clock: MutableClock) -> Iterator[TestClient]:
    verifier = OidcTokenVerifier(StaticKeyProvider(tokens.public_key), ISSUER, AUDIENCE)
    app = create_app(token_verifier=verifier, idp_admin=idp)
    app.state.clock = clock
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def api(client: TestClient, tokens: TokenFactory, idp: InMemoryIdp, clock: MutableClock) -> Api:
    return Api(client, tokens, idp, clock)
