"""DEC-022 security: FORCE RLS + explicit grants (never DELETE) on the new commerce and notification tables,
immutability/transition guards, and the extended platform-invoice snapshot guard (kind/notes frozen; void once,
VOIDED terminal).

Revision ID: d22sec000001
Revises: 196f8f7dc42b
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d22sec000001"
down_revision: str | None = "196f8f7dc42b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS: dict[str, str] = {
    "platform_product": "SELECT, INSERT, UPDATE",  # lifecycle: deactivate/reactivate, never delete
    "platform_line_allocation": "SELECT, INSERT, UPDATE",  # guard: release once
    "platform_line_fulfilment": "SELECT, INSERT, UPDATE",  # guard: FULFILLED -> REVERSED/REVERSAL_FLAGGED only
    "sms_wallet_entry": "SELECT, INSERT",  # append-only ledger
    "platform_membership": "SELECT, INSERT, UPDATE",  # effective-dated mirror (closed, never deleted)
    "notification": "SELECT, INSERT, UPDATE",  # guard: only read_at changes
    "notification_preference": "SELECT, INSERT, UPDATE",
    "notification_profile": "SELECT, INSERT, UPDATE",
    "sms_delivery": "SELECT, INSERT, UPDATE",  # guard: message content immutable
}
PLATFORM = "app_scope() IN ('platform', 'system')"
OWN = "(app_scope() = 'tenant' AND tenant_id = app_tenant_id())"
SYSTEM = "app_scope() = 'system'"
ACTOR = "app_actor_id()"
POLICIES: dict[str, list[str]] = {
    "platform_product": [f"CREATE POLICY p_platform ON platform_product USING ({PLATFORM}) WITH CHECK ({PLATFORM})"],
    **{
        t: [
            f"CREATE POLICY p_platform ON {t} USING ({PLATFORM}) WITH CHECK ({PLATFORM})",
            f"CREATE POLICY p_tenant_read ON {t} FOR SELECT USING ({OWN})",
        ]
        for t in ("platform_line_allocation", "platform_line_fulfilment", "sms_wallet_entry")
    },
    "notification": [
        "CREATE POLICY p_recipient ON notification USING ({c}) WITH CHECK ({c})".format(
            c=f"{SYSTEM} OR ({OWN} AND recipient_user_id = {ACTOR})"
            f" OR (app_scope() = 'platform' AND tenant_id IS NULL AND recipient_user_id = {ACTOR})"
        )
    ],
    "notification_preference": [
        "CREATE POLICY p_owner ON notification_preference USING ({c}) WITH CHECK ({c})".format(
            c=f"{SYSTEM} OR ({OWN} AND (user_id = {ACTOR} OR user_id IS NULL))"
            f" OR (app_scope() = 'platform' AND tenant_id IS NULL AND user_id = {ACTOR})"
        )
    ],
    "notification_profile": [
        "CREATE POLICY p_owner ON notification_profile USING ({c}) WITH CHECK ({c})".format(
            c=f"{SYSTEM} OR (app_scope() IN ('tenant', 'platform') AND user_id = {ACTOR})"
        )
    ],
    "sms_delivery": [
        f"CREATE POLICY p_read ON sms_delivery FOR SELECT USING ({SYSTEM} OR {OWN}"
        " OR (app_scope() = 'platform' AND tenant_id IS NULL))",
        "CREATE POLICY p_write ON sms_delivery FOR INSERT WITH CHECK"
        f" ({SYSTEM} OR (app_scope() = 'platform' AND tenant_id IS NULL))",
        f"CREATE POLICY p_update ON sms_delivery FOR UPDATE USING ({SYSTEM}) WITH CHECK ({SYSTEM})",
    ],
}
RLS_TABLES = [t for t in GRANTS if t != "platform_membership"]  # identity mirrors carry no tenant data
DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)
OLD_INVOICE_GUARD = """
CREATE OR REPLACE FUNCTION guard_platform_invoice() RETURNS trigger LANGUAGE plpgsql AS
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
"""
NEW_INVOICE_GUARD = """
CREATE OR REPLACE FUNCTION guard_platform_invoice() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
     IF (NEW.tenant_id, NEW.subscription_id, NEW.rate_version_id, NEW.invoice_number, NEW.period_start,
         NEW.period_end, NEW.currency, NEW.billable_assets, NEW.enrolled_assets, NEW.subtotal,
         NEW.discount_total, NEW.tax_total, NEW.total, NEW.issued_at, NEW.due_date, NEW.kind, NEW.notes)
        IS DISTINCT FROM
        (OLD.tenant_id, OLD.subscription_id, OLD.rate_version_id, OLD.invoice_number, OLD.period_start,
         OLD.period_end, OLD.currency, OLD.billable_assets, OLD.enrolled_assets, OLD.subtotal,
         OLD.discount_total, OLD.tax_total, OLD.total, OLD.issued_at, OLD.due_date, OLD.kind, OLD.notes) THEN
       RAISE EXCEPTION 'asseta: issued invoice snapshot is immutable' USING ERRCODE = 'insufficient_privilege';
     END IF;
     IF OLD.status = 'VOIDED' AND (NEW.status <> 'VOIDED'
          OR (NEW.voided_at, NEW.voided_by, NEW.void_reason) IS DISTINCT FROM
             (OLD.voided_at, OLD.voided_by, OLD.void_reason)) THEN
       RAISE EXCEPTION 'asseta: a voided invoice is final' USING ERRCODE = 'insufficient_privilege';
     END IF;
     IF NEW.status = 'VOIDED' AND (NEW.voided_at IS NULL OR NEW.void_reason IS NULL) THEN
       RAISE EXCEPTION 'asseta: voiding requires time and reason' USING ERRCODE = 'insufficient_privilege';
     END IF;
     IF OLD.status <> 'VOIDED' AND NEW.status <> 'VOIDED' AND (NEW.voided_at IS NOT NULL OR NEW.void_reason IS NOT NULL)
     THEN
       RAISE EXCEPTION 'asseta: void fields are set only by voiding' USING ERRCODE = 'insufficient_privilege';
     END IF;
     RETURN NEW;
   END $$;
