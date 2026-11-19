"""Machine report DTOs (ADR-008 §2). Hours are decimal strings: readings and differences in the machine's meter
precision, report lines with at most 2 decimals."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.machine_reports.models import MachineReportStatus, ReportLineKind, StartSource
from asseta.modules.meter.dto import FindingDto, MeterCaptureIn
from asseta.modules.platform_billing.dto import Reason

# At most 2 decimals (checked by the service: HOURS_PRECISION), whatever the meter's precision.
LineHours = Annotated[Decimal, Field(gt=0, max_digits=14)]
Note = Annotated[str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MachineReportLineIn(BaseModel):
    """CUSTOMER: `customer_id` + `hours` (drawn from the hours the customer bought). NON_PRODUCTIVE: `reason_id` (the
    tenant's machine-report reason list) + `hours` + `note` (required)."""

    kind: ReportLineKind
    customer_id: uuid.UUID | None = None
    reason_id: uuid.UUID | None = None
    hours: LineHours
    note: Note | None = None

    @model_validator(mode="after")
    def _kind(self) -> "MachineReportLineIn":
        if self.kind is ReportLineKind.CUSTOMER:
            if self.customer_id is None or self.reason_id is not None:
                raise ValueError("a CUSTOMER line names customer_id (and no reason_id)")
        else:
            if self.reason_id is None or self.customer_id is not None:
                raise ValueError("a NON_PRODUCTIVE line names reason_id (and no customer_id)")
            if not self.note:
                raise ValueError("a NON_PRODUCTIVE line needs a note")
        return self


class MachineReportIn(BaseModel):
    """A machine report: the new reading and how its hours split. Give the new reading as `capture` (a DAILY meter
    reading of this machine: photo, OCR, GPS, time, exactly as POST /meter-captures) or as `capture_id` (a reading
    recorded just before, e.g. by the sync operation METER_CAPTURE). A reading belongs to one report only
    (CAPTURE_ALREADY_USED). A rejected report is final: `corrects_report_id` is kept for older apps but any value is
    refused (CORRECTION_NOT_ALLOWED); send a new report with a new reading. Line hours have at most 2 decimals. The
    lines must add up to the difference between the machine's last approved reading and the new one exactly.

    Opening report (`opening: true`, `lines: []`): when the machine has no starting reading yet (no approved report,
    baseline or reset; `opening_required` in its status), the first report gives only the reading. It is approved like
    any report and its reading then becomes where the next report starts."""

    id: uuid.UUID | None = Field(
        default=None, description="Device-generated report id (offline idempotency; the sync operation id)"
    )
    machine_id: uuid.UUID
    capture: MeterCaptureIn | None = None
    capture_id: uuid.UUID | None = None
    corrects_report_id: uuid.UUID | None = Field(
        default=None,
        description="Retired: a rejected report is final. Any value is refused (CORRECTION_NOT_ALLOWED); send a new "
        "report with a new reading",
    )
    opening: bool = Field(
        default=False, description="An opening report: the machine's first reading, no lines (difference 0)"
    )
    lines: list[MachineReportLineIn] = Field(default_factory=list, max_length=50)
    note: Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)] | None = None
    client_created_at: datetime | None = Field(default=None, description="Device time the report was made")

    @model_validator(mode="after")
    def _reading(self) -> "MachineReportIn":
        if (self.capture is None) == (self.capture_id is None):
            raise ValueError("give exactly one of capture or capture_id")
        if self.opening and self.lines:
            raise ValueError("an opening report has no lines")
        if not self.opening and not self.lines:
            raise ValueError("give the lines the hours are split into")
        if self.capture is not None:
            if self.capture.kind.value != "DAILY":
                raise ValueError("the report's reading is a DAILY reading")
            if self.capture.machine_id is not None and self.capture.machine_id != self.machine_id:
                raise ValueError("capture.machine_id is not the report's machine")
        return self


class MachineReportDecisionIn(BaseModel):
    note: Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)] | None = None


class MachineReportRejectIn(BaseModel):
    reason: Reason


