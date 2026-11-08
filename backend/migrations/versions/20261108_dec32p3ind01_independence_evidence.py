"""DEC-032 Phase 3: independence and evidence. Generated references (COL-, PAY-, RMT-, CTR-, HTR-, RET-, CADJ-, ADJ-,
ARQ-) on collections, remittances, transfers, retentions, adjustments, with existing rows backfilled and the counters
aligned; evidence attachments on hours transfers, credit arrangements, classifications, non-revenue approvals, cash
variances and custody adjustments; client-created time on hours purchases, retentions and adjustments; variance
investigation (assignee, explanation + evidence, closure by a second person, append-only history, CUSTOMER_HOUR
variances); partial remittance approval; case closure proposals; new policy keys on the platform defaults.

Revision ID: dec32p3ind01
Revises: dec32p3sw01
Create Date: 2026-11-08 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "dec32p3ind01"
down_revision: str | Sequence[str] | None = "dec32p3sw01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASON = "DEC-032 Phase 3: independence and evidence"
EVIDENCE_TABLES = (
    "hours_transfer",
    "credit_arrangement",
    "engine_hour_classification",
    "non_revenue_approval",
    "custody_adjustment",
    "cash_variance",
)
CLIENT_TIME_TABLES = ("hours_purchase", "cash_retention", "custody_adjustment", "adjustment_request")
# table, number column, series (a SQL expression over the row `t`), time column to order and date by
NUMBERED = (
    ("cash_handover", "remittance_number", "'RMT'", "recorded_at"),
    ("cash_transfer", "transfer_number", "'CTR'", "recorded_at"),
    ("hours_transfer", "transfer_number", "'HTR'", "requested_at"),
    ("cash_retention", "retention_number", "'RET'", "created_at"),
    ("custody_adjustment", "adjustment_number", "'CADJ'", "created_at"),
    ("adjustment_request", "request_number", "'ARQ'", "proposed_at"),
    ("adjustment_ledger_entry", "entry_number", "'ADJ'", "posted_at"),
    ("customer_payment", "collection_number", "CASE WHEN t.method = 'CASH' THEN 'COL' ELSE 'PAY' END", "recorded_at"),
)
NUMBER_TABLES = {t: col for t, col, _, _ in NUMBERED}
POLICY_PATCHES = {
    "CUSTOMER_HOURS": (
        '{"transfer_evidence_required": false, "credit_evidence_required": false, '
        '"zero_amount_requires_approval": true, "variance_sweep_enabled": true, "variance_tolerance_hours": "0.01"}'
    ),
    "CASH_CUSTODY": (
        '{"variance_evidence_required": false, "custody_adjustment_evidence_required": false, '
        '"collection_link_required": false, "variance_closure_requires_second_person": true}'
    ),
    "ENGINE_HOURS": '{"classification_evidence_required": false}',
    "REVENUE_RECONCILIATION": '{"non_revenue_evidence_required": false}',
    "OVERSIGHT": '{"case_closure_requires_second_person": false}',
}
_VARIANCE_MUTABLE = (
    "ARRAY['status','reason_id','proposed_by','proposed_at','proposal_note','outcome','resolved_by','resolved_at',"
    "'resolution_note','proposed_outcome','assignee_user_id','assigned_by','assigned_at','explanation','explained_by',"
    "'explained_at','evidence_attachment_ids']"
)
_VARIANCE_MUTABLE_OLD = (
    "ARRAY['status','reason_id','proposed_by','proposed_at','proposal_note','outcome','resolved_by','resolved_at',"
    "'resolution_note']"
)
DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)


def _guard_anomaly_case(mutable: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION guard_anomaly_case() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[] := ARRAY[{mutable}];
        BEGIN
          IF TG_OP = 'DELETE' THEN {DENY}; END IF;
          IF (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: case subject and opening facts are immutable'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF (OLD.status, NEW.status) NOT IN (('OPEN','OPEN'), ('OPEN','IN_REVIEW'), ('OPEN','RESOLVED'),
              ('IN_REVIEW','IN_REVIEW'), ('IN_REVIEW','RESOLVED'), ('RESOLVED','IN_REVIEW')) THEN
            RAISE EXCEPTION 'asseta: case transition % -> % is not permitted', OLD.status, NEW.status
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF severity_rank(NEW.severity) < severity_rank(OLD.severity) THEN
            RAISE EXCEPTION 'asseta: case severity is never lowered' USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF NEW.status = 'RESOLVED' AND OLD.status <> 'RESOLVED' AND (NEW.resolved_by IS NULL OR NOT EXISTS (
               SELECT 1 FROM case_outcome o WHERE o.case_id = NEW.id AND o.decided_at = NEW.resolved_at
                 AND o.decided_by = NEW.resolved_by)) THEN
            RAISE EXCEPTION 'asseta: resolving a case requires a recorded outcome'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;"""


