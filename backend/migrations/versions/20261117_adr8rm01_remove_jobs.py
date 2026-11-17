"""ADR-008 §4: jobs and everything that only existed because of them are removed (no tenant data to keep).

Dropped tables: job, job_activity, customer_acknowledgement, rental_contract (contracts), machine_changeover,
work_execution_allocation, tenant_hire_invoice, hire_invoice_line, hire_invoice_job, hire_invoice_counter,
hire_payment_allocation (job-based hire invoices; credit invoices replace them), revenue_reason, revenue_difference,
revenue_difference_adjustment, non_revenue_approval (job revenue differences) and site_checkin (site check-ins), with
their guard functions.

Dropped columns: the job links of meter_capture, hours_ledger_entry (with its work-execution allocation link and
drawdown usage day), expense, fuel_event, risk_signal, anomaly_case, cash_variance, meter_correction and
work_allocation (with its changeover link and work-log activity type); financial_adjustment.invoice_id.

Data kept readable: meter readings taken as job opening/closing readings stay as DAILY readings; risk signals and
cases whose subject was a job now name its machine; audit rows keep their text. Rows that only described removed
mechanics are deleted: provisional daily-drawdown entries of the hours ledger, hire-invoice reversal adjustments and
the platform/tenant versions of the retired REVENUE_RECONCILIATION and HIRE_BILLING policies.

`job_exception` (the review findings of meter readings) is renamed `meter_exception`.

`machine_report.opening`: an opening report (the machine's first reading, no lines, 0 hours) replaces the need for a
meter baseline before the first report.

The downgrade recreates every table, column, index, constraint, trigger, policy and grant (data removed by the
upgrade is not restored; the retired policies get their platform defaults back).

Revision ID: adr8rm01
Revises: mrep01
Create Date: 2026-11-17 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "adr8rm01"
down_revision: str | Sequence[str] | None = "mrep01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DROPPED_TABLES = (  # dependency order
    "non_revenue_approval",
    "revenue_difference_adjustment",
    "revenue_difference",
    "revenue_reason",
    "site_checkin",
    "hire_payment_allocation",
    "hire_invoice_job",
    "hire_invoice_line",
    "hire_invoice_counter",
    "tenant_hire_invoice",
    "work_execution_allocation",
    "machine_changeover",
    "customer_acknowledgement",
    "job_activity",
    "job",
    "rental_contract",
)
DROPPED_FUNCTIONS = (
    "guard_hire_invoice",
    "guard_hire_invoice_line_insert",
    "guard_revenue_difference",
    "guard_machine_changeover",
    "guard_site_checkin",
)
JOB_COLUMNS = (  # (table, has an index ix_<table>_job_id)
    ("meter_capture", True),
    ("hours_ledger_entry", True),
    ("expense", True),
    ("fuel_event", True),
    ("risk_signal", False),
    ("anomaly_case", False),
    ("cash_variance", False),
    ("meter_correction", False),
    ("work_allocation", True),
)
EXCEPTION_RENAMES = (  # constraint ("c") / index ("i") names of job_exception -> meter_exception
    ("job_exception_pkey", "meter_exception_pkey", "c"),
    ("uq_job_exception_dedupe", "uq_meter_exception_dedupe", "c"),
    ("job_exception_machine_id_fkey", "meter_exception_machine_id_fkey", "c"),
    ("job_exception_meter_capture_id_fkey", "meter_exception_meter_capture_id_fkey", "c"),
    ("job_exception_tenant_id_fkey", "meter_exception_tenant_id_fkey", "c"),
    ("ix_job_exception_status", "ix_meter_exception_status", "i"),
    ("ix_job_exception_sync_revision", "ix_meter_exception_sync_revision", "i"),
    ("ix_job_exception_meter_capture_id", "ix_meter_exception_meter_capture_id", "i"),
)
OPENING_RANGE = (
    "(opening AND hours = 0 AND start_reading = end_reading) OR "
    "(NOT opening AND hours > 0 AND end_reading - start_reading = hours)"
)
RETIRED_POLICIES = {
    "HIRE_BILLING": '{"rounding": "HALF_UP", "billable_hours_increment": "0.1", "invoice_void_requires_approval": true}',
    "REVENUE_RECONCILIATION": (
        '{"basis": "INVOICED_OR_PREPAID", "period": "WEEK", "enabled": false, "recheck_days": 28, '
        '"tolerance_amount": null, "tolerance_percent": "5", "case_threshold_amount": null, '
        '"unexplained_hours_rate": null, "non_revenue_activity_types": ["MOBILIZATION"], '
        '"unexplained_hours_treatment": "VALUE_AT_RISK", "unexplained_hours_rate_source": "MACHINE_RATE_CARD", '
        '"deduct_non_revenue_from_working_hours": false, "deduct_non_revenue_from_prepaid_hours": false, '
        '"non_revenue_requires_approval": true, "non_revenue_evidence_required": false}'
    ),
}


def _without_trigger(table: str, trigger: str, sql: str) -> None:
    """Run a one-off data step on an append-only table (its guard trigger refuses it otherwise)."""
    op.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
    op.execute(sql)
    op.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")


def upgrade() -> None:
    # Signals and cases whose subject was a job now name the job's machine (their history stays readable).
    for table, trigger in (("risk_signal", "trg_risk_signal_guard"), ("anomaly_case", "trg_anomaly_case_guard")):
        _without_trigger(
            table,
            trigger,
            f"UPDATE {table} t SET subject_type = 'MACHINE', "
            f"subject_id = COALESCE(t.machine_id, (SELECT j.machine_id FROM job j WHERE j.id = t.subject_id)) "
            f"WHERE t.subject_type = 'JOB'",
        )
    # Job opening/closing readings stay as the machine's readings.
    _without_trigger(
        "meter_capture",
        "trg_meter_capture_guard",
        "UPDATE meter_capture SET kind = 'DAILY' WHERE kind IN ('OPENING', 'CLOSING')",
    )
    op.drop_index("uq_meter_capture_job_kind_active", table_name="meter_capture")
    op.drop_constraint("ck_meter_capture_job_reading", "meter_capture", type_="check")
    # Daily drawdown of running jobs is gone: its provisional entries no longer hold hours.
    _without_trigger(
        "hours_ledger_entry",
        "trg_hours_ledger_entry_immutable",
        "DELETE FROM hours_ledger_entry WHERE entry_type IN ('PROVISIONAL', 'PROVISIONAL_REVERSED')",
    )
    op.drop_index("ix_hours_ledger_job_type", table_name="hours_ledger_entry")
    op.drop_index("ix_hours_ledger_entry_allocation_id", table_name="hours_ledger_entry")
    op.drop_column("hours_ledger_entry", "allocation_id")
    op.drop_column("hours_ledger_entry", "usage_day")
    # Hire invoices are gone: their reversals no longer adjust anything.
    _without_trigger(
        "financial_adjustment",
        "trg_financial_adjustment_immutable",
        "DELETE FROM financial_adjustment WHERE kind = 'INVOICE_REVERSAL'",
    )
    op.drop_column("financial_adjustment", "invoice_id")
    for table, _ in JOB_COLUMNS:
        op.drop_column(table, "job_id")  # its index and foreign key go with it
    op.drop_column("work_allocation", "changeover_id")
    op.drop_column("work_allocation", "activity_type")
    op.drop_column("job_exception", "job_id")
    for table in DROPPED_TABLES:
        op.execute(f"DROP TABLE {table}")
    for fn in DROPPED_FUNCTIONS:
        op.execute(f"DROP FUNCTION {fn}()")
    # The review findings of meter readings keep their rows under their own name.
    op.rename_table("job_exception", "meter_exception")
    for old, new, kind in EXCEPTION_RENAMES:
        if kind == "c":
            op.execute(f"ALTER TABLE meter_exception RENAME CONSTRAINT {old} TO {new}")
        else:
            op.execute(f"ALTER INDEX {old} RENAME TO {new}")
    op.execute("ALTER FUNCTION guard_job_exception() RENAME TO guard_meter_exception")
    op.execute("ALTER TRIGGER trg_job_exception_guard ON meter_exception RENAME TO trg_meter_exception_guard")
    op.execute(
        "ALTER TRIGGER trg_job_exception_sync_revision ON meter_exception RENAME TO trg_meter_exception_sync_revision"
    )
    # Opening reports: the first reading of a machine without a starting point (0 hours, no lines).
    op.add_column("machine_report", sa.Column("opening", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.drop_constraint("ck_machine_report_range", "machine_report", type_="check")
    op.create_check_constraint("ck_machine_report_range", "machine_report", OPENING_RANGE)
    # Retired policy types (every rule was about jobs or hire invoices).
    _without_trigger(
        "policy_version",
        "trg_policy_version_immutable",
        "DELETE FROM policy_version WHERE policy_type IN ('REVENUE_RECONCILIATION', 'HIRE_BILLING')",
    )


def downgrade() -> None:
    # The data steps below need the system scope under FORCE row-level security (adr8fix01 explains the upgrade's).
    op.execute("SELECT set_config('app.scope', 'system', true)")
    _without_trigger("machine_report", "trg_machine_report_guard", "DELETE FROM machine_report WHERE opening")
    op.drop_constraint("ck_machine_report_range", "machine_report", type_="check")
    op.create_check_constraint(
        "ck_machine_report_range", "machine_report", "hours > 0 AND end_reading - start_reading = hours"
    )
    op.drop_column("machine_report", "opening")
    op.execute(
        "ALTER TRIGGER trg_meter_exception_sync_revision ON meter_exception RENAME TO trg_job_exception_sync_revision"
    )
    op.execute("ALTER TRIGGER trg_meter_exception_guard ON meter_exception RENAME TO trg_job_exception_guard")
    op.execute("ALTER FUNCTION guard_meter_exception() RENAME TO guard_job_exception")
    for old, new, kind in EXCEPTION_RENAMES:
        if kind == "c":
            op.execute(f"ALTER TABLE meter_exception RENAME CONSTRAINT {new} TO {old}")
        else:
            op.execute(f"ALTER INDEX {new} RENAME TO {old}")
    op.rename_table("meter_exception", "job_exception")
    for stmt in DROPPED_DDL:
        op.execute(stmt)
    op.add_column("job_exception", sa.Column("job_id", sa.UUID(), sa.ForeignKey("job.id"), nullable=True))
    op.create_index("ix_job_exception_job_id", "job_exception", ["job_id"])
    for table, indexed in JOB_COLUMNS:
        name = "fk_cash_variance_job" if table == "cash_variance" else f"{table}_job_id_fkey"
        op.add_column(table, sa.Column("job_id", sa.UUID(), nullable=True))
        op.create_foreign_key(name, table, "job", ["job_id"], ["id"])
        if indexed:
            op.create_index(f"ix_{table}_job_id", table, ["job_id"])
    op.add_column("work_allocation", sa.Column("activity_type", sa.String(length=24), nullable=True))
    op.add_column(
        "work_allocation",
        sa.Column("changeover_id", sa.UUID(), sa.ForeignKey("machine_changeover.id"), nullable=True),
    )
    op.add_column(
        "financial_adjustment",
        sa.Column("invoice_id", sa.UUID(), sa.ForeignKey("tenant_hire_invoice.id"), nullable=True),
    )
    op.add_column(
        "hours_ledger_entry",
        sa.Column("allocation_id", sa.UUID(), sa.ForeignKey("work_execution_allocation.id"), nullable=True),
    )
    op.create_index("ix_hours_ledger_entry_allocation_id", "hours_ledger_entry", ["allocation_id"])
    op.add_column("hours_ledger_entry", sa.Column("usage_day", sa.Date(), nullable=True))
    op.create_index("ix_hours_ledger_job_type", "hours_ledger_entry", ["job_id", "entry_type"])
    op.create_check_constraint("ck_meter_capture_job_reading", "meter_capture", "kind = 'DAILY' OR job_id IS NOT NULL")
    op.create_index(
        "uq_meter_capture_job_kind_active",
        "meter_capture",
        ["job_id", "kind"],
        unique=True,
        postgresql_where=sa.text("state IN ('ACCEPTED', 'PROVISIONAL') AND kind <> 'DAILY'"),
    )
    for ptype, values in RETIRED_POLICIES.items():
        op.execute(f"""
            INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                        values, reason, created_at, source)
            SELECT gen_random_uuid(), '{ptype}', 'PLATFORM', NULL, NULL, 1, TIMESTAMPTZ '2000-01-01 00:00:00+00',
                   '{values}'::jsonb, 'Seeded platform default (replaceable configuration)', now(), 'migration'
            WHERE NOT EXISTS (SELECT 1 FROM policy_version WHERE policy_type = '{ptype}' AND scope = 'PLATFORM')
        """)


# The schema of the dropped tables at revision mrep01 (pg_dump of a database at that revision), for the downgrade.
DROPPED_DDL: tuple[str, ...] = (
    """CREATE OR REPLACE FUNCTION public.guard_hire_invoice()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        DECLARE mutable text[];
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'; END IF;
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
        END $function$""",
    """CREATE OR REPLACE FUNCTION public.guard_hire_invoice_line_insert()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM tenant_hire_invoice i WHERE i.id = NEW.invoice_id AND i.status = 'DRAFT') THEN
            RAISE EXCEPTION 'asseta: lines can only be added to a draft hire invoice'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $function$""",
    """CREATE OR REPLACE FUNCTION public.guard_revenue_difference()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status NOT IN ('OPEN', 'EXPLANATION_PROPOSED')
             OR ROW(NEW.tenant_id, NEW.machine_id, NEW.period_kind, NEW.period_key, NEW.period_start, NEW.period_end, NEW.local_from, NEW.local_to, NEW.job_id, NEW.currency, NEW.policy_version, NEW.opened_at) IS DISTINCT FROM ROW(OLD.tenant_id, OLD.machine_id, OLD.period_kind, OLD.period_key, OLD.period_start, OLD.period_end, OLD.local_from, OLD.local_to, OLD.job_id, OLD.currency, OLD.policy_version, OLD.opened_at) THEN
            RAISE EXCEPTION 'asseta: a decided revenue difference is final and its evidence is immutable'
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $function$""",
    """CREATE OR REPLACE FUNCTION public.guard_machine_changeover()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
          RAISE EXCEPTION 'asseta: a changeover is a record of fact (append-only)'
            USING ERRCODE = 'insufficient_privilege';
        END $function$""",
    """CREATE OR REPLACE FUNCTION public.guard_site_checkin()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
          RAISE EXCEPTION 'asseta: a site check-in is a record of fact (append-only)'
            USING ERRCODE = 'insufficient_privilege';
        END $function$""",
    """CREATE TABLE customer_acknowledgement (
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    client_id uuid NOT NULL,
    method character varying(24) NOT NULL,
    signer_name character varying(200) NOT NULL,
    signer_phone character varying(40),
    signature_attachment_id uuid,
    acknowledged_hours numeric(12,2),
    captured_at timestamp with time zone NOT NULL,
    received_at timestamp with time zone NOT NULL,
    recorded_by uuid,
    id uuid NOT NULL,
    sync_revision bigint DEFAULT nextval('sync_revision_seq'::regclass) NOT NULL
)""",
    """ALTER TABLE ONLY customer_acknowledgement FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE hire_invoice_counter (
    tenant_id uuid NOT NULL,
    year integer NOT NULL,
    last_number integer NOT NULL
)""",
    """ALTER TABLE ONLY hire_invoice_counter FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE hire_invoice_job (
    tenant_id uuid NOT NULL,
    invoice_id uuid NOT NULL,
    job_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    released_at timestamp with time zone,
    id uuid NOT NULL
)""",
    """ALTER TABLE ONLY hire_invoice_job FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE hire_invoice_line (
    invoice_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    line_no integer NOT NULL,
    kind character varying(24) NOT NULL,
    job_id uuid NOT NULL,
    machine_id uuid NOT NULL,
    description character varying(300) NOT NULL,
    quantity numeric(18,6) NOT NULL,
    unit_price numeric(18,4) NOT NULL,
    amount numeric(18,4) NOT NULL,
    id uuid NOT NULL
)""",
    """ALTER TABLE ONLY hire_invoice_line FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE hire_payment_allocation (
    tenant_id uuid NOT NULL,
    payment_id uuid NOT NULL,
    invoice_id uuid NOT NULL,
    amount numeric(18,4) NOT NULL,
    created_by uuid,
    created_at timestamp with time zone NOT NULL,
    released_at timestamp with time zone,
    release_reason text,
    id uuid NOT NULL,
    CONSTRAINT ck_hire_allocation_amount CHECK ((amount > (0)::numeric))
)""",
    """ALTER TABLE ONLY hire_payment_allocation FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE job (
    tenant_id uuid NOT NULL,
    contract_id uuid NOT NULL,
    job_number character varying(40) NOT NULL,
    machine_id uuid NOT NULL,
    job_site_id uuid,
    supervisor_id uuid,
    status character varying(24) NOT NULL,
    planned_start timestamp with time zone NOT NULL,
    planned_end timestamp with time zone,
    currency character varying(3) NOT NULL,
    hourly_rate numeric(18,4) NOT NULL,
    minimum_hours numeric(12,2) NOT NULL,
    standby_treatment character varying(24) NOT NULL,
    standby_rate numeric(18,4),
    mobilization_fee numeric(18,4) NOT NULL,
    discount_percent numeric(7,4) NOT NULL,
    tax_rate_percent numeric(7,4) NOT NULL,
    rate_source character varying(64) NOT NULL,
    approved_by uuid,
    approved_at timestamp with time zone,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    cancellation_reason text,
    version integer NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    sync_revision bigint DEFAULT nextval('sync_revision_seq'::regclass) NOT NULL,
    requested_by_staff_id uuid,
    request_note text,
    billing_mode character varying(16) DEFAULT 'INVOICE'::character varying NOT NULL,
    hours_purchase_id uuid,
    CONSTRAINT ck_job_percentages CHECK ((((discount_percent >= (0)::numeric) AND (discount_percent <= (100)::numeric)) AND ((tax_rate_percent >= (0)::numeric) AND (tax_rate_percent <= (100)::numeric)))),
    CONSTRAINT ck_job_terms CHECK (((hourly_rate >= (0)::numeric) AND (minimum_hours >= (0)::numeric) AND (mobilization_fee >= (0)::numeric)))
)""",
    """ALTER TABLE ONLY job FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE job_activity (
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    client_id uuid NOT NULL,
    activity_type character varying(24) NOT NULL,
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    billable boolean NOT NULL,
    note text,
    recorded_by uuid,
    device_id character varying(128),
    received_at timestamp with time zone NOT NULL,
    id uuid NOT NULL,
    sync_revision bigint DEFAULT nextval('sync_revision_seq'::regclass) NOT NULL,
    CONSTRAINT ck_activity_times CHECK (((ended_at IS NULL) OR (ended_at >= started_at)))
)""",
    """ALTER TABLE ONLY job_activity FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE machine_changeover (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    machine_id uuid NOT NULL,
    capture_id uuid NOT NULL,
    job_id uuid NOT NULL,
    from_customer_id uuid NOT NULL,
    to_customer_id uuid NOT NULL,
    to_job_id uuid,
    recorded_by uuid,
    created_at timestamp with time zone NOT NULL
)""",
    """ALTER TABLE ONLY machine_changeover FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE non_revenue_approval (
    tenant_id uuid NOT NULL,
    activity_id uuid NOT NULL,
    job_id uuid NOT NULL,
    machine_id uuid NOT NULL,
    activity_type character varying(24) NOT NULL,
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone NOT NULL,
    hours numeric(14,2) NOT NULL,
    reason_id uuid NOT NULL,
    note text NOT NULL,
    status character varying(16) NOT NULL,
    proposed_by uuid,
    proposed_at timestamp with time zone NOT NULL,
    decided_by uuid,
    decided_at timestamp with time zone,
    decision_note text,
    policy_version character varying(80) NOT NULL,
    id uuid NOT NULL,
    evidence_attachment_ids uuid[] NOT NULL,
    CONSTRAINT ck_non_revenue_approval_status CHECK (((status)::text = ANY ((ARRAY['PROPOSED'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying])::text[])))
)""",
    """ALTER TABLE ONLY non_revenue_approval FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE rental_contract (
    tenant_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    contract_number character varying(40) NOT NULL,
    job_site_id uuid,
    currency character varying(3) NOT NULL,
    status character varying(24) NOT NULL,
    starts_on timestamp with time zone NOT NULL,
    ends_on timestamp with time zone,
    reference character varying(200),
    notes text,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    sync_revision bigint DEFAULT nextval('sync_revision_seq'::regclass) NOT NULL,
    version integer NOT NULL,
    closed_at timestamp with time zone,
    closed_by uuid,
    close_reason text
)""",
    """ALTER TABLE ONLY rental_contract FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE revenue_difference (
    tenant_id uuid NOT NULL,
    machine_id uuid NOT NULL,
    period_kind character varying(8) NOT NULL,
    period_key character varying(64) NOT NULL,
    period_start timestamp with time zone NOT NULL,
    period_end timestamp with time zone NOT NULL,
    local_from date NOT NULL,
    local_to date NOT NULL,
    job_id uuid,
    currency character varying(3) NOT NULL,
    expected_amount numeric(18,4) NOT NULL,
    in_progress_amount numeric(18,4) NOT NULL,
    attributed_amount numeric(18,4) NOT NULL,
    difference numeric(18,4) NOT NULL,
    customer_work_hours numeric(14,2) NOT NULL,
    non_revenue_hours numeric(14,2) NOT NULL,
    unexplained_hours numeric(14,2) NOT NULL,
    unexplained_expected_amount numeric(18,4) NOT NULL,
    detail jsonb NOT NULL,
    status character varying(24) NOT NULL,
    case_id uuid,
    policy_version character varying(80) NOT NULL,
    opened_at timestamp with time zone NOT NULL,
    computed_at timestamp with time zone NOT NULL,
    reason_id uuid,
    explanation_note text,
    explained_by uuid,
    explained_at timestamp with time zone,
    decided_by uuid,
    decided_at timestamp with time zone,
    decision_note text,
    id uuid NOT NULL,
    value_at_risk_amount numeric(18,4) DEFAULT '0'::numeric NOT NULL,
    CONSTRAINT ck_revenue_difference_period_kind CHECK (((period_kind)::text = ANY ((ARRAY['DAY'::character varying, 'WEEK'::character varying, 'JOB'::character varying])::text[]))),
    CONSTRAINT ck_revenue_difference_status CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'EXPLANATION_PROPOSED'::character varying, 'EXPLAINED'::character varying, 'CONFIRMED'::character varying, 'CLEARED'::character varying])::text[])))
)""",
    """ALTER TABLE ONLY revenue_difference FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE revenue_difference_adjustment (
    tenant_id uuid NOT NULL,
    difference_id uuid NOT NULL,
    previous_difference numeric(18,4) NOT NULL,
    new_difference numeric(18,4) NOT NULL,
    amount numeric(18,4) NOT NULL,
    cause_type character varying(40) NOT NULL,
    cause_id uuid NOT NULL,
    detail jsonb NOT NULL,
    created_by uuid,
    created_at timestamp with time zone NOT NULL,
    id uuid NOT NULL
)""",
    """ALTER TABLE ONLY revenue_difference_adjustment FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE revenue_reason (
    tenant_id uuid NOT NULL,
    code character varying(32) NOT NULL,
    name character varying(120) NOT NULL,
    description text,
    is_active boolean NOT NULL,
    version integer NOT NULL,
    id uuid NOT NULL,
    deactivated_at timestamp with time zone,
    deactivated_by uuid,
    deactivation_reason text,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
)""",
    """ALTER TABLE ONLY revenue_reason FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE site_checkin (
    id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    client_id uuid NOT NULL,
    staff_member_id uuid NOT NULL,
    recorded_by uuid NOT NULL,
    captured_at timestamp with time zone NOT NULL,
    received_at timestamp with time zone NOT NULL,
    gps_status character varying(20) NOT NULL,
    latitude double precision,
    longitude double precision,
    accuracy_m double precision,
    job_site_id uuid,
    job_id uuid,
    distance_m double precision,
    source character varying(8) NOT NULL,
    device_session_id uuid,
    created_at timestamp with time zone NOT NULL
)""",
    """ALTER TABLE ONLY site_checkin FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE tenant_hire_invoice (
    tenant_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    invoice_number character varying(40),
    status character varying(24) NOT NULL,
    currency character varying(3) NOT NULL,
    subtotal numeric(18,4) NOT NULL,
    discount_total numeric(18,4) NOT NULL,
    tax_total numeric(18,4) NOT NULL,
    total numeric(18,4) NOT NULL,
    notes text,
    due_date date,
    created_by uuid,
    created_at timestamp with time zone NOT NULL,
    issued_by uuid,
    issued_at timestamp with time zone,
    voided_by uuid,
    voided_at timestamp with time zone,
    void_reason text,
    id uuid NOT NULL,
    CONSTRAINT ck_hire_invoice_numbered CHECK (((issued_at IS NULL) = (invoice_number IS NULL)))
)""",
    """ALTER TABLE ONLY tenant_hire_invoice FORCE ROW LEVEL SECURITY""",
    """CREATE TABLE work_execution_allocation (
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    customer_id uuid NOT NULL,
    machine_id uuid NOT NULL,
    billable_hours numeric(12,2) NOT NULL,
    exception_id uuid,
    policy_version character varying(80) NOT NULL,
    created_by uuid,
    created_at timestamp with time zone NOT NULL,
    id uuid NOT NULL,
    CONSTRAINT ck_wea_hours CHECK ((billable_hours >= (0)::numeric))
)""",
    """ALTER TABLE ONLY work_execution_allocation FORCE ROW LEVEL SECURITY""",
    """ALTER TABLE ONLY customer_acknowledgement
    ADD CONSTRAINT customer_acknowledgement_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT ex_job_machine_window EXCLUDE USING gist (tenant_id WITH =, machine_id WITH =, tstzrange(planned_start,
CASE
    WHEN ((planned_end IS NULL) OR (planned_end <= planned_start)) THEN 'infinity'::timestamp with time zone
    ELSE planned_end
END, '[)'::text) WITH &&) WHERE (((status)::text = ANY ((ARRAY['APPROVED'::character varying, 'IN_PROGRESS'::character varying])::text[])))""",
    """ALTER TABLE ONLY hire_invoice_counter
    ADD CONSTRAINT hire_invoice_counter_pkey PRIMARY KEY (tenant_id, year)""",
    """ALTER TABLE ONLY hire_invoice_job
    ADD CONSTRAINT hire_invoice_job_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY hire_invoice_line
    ADD CONSTRAINT hire_invoice_line_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY hire_payment_allocation
    ADD CONSTRAINT hire_payment_allocation_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY job_activity
    ADD CONSTRAINT job_activity_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT job_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT machine_changeover_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY non_revenue_approval
    ADD CONSTRAINT non_revenue_approval_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY rental_contract
    ADD CONSTRAINT rental_contract_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY revenue_difference_adjustment
    ADD CONSTRAINT revenue_difference_adjustment_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY revenue_difference
    ADD CONSTRAINT revenue_difference_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY revenue_reason
    ADD CONSTRAINT revenue_reason_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY site_checkin
    ADD CONSTRAINT site_checkin_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY tenant_hire_invoice
    ADD CONSTRAINT tenant_hire_invoice_pkey PRIMARY KEY (id)""",
    """ALTER TABLE ONLY customer_acknowledgement
    ADD CONSTRAINT uq_ack_client UNIQUE (tenant_id, client_id)""",
    """ALTER TABLE ONLY rental_contract
    ADD CONSTRAINT uq_contract_number UNIQUE (tenant_id, contract_number)""",
    """ALTER TABLE ONLY hire_invoice_line
    ADD CONSTRAINT uq_hire_invoice_line_no UNIQUE (invoice_id, line_no)""",
    """ALTER TABLE ONLY tenant_hire_invoice
    ADD CONSTRAINT uq_hire_invoice_number UNIQUE (tenant_id, invoice_number)""",
    """ALTER TABLE ONLY job_activity
    ADD CONSTRAINT uq_job_activity_client UNIQUE (tenant_id, client_id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT uq_job_number UNIQUE (tenant_id, job_number)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT uq_machine_changeover_capture UNIQUE (capture_id)""",
    """ALTER TABLE ONLY revenue_difference
    ADD CONSTRAINT uq_revenue_difference_period UNIQUE (tenant_id, machine_id, period_key, currency)""",
    """ALTER TABLE ONLY revenue_reason
    ADD CONSTRAINT uq_revenue_reason_code UNIQUE (tenant_id, code)""",
    """ALTER TABLE ONLY site_checkin
    ADD CONSTRAINT uq_site_checkin_client UNIQUE (tenant_id, client_id)""",
    """ALTER TABLE ONLY work_execution_allocation
    ADD CONSTRAINT uq_work_execution_allocation_job UNIQUE (job_id)""",
    """ALTER TABLE ONLY work_execution_allocation
    ADD CONSTRAINT work_execution_allocation_pkey PRIMARY KEY (id)""",
    """CREATE INDEX ix_customer_acknowledgement_job_id ON customer_acknowledgement USING btree (job_id)""",
    """CREATE INDEX ix_customer_acknowledgement_sync_revision ON customer_acknowledgement USING btree (sync_revision)""",
    """CREATE INDEX ix_customer_acknowledgement_tenant_id ON customer_acknowledgement USING btree (tenant_id)""",
    """CREATE INDEX ix_hire_invoice_job_invoice_id ON hire_invoice_job USING btree (invoice_id)""",
    """CREATE INDEX ix_hire_invoice_job_tenant_id ON hire_invoice_job USING btree (tenant_id)""",
    """CREATE INDEX ix_hire_invoice_line_invoice_id ON hire_invoice_line USING btree (invoice_id)""",
    """CREATE INDEX ix_hire_invoice_line_job_id ON hire_invoice_line USING btree (job_id)""",
    """CREATE INDEX ix_hire_invoice_line_tenant_id ON hire_invoice_line USING btree (tenant_id)""",
    """CREATE INDEX ix_hire_payment_allocation_invoice_id ON hire_payment_allocation USING btree (invoice_id)""",
    """CREATE INDEX ix_hire_payment_allocation_payment_id ON hire_payment_allocation USING btree (payment_id)""",
    """CREATE INDEX ix_hire_payment_allocation_tenant_id ON hire_payment_allocation USING btree (tenant_id)""",
    """CREATE INDEX ix_job_activity_job_id ON job_activity USING btree (job_id)""",
    """CREATE INDEX ix_job_activity_sync_revision ON job_activity USING btree (sync_revision)""",
    """CREATE INDEX ix_job_activity_tenant_id ON job_activity USING btree (tenant_id)""",
    """CREATE INDEX ix_job_contract_id ON job USING btree (contract_id)""",
    """CREATE INDEX ix_job_hours_purchase_id ON job USING btree (hours_purchase_id)""",
    """CREATE INDEX ix_job_machine_id ON job USING btree (machine_id)""",
    """CREATE INDEX ix_job_sync_revision ON job USING btree (sync_revision)""",
    """CREATE INDEX ix_job_tenant_id ON job USING btree (tenant_id)""",
    """CREATE INDEX ix_machine_changeover_job_id ON machine_changeover USING btree (job_id)""",
    """CREATE INDEX ix_machine_changeover_machine_id ON machine_changeover USING btree (machine_id)""",
    """CREATE INDEX ix_machine_changeover_tenant_id ON machine_changeover USING btree (tenant_id)""",
    """CREATE INDEX ix_non_revenue_approval_activity_id ON non_revenue_approval USING btree (activity_id)""",
    """CREATE INDEX ix_non_revenue_approval_machine_id ON non_revenue_approval USING btree (machine_id)""",
    """CREATE INDEX ix_non_revenue_approval_status ON non_revenue_approval USING btree (tenant_id, status)""",
    """CREATE INDEX ix_rental_contract_customer_id ON rental_contract USING btree (customer_id)""",
    """CREATE INDEX ix_rental_contract_sync_revision ON rental_contract USING btree (sync_revision)""",
    """CREATE INDEX ix_rental_contract_tenant_id ON rental_contract USING btree (tenant_id)""",
    """CREATE INDEX ix_revenue_difference_adjustment_difference_id ON revenue_difference_adjustment USING btree (difference_id)""",
    """CREATE INDEX ix_revenue_difference_machine_id ON revenue_difference USING btree (machine_id)""",
    """CREATE INDEX ix_revenue_difference_status ON revenue_difference USING btree (tenant_id, status)""",
    """CREATE INDEX ix_revenue_reason_tenant_id ON revenue_reason USING btree (tenant_id)""",
    """CREATE INDEX ix_site_checkin_job_site_id ON site_checkin USING btree (job_site_id)""",
    """CREATE INDEX ix_site_checkin_staff_time ON site_checkin USING btree (tenant_id, staff_member_id, captured_at)""",
    """CREATE INDEX ix_site_checkin_tenant_id ON site_checkin USING btree (tenant_id)""",
    """CREATE INDEX ix_tenant_hire_invoice_customer_id ON tenant_hire_invoice USING btree (customer_id)""",
    """CREATE INDEX ix_tenant_hire_invoice_tenant_id ON tenant_hire_invoice USING btree (tenant_id)""",
    """CREATE INDEX ix_work_execution_allocation_customer_id ON work_execution_allocation USING btree (customer_id)""",
    """CREATE INDEX ix_work_execution_allocation_machine_id ON work_execution_allocation USING btree (machine_id)""",
    """CREATE INDEX ix_work_execution_allocation_tenant_id ON work_execution_allocation USING btree (tenant_id)""",
    """CREATE UNIQUE INDEX uq_hire_invoice_job_active ON hire_invoice_job USING btree (job_id) WHERE (released_at IS NULL)""",
    """CREATE UNIQUE INDEX uq_job_machine_running ON job USING btree (machine_id) WHERE ((status)::text = 'IN_PROGRESS'::text)""",
    """CREATE UNIQUE INDEX uq_non_revenue_approval_live ON non_revenue_approval USING btree (tenant_id, activity_id) WHERE ((status)::text = ANY ((ARRAY['PROPOSED'::character varying, 'APPROVED'::character varying])::text[]))""",
    """CREATE TRIGGER trg_customer_acknowledgement_immutable BEFORE DELETE OR UPDATE ON customer_acknowledgement FOR EACH ROW EXECUTE FUNCTION reject_mutation()""",
    """CREATE TRIGGER trg_hire_invoice_job_guard BEFORE DELETE OR UPDATE ON hire_invoice_job FOR EACH ROW EXECUTE FUNCTION guard_released_once()""",
    """CREATE TRIGGER trg_hire_invoice_line_immutable BEFORE DELETE OR UPDATE ON hire_invoice_line FOR EACH ROW EXECUTE FUNCTION reject_mutation()""",
    """CREATE TRIGGER trg_hire_invoice_line_insert BEFORE INSERT ON hire_invoice_line FOR EACH ROW EXECUTE FUNCTION guard_hire_invoice_line_insert()""",
    """CREATE TRIGGER trg_hire_payment_allocation_guard BEFORE DELETE OR UPDATE ON hire_payment_allocation FOR EACH ROW EXECUTE FUNCTION guard_released_once()""",
    """CREATE TRIGGER trg_job_activity_immutable BEFORE DELETE OR UPDATE ON job_activity FOR EACH ROW EXECUTE FUNCTION reject_mutation()""",
    """CREATE TRIGGER trg_job_sync_revision BEFORE UPDATE ON job FOR EACH ROW EXECUTE FUNCTION bump_sync_revision()""",
    """CREATE TRIGGER trg_machine_changeover_guard BEFORE DELETE OR UPDATE ON machine_changeover FOR EACH ROW EXECUTE FUNCTION guard_machine_changeover()""",
    """CREATE TRIGGER trg_non_revenue_approval_guard BEFORE DELETE OR UPDATE ON non_revenue_approval FOR EACH ROW EXECUTE FUNCTION guard_engine_hours_decision()""",
    """CREATE TRIGGER trg_rental_contract_sync_revision BEFORE UPDATE ON rental_contract FOR EACH ROW EXECUTE FUNCTION bump_sync_revision()""",
    """CREATE TRIGGER trg_revenue_difference_adjustment_immutable BEFORE DELETE OR UPDATE ON revenue_difference_adjustment FOR EACH ROW EXECUTE FUNCTION reject_mutation()""",
    """CREATE TRIGGER trg_revenue_difference_guard BEFORE DELETE OR UPDATE ON revenue_difference FOR EACH ROW EXECUTE FUNCTION guard_revenue_difference()""",
    """CREATE TRIGGER trg_revenue_reason_no_delete BEFORE DELETE ON revenue_reason FOR EACH ROW EXECUTE FUNCTION reject_mutation()""",
    """CREATE TRIGGER trg_site_checkin_guard BEFORE DELETE OR UPDATE ON site_checkin FOR EACH ROW EXECUTE FUNCTION guard_site_checkin()""",
    """CREATE TRIGGER trg_tenant_hire_invoice_guard BEFORE DELETE OR UPDATE ON tenant_hire_invoice FOR EACH ROW EXECUTE FUNCTION guard_hire_invoice()""",
    """CREATE TRIGGER trg_work_execution_allocation_immutable BEFORE DELETE OR UPDATE ON work_execution_allocation FOR EACH ROW EXECUTE FUNCTION reject_mutation()""",
    """ALTER TABLE ONLY customer_acknowledgement
    ADD CONSTRAINT customer_acknowledgement_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY customer_acknowledgement
    ADD CONSTRAINT customer_acknowledgement_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY hire_invoice_counter
    ADD CONSTRAINT hire_invoice_counter_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY hire_invoice_job
    ADD CONSTRAINT hire_invoice_job_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES tenant_hire_invoice(id)""",
    """ALTER TABLE ONLY hire_invoice_job
    ADD CONSTRAINT hire_invoice_job_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY hire_invoice_job
    ADD CONSTRAINT hire_invoice_job_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY hire_invoice_line
    ADD CONSTRAINT hire_invoice_line_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES tenant_hire_invoice(id)""",
    """ALTER TABLE ONLY hire_invoice_line
    ADD CONSTRAINT hire_invoice_line_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY hire_invoice_line
    ADD CONSTRAINT hire_invoice_line_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES machine(id)""",
    """ALTER TABLE ONLY hire_invoice_line
    ADD CONSTRAINT hire_invoice_line_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY hire_payment_allocation
    ADD CONSTRAINT hire_payment_allocation_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES tenant_hire_invoice(id)""",
    """ALTER TABLE ONLY hire_payment_allocation
    ADD CONSTRAINT hire_payment_allocation_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES customer_payment(id)""",
    """ALTER TABLE ONLY hire_payment_allocation
    ADD CONSTRAINT hire_payment_allocation_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY job_activity
    ADD CONSTRAINT job_activity_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY job_activity
    ADD CONSTRAINT job_activity_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT job_contract_id_fkey FOREIGN KEY (contract_id) REFERENCES rental_contract(id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT job_hours_purchase_id_fkey FOREIGN KEY (hours_purchase_id) REFERENCES hours_purchase(id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT job_job_site_id_fkey FOREIGN KEY (job_site_id) REFERENCES job_site(id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT job_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES machine(id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT job_requested_by_staff_id_fkey FOREIGN KEY (requested_by_staff_id) REFERENCES staff_member(id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT job_supervisor_id_fkey FOREIGN KEY (supervisor_id) REFERENCES staff_member(id)""",
    """ALTER TABLE ONLY job
    ADD CONSTRAINT job_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT machine_changeover_capture_id_fkey FOREIGN KEY (capture_id) REFERENCES meter_capture(id)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT machine_changeover_from_customer_id_fkey FOREIGN KEY (from_customer_id) REFERENCES customer(id)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT machine_changeover_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT machine_changeover_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES machine(id)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT machine_changeover_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT machine_changeover_to_customer_id_fkey FOREIGN KEY (to_customer_id) REFERENCES customer(id)""",
    """ALTER TABLE ONLY machine_changeover
    ADD CONSTRAINT machine_changeover_to_job_id_fkey FOREIGN KEY (to_job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY non_revenue_approval
    ADD CONSTRAINT non_revenue_approval_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES job_activity(id)""",
    """ALTER TABLE ONLY non_revenue_approval
    ADD CONSTRAINT non_revenue_approval_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY non_revenue_approval
    ADD CONSTRAINT non_revenue_approval_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES machine(id)""",
    """ALTER TABLE ONLY non_revenue_approval
    ADD CONSTRAINT non_revenue_approval_reason_id_fkey FOREIGN KEY (reason_id) REFERENCES revenue_reason(id)""",
    """ALTER TABLE ONLY non_revenue_approval
    ADD CONSTRAINT non_revenue_approval_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY rental_contract
    ADD CONSTRAINT rental_contract_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customer(id)""",
    """ALTER TABLE ONLY rental_contract
    ADD CONSTRAINT rental_contract_job_site_id_fkey FOREIGN KEY (job_site_id) REFERENCES job_site(id)""",
    """ALTER TABLE ONLY rental_contract
    ADD CONSTRAINT rental_contract_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY revenue_difference_adjustment
    ADD CONSTRAINT revenue_difference_adjustment_difference_id_fkey FOREIGN KEY (difference_id) REFERENCES revenue_difference(id)""",
    """ALTER TABLE ONLY revenue_difference_adjustment
    ADD CONSTRAINT revenue_difference_adjustment_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY revenue_difference
    ADD CONSTRAINT revenue_difference_case_id_fkey FOREIGN KEY (case_id) REFERENCES anomaly_case(id)""",
    """ALTER TABLE ONLY revenue_difference
    ADD CONSTRAINT revenue_difference_currency_fkey FOREIGN KEY (currency) REFERENCES currency(code)""",
    """ALTER TABLE ONLY revenue_difference
    ADD CONSTRAINT revenue_difference_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY revenue_difference
    ADD CONSTRAINT revenue_difference_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES machine(id)""",
    """ALTER TABLE ONLY revenue_difference
    ADD CONSTRAINT revenue_difference_reason_id_fkey FOREIGN KEY (reason_id) REFERENCES revenue_reason(id)""",
    """ALTER TABLE ONLY revenue_difference
    ADD CONSTRAINT revenue_difference_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY revenue_reason
    ADD CONSTRAINT revenue_reason_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY site_checkin
    ADD CONSTRAINT site_checkin_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY site_checkin
    ADD CONSTRAINT site_checkin_job_site_id_fkey FOREIGN KEY (job_site_id) REFERENCES job_site(id)""",
    """ALTER TABLE ONLY site_checkin
    ADD CONSTRAINT site_checkin_staff_member_id_fkey FOREIGN KEY (staff_member_id) REFERENCES staff_member(id)""",
    """ALTER TABLE ONLY site_checkin
    ADD CONSTRAINT site_checkin_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY tenant_hire_invoice
    ADD CONSTRAINT tenant_hire_invoice_currency_fkey FOREIGN KEY (currency) REFERENCES currency(code)""",
    """ALTER TABLE ONLY tenant_hire_invoice
    ADD CONSTRAINT tenant_hire_invoice_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customer(id)""",
    """ALTER TABLE ONLY tenant_hire_invoice
    ADD CONSTRAINT tenant_hire_invoice_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE ONLY work_execution_allocation
    ADD CONSTRAINT work_execution_allocation_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customer(id)""",
    """ALTER TABLE ONLY work_execution_allocation
    ADD CONSTRAINT work_execution_allocation_exception_id_fkey FOREIGN KEY (exception_id) REFERENCES job_exception(id)""",
    """ALTER TABLE ONLY work_execution_allocation
    ADD CONSTRAINT work_execution_allocation_job_id_fkey FOREIGN KEY (job_id) REFERENCES job(id)""",
    """ALTER TABLE ONLY work_execution_allocation
    ADD CONSTRAINT work_execution_allocation_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES machine(id)""",
    """ALTER TABLE ONLY work_execution_allocation
    ADD CONSTRAINT work_execution_allocation_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id)""",
    """ALTER TABLE customer_acknowledgement ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE hire_invoice_counter ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE hire_invoice_job ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE hire_invoice_line ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE hire_payment_allocation ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE job ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE job_activity ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE machine_changeover ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE non_revenue_approval ENABLE ROW LEVEL SECURITY""",
    """CREATE POLICY p_tenant ON customer_acknowledgement USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON hire_invoice_counter USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON hire_invoice_job USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON hire_invoice_line USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON hire_payment_allocation USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON job USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON job_activity USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON machine_changeover USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON non_revenue_approval USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON rental_contract USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON revenue_difference USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON revenue_difference_adjustment USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON revenue_reason USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON site_checkin USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON tenant_hire_invoice USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """CREATE POLICY p_tenant ON work_execution_allocation USING ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text))) WITH CHECK ((((app_scope() = 'tenant'::text) AND (tenant_id = app_tenant_id())) OR (app_scope() = 'system'::text)))""",
    """ALTER TABLE rental_contract ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE revenue_difference ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE revenue_difference_adjustment ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE revenue_reason ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE site_checkin ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE tenant_hire_invoice ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE work_execution_allocation ENABLE ROW LEVEL SECURITY""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE customer_acknowledgement FROM asseta_app; GRANT SELECT,INSERT,DELETE ON TABLE customer_acknowledgement TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE hire_invoice_counter FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE hire_invoice_counter TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE hire_invoice_job FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE hire_invoice_job TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE hire_invoice_line FROM asseta_app; GRANT SELECT,INSERT ON TABLE hire_invoice_line TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE hire_payment_allocation FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE hire_payment_allocation TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE job FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE job TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE job_activity FROM asseta_app; GRANT SELECT,INSERT,DELETE ON TABLE job_activity TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE machine_changeover FROM asseta_app; GRANT SELECT,INSERT ON TABLE machine_changeover TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE non_revenue_approval FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE non_revenue_approval TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE rental_contract FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE rental_contract TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE revenue_difference FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE revenue_difference TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE revenue_difference_adjustment FROM asseta_app; GRANT SELECT,INSERT ON TABLE revenue_difference_adjustment TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE revenue_reason FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE revenue_reason TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE site_checkin FROM asseta_app; GRANT SELECT,INSERT ON TABLE site_checkin TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE tenant_hire_invoice FROM asseta_app; GRANT SELECT,INSERT,UPDATE ON TABLE tenant_hire_invoice TO asseta_app; END IF; END $$""",
    """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'asseta_app') THEN REVOKE ALL ON TABLE work_execution_allocation FROM asseta_app; GRANT SELECT,INSERT ON TABLE work_execution_allocation TO asseta_app; END IF; END $$""",
)