class LotDto(BaseModel):
    """Hours of one order (lot) a customer line consumed on approval, oldest activated first."""

    purchase_id: uuid.UUID
    purchase_number: str | None = None
    machine_id: uuid.UUID = Field(description="The machine the order's hours were on")
    hours: Decimal


class MachineReportLineDto(BaseModel):
    id: uuid.UUID
    line_no: int
    kind: ReportLineKind
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    reason_id: uuid.UUID | None
    reason_code: str | None = None
    reason_name: str | None = None
    hours: Decimal
    note: str | None
    available_hours: Decimal | None = Field(
        default=None,
        description="SUBMITTED reports, customer lines: the customer's hours available to this report now (its own "
        "reservation included)",
    )
    lots: list[LotDto] = Field(default_factory=list, description="APPROVED reports: the orders the hours came from")


class TrackerCheckDto(BaseModel):
    """Approver aid: engine hours the machine's tracker counted over the report's period, against the meter."""

    available: bool = Field(description="False when the machine has no tracker engine-hour counts for the period")
    tracker_hours: Decimal | None
    meter_hours: Decimal
    difference: Decimal | None = Field(description="meter_hours - tracker_hours")
    tracker_from_at: datetime | None = None
    tracker_to_at: datetime | None = None


class MachineReportDto(BaseModel):
    id: uuid.UUID
    report_number: str
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    capture_id: uuid.UUID
    opening: bool = Field(default=False, description="An opening report (the machine's first reading, 0 hours)")
    start_source: StartSource
    start_ref: uuid.UUID
    start_reading: Decimal
    start_at: datetime
    end_reading: Decimal
    end_at: datetime
    hours: Decimal
    customer_hours: Decimal
    non_productive_hours: Decimal
    status: MachineReportStatus
    previous_visit_at: datetime | None = Field(
        default=None,
        description="Taken-at time of the machine's previous visit: the latest earlier reading that belongs to any "
        "machine report (any status). Null: first visit",
    )
    since_previous_visit_seconds: int | None = Field(
        default=None,
        description="This report's reading taken-at time minus previous_visit_at, in seconds (server-computed at "
        "submit, never changed). Null: first visit",
    )
    previous_visit_lat: float | None = Field(default=None, description="The previous visit's reading GPS latitude")
    previous_visit_lng: float | None = Field(default=None, description="The previous visit's reading GPS longitude")
    previous_visit_accuracy_m: float | None = Field(default=None, description="Its GPS accuracy (metres)")
    previous_visit_place: str | None = Field(
        default=None,
        description="The previous visit's place: the area label the phone's geocoder gave its reading, or null",
    )
    previous_visit_site_name: str | None = Field(
        default=None, description="Hint: the company site whose area contains the previous visit's GPS point, or null"
    )
    visit_lat: float | None = Field(default=None, description="This report's reading GPS latitude")
    visit_lng: float | None = Field(default=None, description="This report's reading GPS longitude")
    visit_accuracy_m: float | None = Field(default=None, description="Its GPS accuracy (metres)")
    visit_place: str | None = Field(
        default=None,
        description="This report's place: the area label the phone's geocoder gave its reading (meter capture "
        "place_name), or null",
    )
    visit_site_name: str | None = Field(
        default=None,
        description="Hint: the company site (geofence) containing this reading's GPS point, nearest site first; null "
        "when none (server lookup, no outside geocoding)",
    )
    corrects_id: uuid.UUID | None = Field(description="History only (reports made before rejections became final)")
    corrected_by_id: uuid.UUID | None = Field(
        default=None, description="History only: the report that corrected this rejected one (older reports)"
    )
    note: str | None
    source: str
    submitted_by: uuid.UUID | None
    submitted_by_name: str | None = None
    submitted_at: datetime
    client_created_at: datetime | None
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    policy_version: str
    lines: list[MachineReportLineDto] = []
    photo_attachment_id: uuid.UUID | None = None
    capture_state: str | None = None
    findings: list[FindingDto] = Field(default_factory=list, description="The reading's findings (review evidence)")
    tracker: TrackerCheckDto | None = Field(default=None, description="Detail only: tracker cross-check")


