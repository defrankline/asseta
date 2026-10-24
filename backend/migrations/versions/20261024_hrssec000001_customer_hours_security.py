"""Customer hours security: tenant-owned FORCE RLS and explicit grants (never DELETE) on the hours tables, an
append-only hours ledger / work execution allocations / payment evidence, guards that allow only the documented
changes (purchase: one cancellation stamp; proposals: edit while PROPOSED, one decision, revoke once; requests: one
decision; allocations: release once) and the seeded CUSTOMER_HOURS platform policy (replaceable configuration).

Revision ID: hrssec000001
Revises: hours0000001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "hrssec000001"
down_revision: str | None = "hours0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS: dict[str, str] = {
    "hours_sequence": "SELECT, INSERT, UPDATE",
    "hours_reason_code": "SELECT, INSERT, UPDATE",  # guard: identity frozen, never deleted (deactivated instead)
    "customer_discount": "SELECT, INSERT, UPDATE",  # guard: proposal lifecycle
    "credit_arrangement": "SELECT, INSERT, UPDATE",  # guard: proposal lifecycle
    "hours_purchase": "SELECT, INSERT, UPDATE",  # guard: immutable except the cancellation stamp (once)
    "hours_payment_allocation": "SELECT, INSERT, UPDATE",  # guard: release only
    "payment_evidence": "SELECT, INSERT",
    "work_execution_allocation": "SELECT, INSERT",
    "hours_ledger_entry": "SELECT, INSERT",
    "hours_transfer": "SELECT, INSERT, UPDATE",  # guard: PENDING -> one decision
    "hours_cancellation": "SELECT, INSERT, UPDATE",  # guard: PENDING -> one decision
}
APPEND_ONLY = ["payment_evidence", "work_execution_allocation", "hours_ledger_entry"]
GUARDED = {
    "hours_reason_code": "guard_hours_reason_code",
    "customer_discount": "guard_hours_proposal",
    "credit_arrangement": "guard_hours_proposal",
    "hours_purchase": "guard_hours_purchase",
    "hours_payment_allocation": "guard_released_once",  # shared with hire_payment_allocation (gate 5)
    "hours_transfer": "guard_hours_request",
    "hours_cancellation": "guard_hours_request",
}
OWN_FUNCTIONS = ["guard_hours_reason_code", "guard_hours_proposal", "guard_hours_purchase", "guard_hours_request"]
HOURS_SEED = (
    '{"enabled": true, "walk_in_allowed": true, "billing_modes": ["PREPAID_HOURS", "INVOICE"], '
    '"default_billing_mode": "INVOICE", "activation_basis": ["VERIFIED_PAYMENT", "CREDIT"], '
    '"partial_activation": true, "hours_increment": "0.01", "expiry_days": null, "expiry_warning_days": 7, '
    '"over_consumption": "BLOCK_START", "overrun_exception_blocking": true, "transfer_requires_approval": true, '
    '"cancellation_requires_approval": true, "cancellation_after_consumption_allowed": false, '
    '"discount_requires_approval": true, "max_discount_percent": "100", "credit_allowed": true, '
    '"reason_code_required": false}'
)
DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)


def upgrade() -> None:
    op.execute(f"""
        CREATE FUNCTION guard_hours_reason_code() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id OR NEW.kind <> OLD.kind
             OR NEW.created_at <> OLD.created_at THEN
            {DENY};
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_hours_proposal() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[];
        BEGIN
          IF TG_OP = 'DELETE' THEN {DENY}; END IF;
          IF OLD.status = 'PROPOSED' AND NEW.status = 'PROPOSED' THEN
            mutable := ARRAY['percent','limit_amount','effective_from','effective_to','terms','reason',
                             'reason_code_id','version'];
          ELSIF OLD.status = 'PROPOSED' AND NEW.status IN ('APPROVED', 'REJECTED', 'WITHDRAWN') THEN
            mutable := ARRAY['status','decided_by','decided_at','decision_note','version'];
          ELSIF OLD.status = 'APPROVED' AND NEW.status = 'REVOKED' THEN
            mutable := ARRAY['status','revoked_by','revoked_at','revoke_reason','version'];
          ELSE
            RAISE EXCEPTION 'asseta: % -> % is not permitted on %', OLD.status, NEW.status, TG_TABLE_NAME
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: decided terms are immutable' USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_hours_purchase() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[] := ARRAY['cancelled_at','cancelled_by','cancellation_id'];
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.cancelled_at IS NOT NULL OR NEW.cancelled_at IS NULL
             OR (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: an hours purchase is immutable (only a single cancellation stamp)'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_hours_request() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[] := ARRAY['status','decided_by','decided_at','decision_note'];
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'PENDING' OR NEW.status NOT IN ('APPROVED', 'REJECTED', 'WITHDRAWN')
             OR (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: a request is decided once and its content is immutable'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
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
        SELECT gen_random_uuid(), 'CUSTOMER_HOURS', 'PLATFORM', NULL, NULL, 1, TIMESTAMPTZ '2000-01-01 00:00:00+00',
               '{HOURS_SEED}'::jsonb, 'Seeded platform default (replaceable configuration)', now(), 'migration'
        WHERE NOT EXISTS (SELECT 1 FROM policy_version WHERE policy_type = 'CUSTOMER_HOURS' AND scope = 'PLATFORM');
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
    for fn in OWN_FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS {fn}()")
    # The CUSTOMER_HOURS platform seed is immutable (policy_version trigger) and harmless; re-upgrade is idempotent.