"""


def upgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE FUNCTION app_actor_id() RETURNS uuid LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.actor_id', true), '')::uuid $$;
        {NEW_INVOICE_GUARD}
        CREATE FUNCTION guard_line_fulfilment() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'FULFILLED' OR NEW.status NOT IN ('REVERSED', 'REVERSAL_FLAGGED')
             OR (to_jsonb(NEW) - ARRAY['status','reversed_at','reversal_note','effect'])
                IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','reversed_at','reversal_note','effect']) THEN
            {DENY};
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_notification_read() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR (to_jsonb(NEW) - 'read_at') IS DISTINCT FROM (to_jsonb(OLD) - 'read_at') THEN
            {DENY};
          END IF;
          RETURN NEW;
        END $$;
        CREATE FUNCTION guard_sms_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[] := ARRAY['status','attempts','next_attempt_at','last_error','provider','sent_at',
                                        'updated_at'];
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'PENDING'
             OR (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            {DENY};
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER trg_platform_line_allocation_guard BEFORE UPDATE OR DELETE ON platform_line_allocation
          FOR EACH ROW EXECUTE FUNCTION guard_released_once();
        CREATE TRIGGER trg_platform_line_fulfilment_guard BEFORE UPDATE OR DELETE ON platform_line_fulfilment
          FOR EACH ROW EXECUTE FUNCTION guard_line_fulfilment();
        CREATE TRIGGER trg_sms_wallet_entry_immutable BEFORE UPDATE OR DELETE ON sms_wallet_entry
          FOR EACH ROW EXECUTE FUNCTION reject_mutation();
        CREATE TRIGGER trg_notification_guard BEFORE UPDATE OR DELETE ON notification
          FOR EACH ROW EXECUTE FUNCTION guard_notification_read();
        CREATE TRIGGER trg_sms_delivery_guard BEFORE UPDATE OR DELETE ON sms_delivery
          FOR EACH ROW EXECUTE FUNCTION guard_sms_delivery();
    """)
    for t in RLS_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        for stmt in POLICIES[t]:
            op.execute(stmt)
    grants = "\n".join(f"REVOKE ALL ON {t} FROM asseta_app; GRANT {p} ON {t} TO asseta_app;" for t, p in GRANTS.items())
    op.execute(f"""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN
            {grants}
          END IF;
        END $$;
    """)


def downgrade() -> None:
    for t in RLS_TABLES:
        for name in ("p_platform", "p_tenant_read", "p_recipient", "p_owner", "p_read", "p_write", "p_update"):
            op.execute(f"DROP POLICY IF EXISTS {name} ON {t}")
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY; ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
    op.execute(f"""
        DROP TRIGGER IF EXISTS trg_platform_line_allocation_guard ON platform_line_allocation;
        DROP TRIGGER IF EXISTS trg_platform_line_fulfilment_guard ON platform_line_fulfilment;
        DROP TRIGGER IF EXISTS trg_sms_wallet_entry_immutable ON sms_wallet_entry;
        DROP TRIGGER IF EXISTS trg_notification_guard ON notification;
        DROP TRIGGER IF EXISTS trg_sms_delivery_guard ON sms_delivery;
        DROP FUNCTION IF EXISTS guard_line_fulfilment();
        DROP FUNCTION IF EXISTS guard_notification_read();
        DROP FUNCTION IF EXISTS guard_sms_delivery();
        DROP FUNCTION IF EXISTS app_actor_id();
        {OLD_INVOICE_GUARD}
    """)
