"""Engine-hour accountability policy (accountability design B, controls [3.2.x]).

Every switch is tenant configuration with a safe platform default; switching a capability off keeps the behaviour
that existed before it. Segregation of duties (proposer != approver) applies to every approval that a switch keeps
on and is never relaxable; the switches only decide *whether* a second person is needed."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EngineHoursPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # [3.2.1] A job may only START on a machine with an approved meter baseline. Off: jobs start as before.
    baseline_required_before_start: bool
    # [3.2.7] A working machine (running job or engine activity that day) needs a DAILY or job reading by the
    # cut-off hour (tenant local time), else MISSING_DAILY_REPORT is flagged and reminded. Off: no flag/reminder.
    daily_report_required: bool
    daily_report_cutoff_hour: int = Field(ge=0, le=23)
    # [3.2.8] An UNEXPLAINED segment older than this opens an investigation case (never reclassifies it).
    # Null: ageing never opens a case.
    unexplained_investigation_after_days: int | None = Field(default=None, ge=1, le=365)
    # Unallocated segments above this many hours raise UNEXPLAINED_HOURS and age (0 = any positive hours).
    unexplained_flag_min_hours: Decimal = Field(ge=0, le=Decimal(1000))
    # [3.2.6] A classification of unallocated hours is proposed by one person and approved by another holding
    # `tenant.meter.classify`. Off: a `tenant.meter.classify` holder's classification takes effect directly.
    classification_requires_approval: bool
    # [3.2.9] A reading correction (supersede) is proposed by one person and approved by another holding
    # `tenant.meter.approve`. Off: a `tenant.meter.approve` holder's correction takes effect directly (as before).
    correction_requires_second_person: bool
    # Readings held for review (PROVISIONAL with unreviewed blocking findings) count in the ledger as verified.
    # Off (default): such intervals show as PENDING_REVIEW and are not flagged, aged or classified until reviewed.
    ledger_includes_unreviewed_readings: bool
    # [3.2.5] Refuse a job START whose opening reading falls inside another job's interval (time or meter range).
    # Off: allowed; the ledger still reports the overlap.
    prevent_overlapping_allocation: bool
    # [3.2.5] Refuse a job activity (work log) entry that overlaps another timed entry of the same job.
    prevent_overlapping_activity: bool


ENGINE_HOURS_SEED: dict[str, object] = {
    "baseline_required_before_start": False,  # off: existing tenants keep starting jobs; switch on per tenant
    "daily_report_required": False,  # off: no new reminders until a tenant opts in
    "daily_report_cutoff_hour": 18,
    "unexplained_investigation_after_days": 3,
    "unexplained_flag_min_hours": "0",
    "classification_requires_approval": True,
    "correction_requires_second_person": True,
    "ledger_includes_unreviewed_readings": False,
    "prevent_overlapping_allocation": True,
    "prevent_overlapping_activity": True,
}