def _guard_variance(mutable: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION guard_cash_variance() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status = 'RESOLVED'
             OR (to_jsonb(NEW) - {mutable}) IS DISTINCT FROM (to_jsonb(OLD) - {mutable}) THEN
            RAISE EXCEPTION 'asseta: cash variance evidence is immutable; a resolved variance is final'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;"""


def _add_columns() -> None:
    for table, column, _, _ in NUMBERED:
        op.add_column(table, sa.Column(column, sa.String(32), nullable=True))
    for table in EVIDENCE_TABLES:
        op.add_column(
            table,
            sa.Column("evidence_attachment_ids", ARRAY(sa.UUID()), nullable=False, server_default=sa.text("'{}'")),
        )
        op.alter_column(table, "evidence_attachment_ids", server_default=None)
    for table in CLIENT_TIME_TABLES:
        op.add_column(table, sa.Column("client_created_at", sa.DateTime(timezone=True), nullable=True))
    for name, column in (
        ("unit", sa.String(16)),
        ("proposed_outcome", sa.String(24)),
        ("assignee_user_id", sa.UUID()),
        ("assigned_by", sa.UUID()),
        ("assigned_at", sa.DateTime(timezone=True)),
        ("explanation", sa.Text()),
        ("explained_by", sa.UUID()),
        ("explained_at", sa.DateTime(timezone=True)),
        ("check_code", sa.String(40)),
        ("customer_id", sa.Uuid()),
        ("machine_id", sa.Uuid()),
        ("purchase_id", sa.Uuid()),
        ("job_id", sa.Uuid()),
    ):
        op.add_column("cash_variance", sa.Column(name, column, nullable=name != "unit", server_default=_unit(name)))
    op.alter_column("cash_variance", "unit", server_default=None)
    op.create_index(op.f("ix_cash_variance_assignee_user_id"), "cash_variance", ["assignee_user_id"])
    op.create_index(op.f("ix_cash_variance_customer_id"), "cash_variance", ["customer_id"])
    op.create_index(op.f("ix_cash_variance_purchase_id"), "cash_variance", ["purchase_id"])
    op.create_foreign_key(op.f("fk_cash_variance_customer"), "cash_variance", "customer", ["customer_id"], ["id"])
    op.create_foreign_key(op.f("fk_cash_variance_machine"), "cash_variance", "machine", ["machine_id"], ["id"])
    op.create_foreign_key(op.f("fk_cash_variance_purchase"), "cash_variance", "hours_purchase", ["purchase_id"], ["id"])
    op.create_foreign_key(op.f("fk_cash_variance_job"), "cash_variance", "job", ["job_id"], ["id"])
    for name, column in (
        ("closure_outcome", sa.String(32)),
        ("closure_explanation", sa.Text()),
        ("closure_proposed_by", sa.UUID()),
        ("closure_proposed_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("anomaly_case", sa.Column(name, column, nullable=True))


def _unit(name: str) -> sa.TextClause | None:
    return sa.text("'MONEY'") if name == "unit" else None


def _backfill() -> None:
    tables = list(NUMBER_TABLES)
    tz = "(SELECT timezone FROM tenant_settings ts WHERE ts.tenant_id = t.tenant_id)"
    op.execute("SELECT set_config('app.scope', 'system', true)")
    for table in tables:
        op.execute(f"ALTER TABLE {table} DISABLE TRIGGER USER")
    for table, column, series, at in NUMBERED:
        year = f"(EXTRACT(YEAR FROM t.{at} AT TIME ZONE COALESCE({tz}, 'UTC')))::int"
        base = f"SELECT t.id, t.tenant_id, t.{at} AS at, {series} AS series, {year} AS year FROM {table} t"
        op.execute(f"""
            UPDATE {table} u SET {column} = n.series || '-' || n.year || '-' || lpad(n.seq::text, 5, '0')
              FROM (SELECT b.id, b.series, b.year,
                           row_number() OVER (PARTITION BY b.tenant_id, b.series, b.year ORDER BY b.at, b.id) AS seq
                      FROM ({base}) b) n
             WHERE u.id = n.id;
            INSERT INTO hours_sequence (tenant_id, series, year, last_number)
            SELECT b.tenant_id, b.series, b.year, count(*) FROM ({base}) b GROUP BY b.tenant_id, b.series, b.year
            ON CONFLICT (tenant_id, series, year) DO UPDATE SET last_number = EXCLUDED.last_number;
        """)
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE TRIGGER USER")


def _constraints() -> None:
    for table, column, _, _ in NUMBERED:
        op.alter_column(table, column, nullable=False)
    for name, table, column in (
        ("uq_cash_handover_number", "cash_handover", "remittance_number"),
        ("uq_cash_transfer_number", "cash_transfer", "transfer_number"),
        ("uq_hours_transfer_number", "hours_transfer", "transfer_number"),
        ("uq_cash_retention_number", "cash_retention", "retention_number"),
        ("uq_custody_adjustment_number", "custody_adjustment", "adjustment_number"),
        ("uq_adjustment_request_number", "adjustment_request", "request_number"),
        ("uq_adjustment_entry_number", "adjustment_ledger_entry", "entry_number"),
        ("uq_customer_payment_number", "customer_payment", "collection_number"),
    ):
        op.create_unique_constraint(name, table, ["tenant_id", column])


def _new_tables() -> None:
    op.create_table(
        "partial_remittance_approval",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("handover_id", sa.Uuid(), nullable=False),
        sa.Column("reason_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["handover_id"], ["cash_handover.id"]),
        sa.ForeignKeyConstraint(["reason_id"], ["cash_reason.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handover_id", name="uq_partial_remittance_handover"),
    )
    op.create_index(op.f("ix_partial_remittance_approval_tenant_id"), "partial_remittance_approval", ["tenant_id"])
    op.create_index(op.f("ix_partial_remittance_approval_handover_id"), "partial_remittance_approval", ["handover_id"])
    op.create_table(
        "cash_variance_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("variance_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("data", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["variance_id"], ["cash_variance.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("variance_id", "seq", name="uq_cash_variance_event_seq"),
    )
    op.create_index(op.f("ix_cash_variance_event_tenant_id"), "cash_variance_event", ["tenant_id"])
    op.execute("""
        CREATE TRIGGER trg_partial_remittance_approval_guard BEFORE UPDATE OR DELETE ON partial_remittance_approval
          FOR EACH ROW EXECUTE FUNCTION guard_pending_decision();
        CREATE TRIGGER trg_cash_variance_event_immutable BEFORE UPDATE OR DELETE ON cash_variance_event
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
    """)
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    grants = {"partial_remittance_approval": "SELECT, INSERT, UPDATE", "cash_variance_event": "SELECT, INSERT"}
    for t in grants:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {t} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    grant_sql = "\n".join(
        f"REVOKE ALL ON {t} FROM asseta_app; GRANT {p} ON {t} TO asseta_app;" for t, p in grants.items()
    )
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grant_sql}
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO cash_variance_event (id, tenant_id, variance_id, action, actor_user_id, note, data, occurred_at, seq)
        SELECT gen_random_uuid(), tenant_id, id, 'OPENED', opened_by, NULL, '{{}}'::jsonb, opened_at, 1 FROM cash_variance;
        INSERT INTO cash_variance_event (id, tenant_id, variance_id, action, actor_user_id, note, data, occurred_at, seq)
        SELECT gen_random_uuid(), tenant_id, id, 'RESOLVED', resolved_by, resolution_note,
               jsonb_build_object('outcome', outcome), resolved_at, 2
          FROM cash_variance WHERE status = 'RESOLVED' AND resolved_at IS NOT NULL;
    """)