class AvailableHoursDto(BaseModel):
    """A customer's hours a new report may draw on: activated - consumed - reserved by other SUBMITTED reports."""

    customer_id: uuid.UUID
    customer_name: str | None = None
    machine_id: uuid.UUID | None = Field(
        default=None, description="Set when the tenant draws reports only on the machine's hours (scope MACHINE)"
    )
    remaining: Decimal = Field(description="Activated hours not yet used")
    reserved: Decimal = Field(description="Held by SUBMITTED reports")
    available: Decimal


class MachineReportReasonIn(BaseModel):
    """A machine-report reason (the tenant's own list; e.g. Transit between sites, Breakdown / repair)."""

    code: Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
    description: str | None = Field(default=None, max_length=1000)


class MachineReportReasonDto(Dto):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    version: int


class MachineReportContextDto(BaseModel):
    """What a new report on this machine starts from (the form's first step)."""

    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    meter_decimal_places: int
    previous_reading: Decimal | None = Field(
        description="Null: no starting reading yet: send an opening report (opening: true, no lines)"
    )
    opening_required: bool = Field(default=False, description="The next report on this machine is an opening report")
    previous_at: datetime | None
    previous_source: StartSource | None
    meter_epoch: int
    pending_report_id: uuid.UUID | None = Field(description="A SUBMITTED report holds the machine: the next waits")
    last_report_at: datetime | None
    last_visit_at: datetime | None = Field(
        default=None,
        description="The machine's last visit: taken-at time of the latest reading that belongs to any of its machine "
        "reports (any status). Null: never visited (first visit)",
    )
    last_visit_lat: float | None = Field(default=None, description="The last visit's reading GPS latitude")
    last_visit_lng: float | None = Field(default=None, description="The last visit's reading GPS longitude")
    last_visit_accuracy_m: float | None = Field(default=None, description="Its GPS accuracy (metres)")
    last_visit_place: str | None = Field(
        default=None, description="The last visit's place: the area label the phone's geocoder gave its reading"
    )
    last_visit_site_name: str | None = Field(
        default=None, description="Hint: the company site whose area contains the last visit's GPS point, or null"
    )
    hours_scope: Literal["CUSTOMER", "MACHINE"]
    customers: list[AvailableHoursDto]
    reasons: list[MachineReportReasonDto]


class MachineReportStatusDto(BaseModel):
    """One machine's report status (supervisor dashboard, owner overview)."""

    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    meter_decimal_places: int = 1
    previous_reading: Decimal | None = Field(
        default=None, description="Where a new report starts (last approved reading, baseline or reset); null: none"
    )
    previous_at: datetime | None = None
    previous_source: StartSource | None = None
    opening_required: bool = Field(
        default=False,
        description="No starting reading yet: the next report is an opening report (opening: true, lines: [])",
    )
    last_approved_reading: Decimal | None
    last_approved_at: datetime | None
    last_report_at: datetime | None
    last_visit_at: datetime | None = Field(
        default=None,
        description="The machine's last visit: taken-at time of the latest reading that belongs to any of its machine "
        "reports (any status). Null: never visited",
    )
    last_visit_lat: float | None = Field(default=None, description="The last visit's reading GPS latitude")
    last_visit_lng: float | None = Field(default=None, description="The last visit's reading GPS longitude")
    last_visit_accuracy_m: float | None = Field(default=None, description="Its GPS accuracy (metres)")
    last_visit_place: str | None = Field(
        default=None, description="The last visit's place: the area label the phone's geocoder gave its reading"
    )
    last_visit_site_name: str | None = Field(
        default=None, description="Hint: the company site whose area contains the last visit's GPS point, or null"
    )
    days_since_report: int | None
    pending_report_id: uuid.UUID | None
    pending_report_number: str | None
    rejected_report_id: uuid.UUID | None = Field(
        description="The machine's latest report was rejected: a new report (with a new reading) is due"
    )


class ProductiveHoursDto(BaseModel):
    """Approved report hours of one machine (and reason) in a period."""

    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    reason_id: uuid.UUID | None = None
    reason_name: str | None = None
    productive_hours: Decimal
    non_productive_hours: Decimal
    date_from: date | None = None
    date_to: date | None = None
