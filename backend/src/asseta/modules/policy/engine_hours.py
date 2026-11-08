"""Engine-hour accountability policy (accountability design B, controls [3.2.x]).

Every switch is tenant configuration with a safe platform default; switching a capability off keeps the behaviour
that existed before it. Segregation of duties (proposer != approver) applies to every approval that a switch keeps
on and is never relaxable; the switches only decide *whether* a second person is needed."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EngineHoursPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Master switch (capability ENGINE_HOURS). Off: job meter readings work as before these controls (no baseline
    # gate, overlap refusals, daily reports, unexplained-hour flags or ageing); every switch below reads as off.
    enabled: bool = True
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
    # [DEC-032 A2] Time inside a job counts as customer work without a work-log entry (today's behaviour). Off: in-job
    # hours need a covering work-log entry; uncovered hours are UNEXPLAINED (not billable, not drawn, not wasted).
    # Read per job at its start, so a change never reinterprets a job already running.
    in_job_time_counts_as_customer_work: bool = True
    # [DEC-032 A3] A mid-job changeover reading always moves the allocation to the next customer. On: the hours after
    # it also leave the running job's billing, drawdown and expected revenue. Off (today): the job bills as before.
    changeover_splits_billing: bool = False
    # [DEC-032 A1] A correction of a work allocation is proposed by one person and approved by another holding
    # `tenant.meter.approve`. Off: an approval-permission holder's correction takes effect directly.
    allocation_correction_requires_approval: bool = True
    # [DEC-032 A6] Cumulative open unexplained hours of a machine above this open an investigation by amount as well
    # as by age. Null: only age opens one.
    unexplained_flag_amount_hours: Decimal | None = Field(default=None, gt=0, le=Decimal(100000))
    # [DEC-032 A4] Every daily operational report needs at least one evidence photo. Off (today): evidence is optional.
    daily_report_evidence_required: bool = False
    # [DEC-032 Phase 3] Classifications of unexplained hours need at least one evidence photo. Off (today): optional.
    classification_evidence_required: bool = False

    def in_force(self) -> "EngineHoursPolicy":
        """The rules actually enforced: as configured when enabled; switched off as a whole otherwise."""
        if self.enabled:
            return self
        return self.model_copy(
            update={
                "baseline_required_before_start": False,
                "daily_report_required": False,
                "unexplained_investigation_after_days": None,
                "correction_requires_second_person": False,
                "prevent_overlapping_allocation": False,
                "prevent_overlapping_activity": False,
                "in_job_time_counts_as_customer_work": True,
                "changeover_splits_billing": False,
                "allocation_correction_requires_approval": False,
                "unexplained_flag_amount_hours": None,
                "daily_report_evidence_required": False,
                "classification_evidence_required": False,
            }
        )


ENGINE_HOURS_SEED: dict[str, object] = {
    "enabled": True,
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
    "in_job_time_counts_as_customer_work": True,
    "changeover_splits_billing": False,
    "allocation_correction_requires_approval": True,
    "unexplained_flag_amount_hours": None,
    "daily_report_evidence_required": False,
    "classification_evidence_required": False,
}
