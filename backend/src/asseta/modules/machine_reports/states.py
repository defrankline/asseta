"""Reported state per machine, from supervisors' machine reports only (ADR-008) — never inferred from GPS or engine
data, which are separate observed dimensions on the fleet map.

    REPORT_PENDING   the machine has a SUBMITTED report waiting for a decision
    REPORT_REJECTED  its latest report was rejected: the supervisor corrects it on the same reading
    REPORTED         its latest report was approved
    NOT_REPORTED     no machine report yet
"""

import uuid
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.machine_reports.models import MachineReport, MachineReportStatus


class ReportedWorkState(StrEnum):
    REPORT_PENDING = "REPORT_PENDING"
    REPORT_REJECTED = "REPORT_REJECTED"
    REPORTED = "REPORTED"
    NOT_REPORTED = "NOT_REPORTED"


_FROM_STATUS = {
    MachineReportStatus.SUBMITTED: ReportedWorkState.REPORT_PENDING,
    MachineReportStatus.REJECTED: ReportedWorkState.REPORT_REJECTED,
    MachineReportStatus.APPROVED: ReportedWorkState.REPORTED,
}


def reported_work_states(session: Session) -> dict[uuid.UUID, ReportedWorkState]:
    """Machines with at least one report -> the state of their latest one (RLS-scoped to the caller's tenant). Machines
    that are absent have no report (`NOT_REPORTED`). A SUBMITTED report always wins (it is the latest)."""
    rows = session.execute(
        select(MachineReport.machine_id, MachineReport.status)
        .distinct(MachineReport.machine_id)
        .order_by(MachineReport.machine_id, MachineReport.submitted_at.desc(), MachineReport.created_at.desc())
    ).tuples()
    return {machine_id: _FROM_STATUS[status] for machine_id, status in rows}
