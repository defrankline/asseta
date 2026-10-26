"""DEC-031 Phase 3 (money reaches the owner): company deposit accounts (D1); remittance method, deposit account and
evidence photos (D2); the remote-site holding allowance flag reason on `cash_remittance_overdue` (D3).

New CASH_CUSTODY keys (`remittance_reference_required`, `remittance_evidence_required`, `remittance_account_required`
all false; `max_holding_days` null) are added to the platform default as a new platform version (policy versions are
immutable; the previous platform values are carried over unchanged), so every tenant keeps today's behaviour.

Security: tenant-owned FORCE RLS and explicit grants; evidence links append-only (reject_mutation); deposit accounts
are never deleted (deactivated) and carry a sync revision for the field apps' account picker.

Revision ID: dec31p3dep01
Revises: capsw0000001
Create Date: 2026-10-26 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dec31p3dep01"
down_revision: str | Sequence[str] | None = "capsw0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNT = "company_deposit_account"
EVIDENCE = "remittance_evidence"
OVERDUE = "cash_remittance_overdue"
NEW_KEYS = (
    '{"remittance_reference_required": false, "remittance_evidence_required": false, '
    '"remittance_account_required": false, "max_holding_days": null}'
)
SEED_REASON = "Seeded platform default: DEC-031 remittance controls off (replaceable configuration)"


def upgrade() -> None:
    op.create_table(
        ACCOUNT,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "account_type",
            sa.Enum("BANK", "MOBILE_MONEY", "CASH_OFFICE", name="depositaccounttype", native_enum=False, length=24),
            nullable=False,
        ),
        sa.Column("institution", sa.String(length=120), nullable=True),
        sa.Column("account_number_masked", sa.String(length=40), nullable=True),
        sa.Column("currency", sa.String(length=3), sa.ForeignKey("currency.code"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.UUID(), nullable=True),
        sa.Column("deactivation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "sync_revision", sa.BigInteger(), server_default=sa.text("nextval('sync_revision_seq')"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("char_length(name) >= 2", name="ck_company_deposit_account_name"),
    )
    op.create_index(op.f(f"ix_{ACCOUNT}_tenant_id"), ACCOUNT, ["tenant_id"], unique=False)
    op.create_index(op.f(f"ix_{ACCOUNT}_sync_revision"), ACCOUNT, ["sync_revision"], unique=False)
    op.create_index("uq_company_deposit_account_name", ACCOUNT, ["tenant_id", sa.text("lower(name)")], unique=True)

    op.create_table(
        EVIDENCE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("handover_id", sa.UUID(), sa.ForeignKey("cash_handover.id"), nullable=False),
        sa.Column("attachment_id", sa.UUID(), sa.ForeignKey("capture_attachment.id"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handover_id", "attachment_id", name="uq_remittance_evidence"),
    )
    op.create_index(op.f(f"ix_{EVIDENCE}_tenant_id"), EVIDENCE, ["tenant_id"], unique=False)
    op.create_index(op.f(f"ix_{EVIDENCE}_handover_id"), EVIDENCE, ["handover_id"], unique=False)

    op.add_column(
        "cash_handover",
        sa.Column(
            "method",
            sa.Enum(
                "CASH_TO_OFFICE", "BANK_DEPOSIT", "MOBILE_MONEY", name="remittancemethod", native_enum=False, length=24
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "cash_handover",
        sa.Column("deposit_account_id", sa.UUID(), sa.ForeignKey(f"{ACCOUNT}.id"), nullable=True),
    )

    op.add_column(
        OVERDUE,
        sa.Column(
            "reason",
            sa.Enum("CUTOFF", "HELD_TOO_LONG", name="overduereason", native_enum=False, length=24),
            server_default="CUTOFF",
            nullable=False,
        ),
    )
    op.add_column(OVERDUE, sa.Column("held_since", sa.DateTime(timezone=True), nullable=True))
    op.add_column(OVERDUE, sa.Column("max_holding_days", sa.Integer(), nullable=True))
    op.drop_constraint("uq_cash_remittance_overdue_day", OVERDUE, type_="unique")
    op.create_unique_constraint(
        "uq_cash_remittance_overdue_day_reason", OVERDUE, ["tenant_id", "staff_member_id", "local_day", "reason"]
    )

    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for t in (ACCOUNT, EVIDENCE):
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {t} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    op.execute(f"""
        CREATE TRIGGER trg_{EVIDENCE}_immutable BEFORE UPDATE OR DELETE ON {EVIDENCE}
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
        CREATE TRIGGER trg_{ACCOUNT}_no_delete BEFORE DELETE ON {ACCOUNT}
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
        CREATE TRIGGER trg_{ACCOUNT}_sync_revision BEFORE UPDATE ON {ACCOUNT}
          FOR EACH ROW EXECUTE FUNCTION bump_sync_revision();
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {ACCOUNT} FROM asseta_app; GRANT SELECT, INSERT, UPDATE ON {ACCOUNT} TO asseta_app;
            REVOKE ALL ON {EVIDENCE} FROM asseta_app; GRANT SELECT, INSERT ON {EVIDENCE} TO asseta_app;
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                    values, reason, created_at, source)
        SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
               (SELECT max(version) + 1 FROM policy_version
                 WHERE policy_type = 'CASH_CUSTODY' AND scope = 'PLATFORM' AND tenant_id IS NULL),
               cur.effective_from, cur.values || '{NEW_KEYS}'::jsonb, '{SEED_REASON}', now(), 'migration'
          FROM (SELECT policy_type, effective_from, values FROM policy_version
                 WHERE policy_type = 'CASH_CUSTODY' AND scope = 'PLATFORM' AND tenant_id IS NULL
                   AND effective_from <= now()
                 ORDER BY effective_from DESC, version DESC LIMIT 1) cur
         WHERE NOT (cur.values ? 'max_holding_days');
    """)


def downgrade() -> None:
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
        DELETE FROM policy_version
         WHERE policy_type = 'CASH_CUSTODY' AND scope = 'PLATFORM' AND source = 'migration'
           AND reason = '{SEED_REASON}';
        ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
        ALTER TABLE {OVERDUE} DISABLE TRIGGER trg_{OVERDUE}_immutable;
        DELETE FROM {OVERDUE} WHERE reason <> 'CUTOFF';
        ALTER TABLE {OVERDUE} ENABLE TRIGGER trg_{OVERDUE}_immutable;
    """)
    op.drop_constraint("uq_cash_remittance_overdue_day_reason", OVERDUE, type_="unique")
    op.create_unique_constraint(
        "uq_cash_remittance_overdue_day", OVERDUE, ["tenant_id", "staff_member_id", "local_day"]
    )
    op.drop_column(OVERDUE, "max_holding_days")
    op.drop_column(OVERDUE, "held_since")
    op.drop_column(OVERDUE, "reason")
    op.drop_column("cash_handover", "deposit_account_id")
    op.drop_column("cash_handover", "method")
    for t in (EVIDENCE, ACCOUNT):
        op.execute(f"DROP POLICY IF EXISTS p_tenant ON {t}")
    op.drop_table(EVIDENCE)
    op.drop_table(ACCOUNT)
