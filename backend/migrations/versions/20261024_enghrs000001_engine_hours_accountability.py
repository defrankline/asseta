"""Engine-hour accountability (design B): DAILY meter readings (job optional), approved meter baselines, tenant
explanation lists, classifications of unallocated engine hours and two-person reading corrections.

Security: tenant-owned FORCE RLS and explicit grants (never DELETE) on the new tables; baselines, classifications
and corrections are immutable except for the single PROPOSED -> APPROVED/REJECTED decision (guard trigger).
Seeds the ENGINE_HOURS platform default policy (replaceable configuration).

Rollout for machines that already have readings: each gets a system baseline *proposal* from its earliest live
reading (proposer = system), awaiting a person's approval; until approved the machine shows NO_BASELINE and, while
the tenant policy `baseline_required_before_start` is on, its jobs cannot START (BASELINE_REQUIRED).

Revision ID: enghrs000001
Revises: cashc0000001
Create Date: 2026-10-24 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "enghrs000001"
down_revision: str | Sequence[str] | None = "cashc0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS = {
    "machine_meter_baseline": "SELECT, INSERT, UPDATE",  # guard: one decision
    "engine_hour_reason": "SELECT, INSERT, UPDATE",  # tenant list: edits/deactivation, never deleted
    "engine_hour_classification": "SELECT, INSERT, UPDATE",  # guard: one decision
    "meter_correction": "SELECT, INSERT, UPDATE",  # guard: one decision
}
DECIDED = ["machine_meter_baseline", "engine_hour_classification", "meter_correction"]
ENGINE_HOURS_SEED = (
    '{"baseline_required_before_start": false, "daily_report_required": false, "daily_report_cutoff_hour": 18, '
    '"unexplained_investigation_after_days": 3, "unexplained_flag_min_hours": "0", '
    '"classification_requires_approval": true, "correction_requires_second_person": true, '
    '"ledger_includes_unreviewed_readings": false, "prevent_overlapping_allocation": true, '
    '"prevent_overlapping_activity": true}'
)


def _decision_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("proposed_by", sa.UUID(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    # --- DAILY readings: job optional, one OPENING/CLOSING per job still enforced --------------------------------
    op.alter_column("meter_capture", "job_id", existing_type=sa.UUID(), nullable=True)
    op.drop_index("uq_meter_capture_job_kind_active", table_name="meter_capture")
    op.create_index(
        "uq_meter_capture_job_kind_active",
        "meter_capture",
        ["job_id", "kind"],
        unique=True,
        postgresql_where=sa.text("state IN ('ACCEPTED', 'PROVISIONAL') AND kind <> 'DAILY'"),
    )
    op.create_check_constraint("ck_meter_capture_job_reading", "meter_capture", "kind = 'DAILY' OR job_id IS NOT NULL")

    # --- tables ------------------------------------------------------------------------------------------------
    op.create_table(
        "machine_meter_baseline",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("reading", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_capture_id", sa.UUID(), nullable=True),
        sa.Column("photo_attachment_id", sa.UUID(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *_decision_columns(),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["photo_attachment_id"], ["capture_attachment.id"]),
        sa.ForeignKeyConstraint(["source_capture_id"], ["meter_capture.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_machine_meter_baseline_machine_id"), "machine_meter_baseline", ["machine_id"], unique=False
    )
    op.create_index(op.f("ix_machine_meter_baseline_tenant_id"), "machine_meter_baseline", ["tenant_id"], unique=False)
    op.create_index(
        "uq_meter_baseline_approved",
        "machine_meter_baseline",
        ["tenant_id", "machine_id"],
        unique=True,
        postgresql_where=sa.text("status = 'APPROVED'"),
    )
    op.create_index(
        "uq_meter_baseline_proposed",
        "machine_meter_baseline",
        ["tenant_id", "machine_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PROPOSED'"),
    )
    op.create_table(
        "engine_hour_reason",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.UUID(), nullable=True),
        sa.Column("deactivation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "kind", "code", name="uq_engine_hour_reason_code"),
    )
    op.create_index(op.f("ix_engine_hour_reason_tenant_id"), "engine_hour_reason", ["tenant_id"], unique=False)
    op.create_table(
        "engine_hour_classification",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("start_ref", sa.UUID(), nullable=False),
        sa.Column("end_ref", sa.UUID(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hours", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("reason_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        *_decision_columns(),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["reason_id"], ["engine_hour_reason.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_engine_hour_classification_machine_id"), "engine_hour_classification", ["machine_id"], unique=False
    )
    op.create_index(
        "ix_engine_hour_classification_status", "engine_hour_classification", ["tenant_id", "status"], unique=False
    )
    op.create_index(
        "uq_engine_hour_classification_live",
        "engine_hour_classification",
        ["tenant_id", "machine_id", "start_ref", "end_ref"],
        unique=True,
        postgresql_where=sa.text("status IN ('PROPOSED', 'APPROVED')"),
    )
    op.create_table(
        "meter_correction",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("superseded_capture_id", sa.UUID(), nullable=False),
        sa.Column("replacement_capture_id", sa.UUID(), nullable=False),
        sa.Column("replacement", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("old_reading", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("new_reading", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        *_decision_columns(),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["superseded_capture_id"], ["meter_capture.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replacement_capture_id"),
    )
    op.create_index(op.f("ix_meter_correction_machine_id"), "meter_correction", ["machine_id"], unique=False)
    op.create_index("ix_meter_correction_status", "meter_correction", ["tenant_id", "status"], unique=False)
    op.create_index(
        "uq_meter_correction_open",
        "meter_correction",
        ["tenant_id", "superseded_capture_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PROPOSED'"),
    )

    # --- security: decision guard, RLS, grants -----------------------------------------------------------------
    op.execute("""
        CREATE FUNCTION guard_engine_hours_decision() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[] := ARRAY['status', 'decided_by', 'decided_at', 'decision_note'];
        BEGIN
          IF TG_OP = 'DELETE' OR OLD.status <> 'PROPOSED' OR NEW.status NOT IN ('APPROVED', 'REJECTED')
             OR NEW.decided_by IS NULL OR NEW.decided_at IS NULL
             OR (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: % is immutable (one decision: PROPOSED -> APPROVED/REJECTED)', TG_TABLE_NAME
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
    """)
    for t in DECIDED:
        op.execute(
            f"CREATE TRIGGER trg_{t}_guard BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION guard_engine_hours_decision()"
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
    """)

    # --- seeds: platform default policy; rollout baseline proposals for machines with readings -----------------
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from, values,
                                    reason, created_at, source)
        SELECT gen_random_uuid(), 'ENGINE_HOURS', 'PLATFORM', NULL, NULL, 1, TIMESTAMPTZ '2000-01-01 00:00:00+00',
               '{ENGINE_HOURS_SEED}'::jsonb, 'Seeded platform default (replaceable configuration)', now(), 'migration'
        WHERE NOT EXISTS (SELECT 1 FROM policy_version WHERE policy_type = 'ENGINE_HOURS' AND scope = 'PLATFORM');
        INSERT INTO machine_meter_baseline (id, tenant_id, machine_id, reading, captured_at, source, source_capture_id,
                                            photo_attachment_id, latitude, longitude, accuracy_m, device_id, note,
                                            status, proposed_by, proposed_at)
        SELECT gen_random_uuid(), c.tenant_id, c.machine_id, c.reading, c.captured_at, 'READING', c.id,
               c.photo_attachment_id, c.latitude, c.longitude, c.accuracy_m, c.device_id,
               'Proposed by the system from the earliest reading (engine-hour rollout); needs a person''s approval',
               'PROPOSED', NULL, now()
        FROM (
          SELECT DISTINCT ON (machine_id) * FROM meter_capture
          WHERE state IN ('ACCEPTED', 'PROVISIONAL')
          ORDER BY machine_id, captured_at, id
        ) c;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    for t in DECIDED:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_guard ON {t}")
    op.execute("DROP FUNCTION IF EXISTS guard_engine_hours_decision()")
    op.drop_index(
        "uq_meter_correction_open", table_name="meter_correction", postgresql_where=sa.text("status = 'PROPOSED'")
    )
    op.drop_index("ix_meter_correction_status", table_name="meter_correction")
    op.drop_index(op.f("ix_meter_correction_machine_id"), table_name="meter_correction")
    op.drop_table("meter_correction")
    op.drop_index(
        "uq_engine_hour_classification_live",
        table_name="engine_hour_classification",
        postgresql_where=sa.text("status IN ('PROPOSED', 'APPROVED')"),
    )
    op.drop_index("ix_engine_hour_classification_status", table_name="engine_hour_classification")
    op.drop_index(op.f("ix_engine_hour_classification_machine_id"), table_name="engine_hour_classification")
    op.drop_table("engine_hour_classification")
    op.drop_index(op.f("ix_engine_hour_reason_tenant_id"), table_name="engine_hour_reason")
    op.drop_table("engine_hour_reason")
    op.drop_index("uq_meter_baseline_proposed", table_name="machine_meter_baseline")
    op.drop_index("uq_meter_baseline_approved", table_name="machine_meter_baseline")
    op.drop_index(op.f("ix_machine_meter_baseline_tenant_id"), table_name="machine_meter_baseline")
    op.drop_index(op.f("ix_machine_meter_baseline_machine_id"), table_name="machine_meter_baseline")
    op.drop_table("machine_meter_baseline")
    op.drop_constraint("ck_meter_capture_job_reading", "meter_capture", type_="check")
    op.drop_index("uq_meter_capture_job_kind_active", table_name="meter_capture")
    op.create_index(
        "uq_meter_capture_job_kind_active",
        "meter_capture",
        ["job_id", "kind"],
        unique=True,
        postgresql_where=sa.text("state IN ('ACCEPTED', 'PROVISIONAL')"),
    )
    # DAILY readings have no job: they cannot exist under the old NOT NULL rule (meter_capture is append-only, so
    # a downgrade with DAILY readings present fails here rather than deleting evidence).
    op.alter_column("meter_capture", "job_id", existing_type=sa.UUID(), nullable=False)
    # The ENGINE_HOURS platform seed is immutable (policy_version trigger) and harmless; re-upgrade is idempotent.
