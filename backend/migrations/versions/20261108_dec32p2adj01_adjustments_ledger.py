"""DEC-032 Phase 2: Ledger 6 (adjustment_ledger_entry, append-only) and the uniform propose/decide flow
(adjustment_request); a single reversal stamp on customer payments, hours ledger and financial adjustments linked to
the request that caused them; decided records of the existing approval flows backfilled into the ledger. Policy keys:
CUSTOMER_HOURS.refund_allowed, reversal_used_hours_treatment, adjustment_evidence_required; HIRE_BILLING
invoice_void_requires_approval.

Revision ID: dec32p2adj01
Revises: dec32p1all03
Create Date: 2026-11-08 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dec32p2adj01"
down_revision: str | Sequence[str] | None = "dec32p1all03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOURS_REASON = "DEC-032 Phase 2: refunds, used-hours treatment on reversal, evidence on corrections"
BILLING_REASON = "DEC-032 Phase 2: invoice voids need a second person"
LEDGER = "adjustment_ledger_entry"
REQUEST = "adjustment_request"
DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)


def _request_table() -> None:
    op.create_table(
        REQUEST,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("original_type", sa.String(length=40), nullable=False),
        sa.Column("original_id", sa.UUID(), nullable=False),
        sa.Column("original_reference", sa.String(length=120), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("machine_id", sa.Uuid(), nullable=True),
        sa.Column("purchase_id", sa.Uuid(), nullable=True),
        sa.Column("hours", sa.Numeric(14, 2), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("settlement", sa.String(length=16), nullable=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reason_code_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_attachment_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("proposed_by", sa.UUID(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.CheckConstraint("amount IS NULL OR amount > 0", name="ck_adjustment_request_amount"),
        sa.CheckConstraint("hours IS NULL OR hours <> 0", name="ck_adjustment_request_hours"),
        sa.ForeignKeyConstraint(["currency"], ["currency.code"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["purchase_id"], ["hours_purchase.id"]),
        sa.ForeignKeyConstraint(["reason_code_id"], ["hours_reason_code.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "client_id", name="uq_adjustment_request_client"),
    )
    op.create_index(op.f("ix_adjustment_request_tenant_id"), REQUEST, ["tenant_id"])
    op.create_index(op.f("ix_adjustment_request_customer_id"), REQUEST, ["customer_id"])
    op.create_index(op.f("ix_adjustment_request_machine_id"), REQUEST, ["machine_id"])
    op.create_index(op.f("ix_adjustment_request_purchase_id"), REQUEST, ["purchase_id"])
    op.create_index(op.f("ix_adjustment_request_original_id"), REQUEST, ["original_id"])
    op.create_index(op.f("ix_adjustment_request_proposed_by"), REQUEST, ["proposed_by"])
    op.create_index("ix_adjustment_request_status", REQUEST, ["tenant_id", "status", "proposed_at"])
    op.create_index(
        "uq_adjustment_request_reversal",
        REQUEST,
        ["tenant_id", "original_type", "original_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('PROPOSED', 'APPROVED') AND request_type IN "
            "('PAYMENT_REVERSAL', 'COLLECTION_REVERSAL', 'PURCHASE_REVERSAL', 'INVOICE_VOID')"
        ),
    )


def _ledger_table() -> None:
    op.create_table(
        LEDGER,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("adjustment_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("original_type", sa.String(length=40), nullable=False),
        sa.Column("original_id", sa.UUID(), nullable=False),
        sa.Column("original_reference", sa.String(length=120), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("original_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("new_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("resulting_balance", sa.Numeric(18, 4), nullable=True),
        sa.Column("reason_id", sa.UUID(), nullable=True),
        sa.Column("reason_label", sa.String(length=200), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_attachment_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("machine_id", sa.Uuid(), nullable=True),
        sa.Column("staff_member_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["staff_member_id"], ["staff_member.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "source_type", "source_id", "status", name="uq_adjustment_entry_source"),
    )
    op.create_index(op.f("ix_adjustment_ledger_entry_tenant_id"), LEDGER, ["tenant_id"])
    op.create_index(op.f("ix_adjustment_ledger_entry_original_id"), LEDGER, ["original_id"])
    op.create_index(op.f("ix_adjustment_ledger_entry_original_reference"), LEDGER, ["original_reference"])
    op.create_index(op.f("ix_adjustment_ledger_entry_customer_id"), LEDGER, ["customer_id"])
    op.create_index(op.f("ix_adjustment_ledger_entry_machine_id"), LEDGER, ["machine_id"])
    op.create_index(op.f("ix_adjustment_ledger_entry_staff_member_id"), LEDGER, ["staff_member_id"])
    op.create_index(op.f("ix_adjustment_ledger_entry_requested_by"), LEDGER, ["requested_by"])
    op.create_index(op.f("ix_adjustment_ledger_entry_approved_by"), LEDGER, ["approved_by"])
    op.create_index("ix_adjustment_entry_type", LEDGER, ["tenant_id", "adjustment_type", "posted_at"])
    op.create_index("ix_adjustment_entry_posted", LEDGER, ["tenant_id", "posted_at"])


def _links() -> None:
    op.add_column("hours_ledger_entry", sa.Column("adjustment_request_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_hours_ledger_adjustment_request", "hours_ledger_entry", REQUEST, ["adjustment_request_id"], ["id"]
    )
    op.create_index(
        op.f("ix_hours_ledger_entry_adjustment_request_id"), "hours_ledger_entry", ["adjustment_request_id"]
    )
    op.add_column("financial_adjustment", sa.Column("adjustment_request_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_financial_adjustment_request", "financial_adjustment", REQUEST, ["adjustment_request_id"], ["id"]
    )
    op.create_index(
        op.f("ix_financial_adjustment_adjustment_request_id"), "financial_adjustment", ["adjustment_request_id"]
    )
    op.add_column("customer_payment", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customer_payment", sa.Column("reversal_id", sa.UUID(), nullable=True))


def _guards() -> None:
    # The settlement guard keeps its single decision and gains the single reversal stamp (DEC-032 B4). A reversed row
    # is otherwise frozen: nothing about the original payment or remittance changes.
    op.execute(f"""
        CREATE OR REPLACE FUNCTION guard_settlement_decision() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE stamp text[] := ARRAY['reversed_at','reversal_id'];
        BEGIN
          IF TG_OP = 'DELETE' THEN {DENY}; END IF;
          IF TG_TABLE_NAME = 'customer_payment' AND OLD.status = 'VERIFIED' AND NEW.status = 'VERIFIED'
             AND to_jsonb(OLD) ->> 'reversed_at' IS NULL AND to_jsonb(NEW) ->> 'reversed_at' IS NOT NULL
             AND to_jsonb(NEW) ->> 'reversal_id' IS NOT NULL
             AND (to_jsonb(NEW) - stamp) IS NOT DISTINCT FROM (to_jsonb(OLD) - stamp) THEN
            RETURN NEW;
          END IF;
          IF OLD.status <> 'CLAIMED' OR NEW.status NOT IN ('VERIFIED', 'REJECTED')
             OR (to_jsonb(NEW) - ARRAY['status','verified_by','verified_at','decision_note'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','verified_by','verified_at','decision_note']) THEN
            RAISE EXCEPTION 'asseta: settlement evidence is immutable (only a single verify/reject decision)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
    """)
    # A proposal is immutable; a single decision (or the proposer's withdrawal) may record its outcome.
    op.execute(f"""
        CREATE FUNCTION guard_adjustment_request() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE decision text[] := ARRAY['status','decided_by','decided_at','decision_note','result'];
        BEGIN
          IF TG_OP = 'DELETE' THEN {DENY}; END IF;
          IF OLD.status <> 'PROPOSED' OR NEW.status NOT IN ('APPROVED', 'REJECTED', 'WITHDRAWN')
             OR (to_jsonb(NEW) - decision) IS DISTINCT FROM (to_jsonb(OLD) - decision) THEN
            RAISE EXCEPTION 'asseta: an adjustment request is decided once and its content is immutable'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_{REQUEST}_guard BEFORE UPDATE OR DELETE ON {REQUEST}
          FOR EACH ROW EXECUTE FUNCTION guard_adjustment_request();
        CREATE TRIGGER trg_{LEDGER}_immutable BEFORE UPDATE OR DELETE ON {LEDGER}
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
    """)
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for table in (LEDGER, REQUEST):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {table} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            REVOKE ALL ON {LEDGER} FROM asseta_app; GRANT SELECT, INSERT ON {LEDGER} TO asseta_app;
            REVOKE ALL ON {REQUEST} FROM asseta_app; GRANT SELECT, INSERT, UPDATE ON {REQUEST} TO asseta_app;
          END IF;
        END $$;
    """)


def _new_platform_version(ptype: str, patch: str, reason: str) -> None:
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                    values, reason, created_at, source)
        SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
               (SELECT max(version) + 1 FROM policy_version
                 WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL),
               cur.effective_from, cur.values || '{patch}'::jsonb, '{reason}', now(), 'migration'
          FROM (SELECT policy_type, effective_from, values FROM policy_version
                 WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL
                   AND effective_from <= now()
                 ORDER BY effective_from DESC, version DESC LIMIT 1) cur;
    """)


def _insert(select: str) -> None:
    op.execute(f"""
        INSERT INTO {LEDGER} (id, tenant_id, adjustment_type, status, original_type, original_id, original_reference,
                              source_type, source_id, unit, original_value, new_value, amount, currency,
                              resulting_balance, reason_id, reason_label, reason, evidence_attachment_ids,
                              customer_id, machine_id, staff_member_id, requested_by, requested_at, approved_by,
                              approved_at, decision_note, details, policy_version, posted_at, created_at)
        {select}
        ON CONFLICT ON CONSTRAINT uq_adjustment_entry_source DO NOTHING
    """)


def _backfill() -> None:
    """Decided records of the existing approval flows, as they were (no resulting balance is reconstructed)."""
    _insert("""
        SELECT gen_random_uuid(), t.tenant_id, 'HOURS_TRANSFER', t.status, 'hours_purchase', t.purchase_id,
               p.purchase_number, 'hours_transfer', t.id, 'HOURS', NULL, NULL, t.hours, NULL, NULL, t.reason_code_id,
               rc.label, t.reason, '{}'::uuid[], p.customer_id, t.from_machine_id, NULL, t.requested_by, t.requested_at,
               t.decided_by, t.decided_at, t.decision_note, jsonb_build_object('to_machine_id', t.to_machine_id),
               NULL, COALESCE(t.decided_at, t.requested_at), now()
          FROM hours_transfer t JOIN hours_purchase p ON p.id = t.purchase_id
          LEFT JOIN hours_reason_code rc ON rc.id = t.reason_code_id
         WHERE t.status IN ('APPROVED', 'REJECTED')""")
    _insert("""
        SELECT gen_random_uuid(), c.tenant_id, 'HOURS_CANCELLATION', c.status, 'hours_purchase', c.purchase_id,
               p.purchase_number, 'hours_cancellation', c.id, 'HOURS', NULL, NULL,
               -COALESCE((SELECT sum(l.hours) FROM hours_ledger_entry l WHERE l.cancellation_id = c.id), 0),
               NULL, NULL, c.reason_code_id, rc.label, c.reason, '{}'::uuid[], p.customer_id, p.machine_id, NULL,
               c.requested_by, c.requested_at, c.decided_by, c.decided_at, c.decision_note, '{}'::jsonb, NULL,
               COALESCE(c.decided_at, c.requested_at), now()
          FROM hours_cancellation c JOIN hours_purchase p ON p.id = c.purchase_id
          LEFT JOIN hours_reason_code rc ON rc.id = c.reason_code_id
         WHERE c.status IN ('APPROVED', 'REJECTED')""")
    _insert("""
        SELECT gen_random_uuid(), a.tenant_id, 'CREDIT_ARRANGEMENT', a.status, 'credit_arrangement', a.id, c.name,
               'credit_arrangement', a.id, 'MONEY', NULL, a.limit_amount, a.limit_amount, a.currency, NULL,
               a.reason_code_id, rc.label, a.reason, '{}'::uuid[], a.customer_id, NULL, NULL, a.proposed_by, a.proposed_at,
               a.decided_by, a.decided_at, a.decision_note, '{}'::jsonb, NULL, COALESCE(a.decided_at, a.proposed_at), now()
          FROM credit_arrangement a JOIN customer c ON c.id = a.customer_id
          LEFT JOIN hours_reason_code rc ON rc.id = a.reason_code_id
         WHERE a.status IN ('APPROVED', 'REJECTED')""")
    _insert("""
        SELECT gen_random_uuid(), a.tenant_id, 'CREDIT_ARRANGEMENT', 'REVOKED', 'credit_arrangement', a.id, c.name,
               'credit_arrangement', a.id, 'MONEY', a.limit_amount, 0, -a.limit_amount, a.currency, NULL,
               a.reason_code_id, rc.label, a.revoke_reason, '{}'::uuid[], a.customer_id, NULL, NULL, a.proposed_by, a.proposed_at,
               a.revoked_by, a.revoked_at, a.revoke_reason, '{}'::jsonb, NULL, a.revoked_at, now()
          FROM credit_arrangement a JOIN customer c ON c.id = a.customer_id
          LEFT JOIN hours_reason_code rc ON rc.id = a.reason_code_id
         WHERE a.status = 'REVOKED'""")
    _insert("""
        SELECT gen_random_uuid(), m.tenant_id, 'METER_CORRECTION', m.status, 'meter_capture', m.superseded_capture_id,
               NULL, 'meter_correction', m.id, 'READING', m.old_reading, m.new_reading,
               m.new_reading - m.old_reading, NULL, NULL, NULL, NULL, m.reason, '{}'::uuid[], NULL, m.machine_id, NULL,
               m.proposed_by, m.proposed_at, m.decided_by, m.decided_at, m.decision_note,
               jsonb_build_object('job_id', m.job_id), m.policy_version, COALESCE(m.decided_at, m.proposed_at), now()
          FROM meter_correction m WHERE m.status IN ('APPROVED', 'REJECTED')""")
    _insert("""
        SELECT gen_random_uuid(), w.tenant_id, 'ALLOCATION_CORRECTION',
               CASE WHEN w.status = 'REJECTED' THEN 'REJECTED' ELSE 'APPROVED' END, 'work_allocation', w.supersedes_id,
               NULL, 'work_allocation_correction', w.correction_group_id, 'HOURS', w.hours, NULL, NULL, NULL, NULL,
               NULL, NULL, w.correction_reason, '{}'::uuid[], w.customer_id, w.machine_id, NULL, w.recorded_by,
               w.created_at, w.decided_by, w.decided_at, w.decision_note, '{}'::jsonb, w.policy_version,
               COALESCE(w.decided_at, w.created_at), now()
          FROM work_allocation w
         WHERE w.correction_group_id IS NOT NULL AND w.status IN ('ACTIVE', 'SUPERSEDED', 'REJECTED')
           AND w.decided_at IS NOT NULL
           AND w.id = (SELECT x.id FROM work_allocation x WHERE x.correction_group_id = w.correction_group_id
                        ORDER BY x.start_reading LIMIT 1)""")
    _insert("""
        SELECT gen_random_uuid(), r.tenant_id, 'ENGINE_HOUR_CLASSIFICATION', r.status, 'machine', r.machine_id, NULL,
               'engine_hour_classification', r.id, 'HOURS', r.hours, NULL, r.hours, NULL, NULL, r.reason_id,
               ehr.name, r.note, '{}'::uuid[], NULL, r.machine_id, NULL, r.proposed_by, r.proposed_at, r.decided_by,
               r.decided_at, r.decision_note, jsonb_build_object('outcome', r.outcome), r.policy_version,
               COALESCE(r.decided_at, r.proposed_at), now()
          FROM engine_hour_classification r LEFT JOIN engine_hour_reason ehr ON ehr.id = r.reason_id
         WHERE r.status IN ('APPROVED', 'REJECTED')""")
    _insert("""
        SELECT gen_random_uuid(), n.tenant_id, 'NON_REVENUE_APPROVAL', n.status, 'job_activity', n.activity_id, NULL,
               'non_revenue_approval', n.id, 'HOURS', n.hours, NULL, n.hours, NULL, NULL, n.reason_id, rr.name, n.note,
               '{}'::uuid[], NULL, n.machine_id, NULL, n.proposed_by, n.proposed_at, n.decided_by, n.decided_at,
               n.decision_note, jsonb_build_object('activity_type', n.activity_type, 'job_id', n.job_id), NULL,
               COALESCE(n.decided_at, n.proposed_at), now()
          FROM non_revenue_approval n LEFT JOIN revenue_reason rr ON rr.id = n.reason_id
         WHERE n.status IN ('APPROVED', 'REJECTED')""")
    _insert("""
        SELECT gen_random_uuid(), v.tenant_id,
               CASE WHEN v.outcome = 'WRITTEN_OFF' THEN 'CASH_WRITE_OFF' ELSE 'CASH_VARIANCE_RESOLUTION' END, 'APPROVED',
               'cash_variance', v.id, NULL, 'cash_variance', v.id, 'MONEY', v.declared_amount, v.received_amount,
               v.amount, v.currency, NULL, v.reason_id, cr.label, v.resolution_note, '{}'::uuid[], NULL, NULL,
               v.staff_member_id, v.proposed_by, v.proposed_at, v.resolved_by, v.resolved_at, v.resolution_note,
               jsonb_build_object('outcome', v.outcome, 'source_type', v.source_type), v.policy_version,
               COALESCE(v.resolved_at, v.opened_at), now()
          FROM cash_variance v LEFT JOIN cash_reason cr ON cr.id = v.reason_id WHERE v.status = 'RESOLVED'""")
    _insert("""
        SELECT gen_random_uuid(), a.tenant_id, 'CUSTODY_ADJUSTMENT', a.status,
               COALESCE(a.reverses_entity_type, 'custody_adjustment'), COALESCE(a.reverses_entity_id, a.id), NULL,
               'custody_adjustment', a.id, 'MONEY', NULL, NULL, a.amount, a.currency, NULL, a.reason_id, cr.label, a.reason,
               '{}'::uuid[], NULL, NULL, a.staff_member_id, a.created_by, a.created_at, a.decided_by, a.decided_at,
               a.decision_note, jsonb_build_object('kind', a.kind), NULL, COALESCE(a.decided_at, a.created_at), now()
          FROM custody_adjustment a LEFT JOIN cash_reason cr ON cr.id = a.reason_id
         WHERE a.status IN ('APPROVED', 'REJECTED')""")
    _insert("""
        SELECT gen_random_uuid(), f.tenant_id, 'INVOICE_VOID', 'APPROVED', 'tenant_hire_invoice', f.invoice_id,
               i.invoice_number, 'financial_adjustment', f.id, 'MONEY', i.total, 0, -f.amount, f.currency, NULL, NULL, NULL,
               f.reason, '{}'::uuid[], f.customer_id, NULL, NULL, f.created_by, f.created_at, NULL, NULL, NULL,
               jsonb_build_object('note', 'Voided before invoice voids needed a second person'), NULL, f.created_at, now()
          FROM financial_adjustment f JOIN tenant_hire_invoice i ON i.id = f.invoice_id
         WHERE f.kind = 'INVOICE_REVERSAL' AND f.invoice_id IS NOT NULL""")


def upgrade() -> None:
    _request_table()
    _ledger_table()
    _links()
    _guards()
    _new_platform_version(
        "CUSTOMER_HOURS",
        '{"refund_allowed": false, "reversal_used_hours_treatment": "RECEIVABLE", '
        '"adjustment_evidence_required": true}',
        HOURS_REASON,
    )
    _new_platform_version("HIRE_BILLING", '{"invoice_void_requires_approval": true}', BILLING_REASON)
    _backfill()


def downgrade() -> None:
    for ptype, reason in (
        ("CUSTOMER_HOURS", HOURS_REASON),
        ("HIRE_BILLING", BILLING_REASON),
    ):
        op.execute(f"""
            SELECT set_config('app.scope', 'system', true);
            ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
            DELETE FROM policy_version
             WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND source = 'migration' AND reason = '{reason}';
            ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
        """)
    op.execute(f"""
        DROP TRIGGER IF EXISTS trg_{LEDGER}_immutable ON {LEDGER};
        DROP TRIGGER IF EXISTS trg_{REQUEST}_guard ON {REQUEST};
        DROP FUNCTION IF EXISTS guard_adjustment_request();
        CREATE OR REPLACE FUNCTION guard_settlement_decision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'CLAIMED' OR NEW.status NOT IN ('VERIFIED', 'REJECTED')
             OR (to_jsonb(NEW) - ARRAY['status','verified_by','verified_at','decision_note'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','verified_by','verified_at','decision_note']) THEN
            RAISE EXCEPTION 'asseta: settlement evidence is immutable (only a single verify/reject decision)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
    """)
    op.drop_column("customer_payment", "reversal_id")
    op.drop_column("customer_payment", "reversed_at")
    op.drop_index(op.f("ix_financial_adjustment_adjustment_request_id"), table_name="financial_adjustment")
    op.drop_constraint("fk_financial_adjustment_request", "financial_adjustment", type_="foreignkey")
    op.drop_column("financial_adjustment", "adjustment_request_id")
    op.drop_index(op.f("ix_hours_ledger_entry_adjustment_request_id"), table_name="hours_ledger_entry")
    op.drop_constraint("fk_hours_ledger_adjustment_request", "hours_ledger_entry", type_="foreignkey")
    op.drop_column("hours_ledger_entry", "adjustment_request_id")
    op.drop_table(LEDGER)
    op.drop_table(REQUEST)
