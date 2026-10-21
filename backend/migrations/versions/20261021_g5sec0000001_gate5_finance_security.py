"""Gate 5: tenant-owned FORCE RLS, explicit per-table grants, immutability/decision guards for hire finance and
expenses, expense_category sync revisions, seeded EXPENSE_CAPTURE platform policy.

Revision ID: g5sec0000001
Revises: 9a9d00daca8d
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g5sec0000001"
down_revision: str | None = "9a9d00daca8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Explicit privileges per table (everything else revoked, including what default privileges handed out).
GRANTS: dict[str, str] = {
    "tenant_hire_invoice": "SELECT, INSERT, UPDATE",  # guard: issued snapshot frozen, only ISSUED -> VOIDED
    "hire_invoice_line": "SELECT, INSERT",  # insert only while the invoice is a draft
    "hire_invoice_job": "SELECT, INSERT, UPDATE",  # guard: claim release only
    "hire_invoice_counter": "SELECT, INSERT, UPDATE",
    "financial_adjustment": "SELECT, INSERT",
    "customer_payment": "SELECT, INSERT, UPDATE",  # guard: CLAIMED -> decision only
    "hire_payment_allocation": "SELECT, INSERT, UPDATE",  # guard: release only
    "supervisor_cash_custody": "SELECT, INSERT",
    "cash_handover": "SELECT, INSERT, UPDATE",  # guard: CLAIMED -> decision only
    "expense_category": "SELECT, INSERT, UPDATE",
    "expense": "SELECT, INSERT, UPDATE",  # guard: PENDING_APPROVAL -> decision only
    "expense_attachment": "SELECT, INSERT",
    "fuel_event": "SELECT, INSERT",
    "approval_request": "SELECT, INSERT, UPDATE",  # guard: PENDING -> decision only
}
APPEND_ONLY = [
    "hire_invoice_line",
    "financial_adjustment",
    "supervisor_cash_custody",
    "expense_attachment",
    "fuel_event",
]
GUARDED = {
    "tenant_hire_invoice": "guard_hire_invoice",
    "hire_invoice_job": "guard_released_once",
    "hire_payment_allocation": "guard_released_once",
    "customer_payment": "guard_settlement_decision",
    "cash_handover": "guard_settlement_decision",
    "expense": "guard_pending_decision",
    "approval_request": "guard_pending_decision",
}
EXPENSE_SEED = (
    '{"receipt_required_above": "0", "gps_required": true, "gps_max_accuracy_m": 100.0, "auto_approve_limit": "0"}'
)
DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)


def upgrade() -> None:
    op.execute(f"""
        CREATE FUNCTION guard_hire_invoice() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[];
        BEGIN
          IF TG_OP = 'DELETE' THEN {DENY}; END IF;
          IF OLD.status = 'DRAFT' AND NEW.status IN ('DRAFT', 'ISSUED', 'VOIDED') THEN
            mutable := ARRAY['status','invoice_number','issued_at','issued_by','due_date','notes',
                             'voided_at','voided_by','void_reason'];
          ELSIF OLD.status = 'ISSUED' AND NEW.status = 'VOIDED' THEN
            mutable := ARRAY['status','voided_at','voided_by','void_reason'];
          ELSE
            RAISE EXCEPTION 'asseta: issued hire invoice is immutable (corrections only by reversal)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: hire invoice snapshot is immutable' USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_hire_invoice_line_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM tenant_hire_invoice i WHERE i.id = NEW.invoice_id AND i.status = 'DRAFT') THEN
            RAISE EXCEPTION 'asseta: lines can only be added to a draft hire invoice'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_released_once() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.released_at IS NOT NULL OR NEW.released_at IS NULL
             OR (to_jsonb(NEW) - ARRAY['released_at','release_reason'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['released_at','release_reason']) THEN
            {DENY};
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_settlement_decision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'CLAIMED' OR NEW.status NOT IN ('VERIFIED', 'REJECTED')
             OR (to_jsonb(NEW) - ARRAY['status','verified_by','verified_at','decision_note'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','verified_by','verified_at','decision_note']) THEN
            RAISE EXCEPTION 'asseta: settlement evidence is immutable (only a single verify/reject decision)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_pending_decision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status NOT IN ('PENDING', 'PENDING_APPROVAL')
             OR NEW.status NOT IN ('APPROVED', 'REJECTED')
             OR (to_jsonb(NEW) - ARRAY['status','decided_by','decided_at','decision_note'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','decided_by','decided_at','decision_note']) THEN
            RAISE EXCEPTION 'asseta: captured evidence is immutable (only a single approval decision)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_hire_invoice_line_insert BEFORE INSERT ON hire_invoice_line
          FOR EACH ROW EXECUTE FUNCTION guard_hire_invoice_line_insert();
        CREATE TRIGGER trg_expense_category_sync_revision BEFORE UPDATE ON expense_category
          FOR EACH ROW EXECUTE FUNCTION bump_sync_revision();
    """)
    for t, fn in GUARDED.items():
        op.execute(f"CREATE TRIGGER trg_{t}_guard BEFORE UPDATE OR DELETE ON {t} FOR EACH ROW EXECUTE FUNCTION {fn}()")
    for t in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER trg_{t}_immutable BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )
    own = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
    for t in GRANTS:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY p_tenant ON {t} USING ({own} OR app_scope() = 'system') "
            f"WITH CHECK ({own} OR app_scope() = 'system')"
        )
    grants = "\n".join(f"REVOKE ALL ON {t} FROM asseta_app; GRANT {p} ON {t} TO asseta_app;" for t, p in GRANTS.items())
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grants}
          END IF;
        END $$;
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from, values,
                                    reason, created_at, source)
        SELECT gen_random_uuid(), 'EXPENSE_CAPTURE', 'PLATFORM', NULL, NULL, 1, TIMESTAMPTZ '2000-01-01 00:00:00+00',
               '{EXPENSE_SEED}'::jsonb, 'Seeded platform default (replaceable configuration)', now(), 'migration'
        WHERE NOT EXISTS (SELECT 1 FROM policy_version WHERE policy_type = 'EXPENSE_CAPTURE' AND scope = 'PLATFORM');
    """)


def downgrade() -> None:
    for t in GRANTS:
        op.execute(
            f"DROP POLICY IF EXISTS p_tenant ON {t}; ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;"
            f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY"
        )
    for t in APPEND_ONLY:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_immutable ON {t}")
    for t in GUARDED:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_guard ON {t}")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_hire_invoice_line_insert ON hire_invoice_line;"
        "DROP TRIGGER IF EXISTS trg_expense_category_sync_revision ON expense_category;"
        "DROP FUNCTION IF EXISTS guard_hire_invoice(); DROP FUNCTION IF EXISTS guard_hire_invoice_line_insert();"
        "DROP FUNCTION IF EXISTS guard_released_once(); DROP FUNCTION IF EXISTS guard_settlement_decision();"
        "DROP FUNCTION IF EXISTS guard_pending_decision();"
    )
    # The EXPENSE_CAPTURE platform seed is immutable (policy_version trigger) and harmless; re-upgrade is idempotent.
