"""DEC-031 Phase 4 (prepaid hours used over days and weeks): daily drawdown ledger entries (P1) and low-balance
alerts (P2).

- `hours_ledger_entry.entry_type` widened to 24 characters for PROVISIONAL / PROVISIONAL_REVERSED; new nullable
  `usage_day` (tenant-local day of a provisional draw). The ledger stays append-only.
- `hours_low_balance_alert`: one row per threshold crossing of a purchase; only the re-arm stamp and the customer SMS
  status may change later (guard trigger), never deleted; tenant FORCE RLS (system scope for the scheduler).
- New CUSTOMER_HOURS keys (`drawdown` AT_COMPLETION, `low_balance_hours` null, `low_balance_notify_customer` false)
  are added to the platform default as a new platform version (previous values carried over), so every tenant keeps
  today's behaviour.

Revision ID: dec31p4hrs01
Revises: dec31p2ast01
Create Date: 2026-10-26 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dec31p4hrs01"
down_revision: str | Sequence[str] | None = "dec31p2ast01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALERT = "hours_low_balance_alert"
NEW_KEYS = '{"drawdown": "AT_COMPLETION", "low_balance_hours": null, "low_balance_notify_customer": false}'
SEED_REASON = "Seeded platform default: DEC-031 daily drawdown and low-balance warning off (replaceable configuration)"


def upgrade() -> None:
    op.alter_column("hours_ledger_entry", "entry_type", type_=sa.String(length=24), existing_type=sa.String(length=16))
    op.add_column("hours_ledger_entry", sa.Column("usage_day", sa.Date(), nullable=True))
    op.create_index("ix_hours_ledger_job_type", "hours_ledger_entry", ["job_id", "entry_type"], unique=False)

    op.create_table(
        ALERT,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("purchase_id", sa.UUID(), sa.ForeignKey("hours_purchase.id"), nullable=False),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("machine_id", sa.UUID(), sa.ForeignKey("machine.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("threshold_hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("remaining_hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("available_hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("crossed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notify_customer", sa.Boolean(), nullable=False),
        sa.Column("customer_sms_status", sa.String(length=16), nullable=False),
        sa.Column("customer_sms_id", sa.UUID(), nullable=True),
        sa.Column("rearmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_id", "sequence", name="uq_hours_low_balance_alert_sequence"),
        sa.CheckConstraint(
            "customer_sms_status IN ('NOT_REQUESTED', 'PENDING', 'QUEUED', 'NO_PHONE')",
            name="ck_hours_low_balance_alert_sms",
        ),
    )
    op.create_index(op.f(f"ix_{ALERT}_tenant_id"), ALERT, ["tenant_id"], unique=False)
    op.create_index(op.f(f"ix_{ALERT}_purchase_id"), ALERT, ["purchase_id"], unique=False)
    op.create_index(op.f(f"ix_{ALERT}_customer_id"), ALERT, ["customer_id"], unique=False)
    op.create_index(
        "uq_hours_low_balance_alert_armed",
        ALERT,
        ["purchase_id"],
        unique=True,
        postgresql_where=sa.text("rearmed_at IS NULL"),
    )

    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    op.execute(f"ALTER TABLE {ALERT} ENABLE ROW LEVEL SECURITY; ALTER TABLE {ALERT} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY p_tenant ON {ALERT} USING ({own} OR app_scope() = 'system') "
        f"WITH CHECK ({own} OR app_scope() = 'system')"
    )
    op.execute(f"""
        CREATE FUNCTION guard_hours_low_balance_alert() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE'
             OR (OLD.rearmed_at IS NOT NULL AND NEW.rearmed_at IS DISTINCT FROM OLD.rearmed_at)
             OR (to_jsonb(NEW) - ARRAY['rearmed_at', 'customer_sms_status', 'customer_sms_id'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['rearmed_at', 'customer_sms_status', 'customer_sms_id']) THEN
            RAISE EXCEPTION 'asseta: a low-balance alert is a record of fact (only re-arming and SMS status change)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_{ALERT}_guard BEFORE UPDATE OR DELETE ON {ALERT}
          FOR EACH ROW EXECUTE FUNCTION guard_hours_low_balance_alert();
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {ALERT} FROM asseta_app; GRANT SELECT, INSERT, UPDATE ON {ALERT} TO asseta_app;
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                    values, reason, created_at, source)
        SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
               (SELECT max(version) + 1 FROM policy_version
                 WHERE policy_type = 'CUSTOMER_HOURS' AND scope = 'PLATFORM' AND tenant_id IS NULL),
               cur.effective_from, cur.values || '{NEW_KEYS}'::jsonb, '{SEED_REASON}', now(), 'migration'
          FROM (SELECT policy_type, effective_from, values FROM policy_version
                 WHERE policy_type = 'CUSTOMER_HOURS' AND scope = 'PLATFORM' AND tenant_id IS NULL
                   AND effective_from <= now()
                 ORDER BY effective_from DESC, version DESC LIMIT 1) cur
         WHERE NOT (cur.values ? 'drawdown');
    """)


def downgrade() -> None:
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
        DELETE FROM policy_version
         WHERE policy_type = 'CUSTOMER_HOURS' AND scope = 'PLATFORM' AND source = 'migration'
           AND reason = '{SEED_REASON}';
        ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
        DROP POLICY IF EXISTS p_tenant ON {ALERT};
        DROP TRIGGER IF EXISTS trg_{ALERT}_guard ON {ALERT};
        DROP FUNCTION IF EXISTS guard_hours_low_balance_alert();
        ALTER TABLE hours_ledger_entry DISABLE TRIGGER USER;
        DELETE FROM hours_ledger_entry WHERE entry_type IN ('PROVISIONAL', 'PROVISIONAL_REVERSED');
        ALTER TABLE hours_ledger_entry ENABLE TRIGGER USER;
    """)
    op.drop_table(ALERT)
    op.drop_index("ix_hours_ledger_job_type", table_name="hours_ledger_entry")
    op.drop_column("hours_ledger_entry", "usage_day")
    op.alter_column("hours_ledger_entry", "entry_type", type_=sa.String(length=16), existing_type=sa.String(length=24))