def upgrade() -> None:
    _add_columns()
    _backfill()
    _constraints()
    _new_tables()
    op.execute(_guard_variance(_VARIANCE_MUTABLE))
    op.execute(
        _guard_anomaly_case(
            "'severity','status','assignee_user_id','last_signal_at','resolved_at','resolved_by','updated_at','version',"
            "'closure_outcome','closure_explanation','closure_proposed_by','closure_proposed_at'"
        )
    )
    for ptype, patch in POLICY_PATCHES.items():
        op.execute(f"""
            SELECT set_config('app.scope', 'system', true);
            INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                        values, reason, created_at, source)
            SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
                   (SELECT max(version) + 1 FROM policy_version
                     WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL),
                   cur.effective_from, cur.values || '{patch}'::jsonb, '{REASON}', now(), 'migration'
              FROM (SELECT policy_type, effective_from, values FROM policy_version
                     WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL
                       AND effective_from <= now()
                     ORDER BY effective_from DESC, version DESC LIMIT 1) cur;
        """)


def downgrade() -> None:
    for ptype in POLICY_PATCHES:
        op.execute(f"""
            SELECT set_config('app.scope', 'system', true);
            ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
            ALTER TABLE policy_version NO FORCE ROW LEVEL SECURITY;
            DELETE FROM policy_version
             WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND source = 'migration' AND reason = '{REASON}';
            ALTER TABLE policy_version FORCE ROW LEVEL SECURITY;
            ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
        """)
    op.execute(
        _guard_anomaly_case(
            "'severity','status','assignee_user_id','last_signal_at','resolved_at','resolved_by','updated_at','version'"
        )
    )
    op.execute(_guard_variance(_VARIANCE_MUTABLE_OLD))
    op.drop_table("cash_variance_event")
    op.drop_table("partial_remittance_approval")
    for name in ("closure_outcome", "closure_explanation", "closure_proposed_by", "closure_proposed_at"):
        op.drop_column("anomaly_case", name)
    for fk in (
        "fk_cash_variance_customer",
        "fk_cash_variance_machine",
        "fk_cash_variance_purchase",
        "fk_cash_variance_job",
    ):
        op.drop_constraint(op.f(fk), "cash_variance", type_="foreignkey")
    op.execute("DROP INDEX IF EXISTS ix_cash_variance_assignee_user_id")
    op.execute("DROP INDEX IF EXISTS ix_cash_variance_customer_id")
    op.execute("DROP INDEX IF EXISTS ix_cash_variance_purchase_id")
    for name in (
        "unit",
        "proposed_outcome",
        "assignee_user_id",
        "assigned_by",
        "assigned_at",
        "explanation",
        "explained_by",
        "explained_at",
        "check_code",
        "customer_id",
        "machine_id",
        "purchase_id",
        "job_id",
    ):
        op.drop_column("cash_variance", name)
    for table in EVIDENCE_TABLES:
        op.drop_column(table, "evidence_attachment_ids")
    for table in CLIENT_TIME_TABLES:
        op.drop_column(table, "client_created_at")
    for table, column, _, _ in NUMBERED:
        op.drop_column(table, column)
