"""RLS tenant isolation, immutability/append-only guards, sequences, grants and seed configuration.

Revision ID: b1sec0000001
Revises: 44caeb5fa0e9
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b1sec0000001"
down_revision: str | None = "44caeb5fa0e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "asseta_app"

# Tenant business data: only the owning tenant (or audited internal system workers).
TENANT_OWNED = ["machine"]
# Platform commercial data: platform/system write; tenant may read only its own rows.
PLATFORM_OWNED_TENANT_READ = [
    "commercial_agreement",
    "subscription_rate_version",
    "tenant_subscription",
    "subscription_status_event",
    "entitlement_event",
    "platform_invoice",
    "platform_invoice_line",
    "platform_payment",
    "credit_adjustment",
]
# Enrollment changes originate from the tenant (its machines) and from the platform.
SHARED_WRITE = ["subscription_asset_enrollment", "subscription_pending_charge", "tenant_settings"]
PLATFORM_ONLY = ["entitlement_policy"]
# Append-only / immutable records (no UPDATE/DELETE for the application role, trigger-enforced for all).
IMMUTABLE = [
    "audit_event",
    "platform_invoice_line",
    "subscription_rate_version",
    "subscription_status_event",
    "entitlement_event",
    "credit_adjustment",
]
NO_DELETE = [
    "platform_invoice",
    "platform_payment",
    "subscription_asset_enrollment",
    "subscription_pending_charge",
    "tenant_subscription",
    "commercial_agreement",
    "machine",
    "tenant",
]


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS platform_invoice_number_seq")
    op.execute("CREATE SEQUENCE IF NOT EXISTS commercial_agreement_number_seq")
    op.execute("""
        CREATE FUNCTION app_scope() RETURNS text LANGUAGE sql STABLE AS
        $$ SELECT coalesce(current_setting('app.scope', true), '') $$;
        CREATE FUNCTION app_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;
        CREATE FUNCTION reject_mutation() RETURNS trigger LANGUAGE plpgsql AS
        $$ BEGIN RAISE EXCEPTION 'asseta: % on % is not permitted (immutable record)', TG_OP, TG_TABLE_NAME
           USING ERRCODE = 'insufficient_privilege'; END $$;
        CREATE FUNCTION guard_platform_invoice() RETURNS trigger LANGUAGE plpgsql AS
        $$ BEGIN
             IF (NEW.tenant_id, NEW.subscription_id, NEW.rate_version_id, NEW.invoice_number, NEW.period_start,
                 NEW.period_end, NEW.currency, NEW.billable_assets, NEW.enrolled_assets, NEW.subtotal,
                 NEW.discount_total, NEW.tax_total, NEW.total, NEW.issued_at, NEW.due_date)
                IS DISTINCT FROM
                (OLD.tenant_id, OLD.subscription_id, OLD.rate_version_id, OLD.invoice_number, OLD.period_start,
                 OLD.period_end, OLD.currency, OLD.billable_assets, OLD.enrolled_assets, OLD.subtotal,
                 OLD.discount_total, OLD.tax_total, OLD.total, OLD.issued_at, OLD.due_date) THEN
               RAISE EXCEPTION 'asseta: issued invoice snapshot is immutable' USING ERRCODE = 'insufficient_privilege';
             END IF;
             RETURN NEW;
           END $$;
    """)
    op.execute("""CREATE TRIGGER trg_platform_invoice_immutable BEFORE UPDATE ON platform_invoice
                  FOR EACH ROW EXECUTE FUNCTION guard_platform_invoice()""")
    for table in IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )

    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT USAGE ON SCHEMA public TO {APP_ROLE};
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};
            REVOKE UPDATE, DELETE ON {", ".join(IMMUTABLE)} FROM {APP_ROLE};
            REVOKE DELETE ON {", ".join(NO_DELETE)} FROM {APP_ROLE};
            REVOKE INSERT, UPDATE, DELETE ON currency, alembic_version FROM {APP_ROLE};
          END IF;
        END $$;
    """)

    platform = "app_scope() IN ('platform', 'system')"
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for table in TENANT_OWNED + PLATFORM_OWNED_TENANT_READ + SHARED_WRITE + PLATFORM_ONLY:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for table in TENANT_OWNED:
        op.execute(
            f"CREATE POLICY p_tenant ON {table} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    for table in PLATFORM_OWNED_TENANT_READ + SHARED_WRITE + PLATFORM_ONLY:
        op.execute(f"CREATE POLICY p_platform ON {table} USING ({platform}) WITH CHECK ({platform})")
    for table in PLATFORM_OWNED_TENANT_READ:
        op.execute(f"CREATE POLICY p_tenant_read ON {table} FOR SELECT USING ({own})")
    for table in SHARED_WRITE:
        op.execute(f"CREATE POLICY p_tenant ON {table} USING ({own}) WITH CHECK ({own})")

    # Audit: anyone may append; platform sees only platform/billing actions, never tenant business audit.
    op.execute("ALTER TABLE audit_event ENABLE ROW LEVEL SECURITY; ALTER TABLE audit_event FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY p_insert ON audit_event FOR INSERT WITH CHECK (true)")
    op.execute(f"""CREATE POLICY p_read ON audit_event FOR SELECT USING (
        app_scope() = 'system' OR {own}
        OR (app_scope() = 'platform' AND (action LIKE 'platform.%' OR action LIKE 'billing.%')))""")

    op.execute("""
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO currency (code, name, minor_units) VALUES
          ('TZS', 'Tanzanian Shilling', 2), ('USD', 'US Dollar', 2), ('KES', 'Kenyan Shilling', 2),
          ('UGX', 'Ugandan Shilling', 0), ('EUR', 'Euro', 2)
        ON CONFLICT (code) DO NOTHING;
        INSERT INTO entitlement_policy (id, tenant_id, version, effective_from, grace_days, suspend_after_days,
          past_due_access, suspended_access, cancelled_access, reason, created_at)
        SELECT gen_random_uuid(), NULL, 1, DATE '2000-01-01', 7, 30, 'FULL', 'READ_ONLY', 'READ_ONLY',
          'Seeded platform default (replaceable configuration)', now()
        WHERE NOT EXISTS (SELECT 1 FROM entitlement_policy WHERE tenant_id IS NULL AND version = 1);
    """)


def downgrade() -> None:
    for table in ["audit_event", *TENANT_OWNED, *PLATFORM_OWNED_TENANT_READ, *SHARED_WRITE, *PLATFORM_ONLY]:
        op.execute(
            f"DROP POLICY IF EXISTS p_tenant ON {table}; DROP POLICY IF EXISTS p_platform ON {table};"
            f"DROP POLICY IF EXISTS p_tenant_read ON {table}; DROP POLICY IF EXISTS p_insert ON {table};"
            f"DROP POLICY IF EXISTS p_read ON {table}; ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;"
            f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"
        )
    for table in IMMUTABLE:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
    op.execute("DROP TRIGGER IF EXISTS trg_platform_invoice_immutable ON platform_invoice")
    # Seeds stay when referenced by business data (re-upgrade is idempotent); tables go with the baseline revision.
    op.execute(
        "DELETE FROM entitlement_policy p WHERE tenant_id IS NULL AND version = 1 AND NOT EXISTS ("
        "SELECT 1 FROM entitlement_event e WHERE e.policy_id = p.id)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS guard_platform_invoice(); DROP FUNCTION IF EXISTS reject_mutation();"
        "DROP FUNCTION IF EXISTS app_tenant_id(); DROP FUNCTION IF EXISTS app_scope();"
    )
    op.execute(
        "DROP SEQUENCE IF EXISTS commercial_agreement_number_seq; DROP SEQUENCE IF EXISTS platform_invoice_number_seq"
    )
