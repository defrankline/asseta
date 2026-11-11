"""Employee accountability view (guideline section 10): one person's identity, the cash they hold now and how it got
there, what they reported, proposed and decided over a period. Every record names its type, id and console route.
Neutral: records to look at, never a verdict about the person."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from asseta.core.errors import NotFound
from asseta.modules.accountability.flows import history
from asseta.modules.accountability.links import record_route
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.common import local_bounds, local_date, tenant_settings
from asseta.modules.finance.custody_dto import ReconciliationFigure as F
from asseta.modules.finance.custody_models import CashRetention, CashTransfer, CashTransferStatus, CashVariance
from asseta.modules.finance.dto import CashCustodyBalanceDto
from asseta.modules.finance.models import CashHandover, SettlementStatus
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.models import AppUser, Role, TenantMembership
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.allocation_models import DailyOperationalReport
from asseta.modules.oversight.service import ScorecardService
from asseta.modules.pettycash.dto import PettyCashBalanceDto
from asseta.modules.pettycash.ledger import FundLedger
from asseta.modules.pettycash.models import PettyCashFund
from asseta.modules.policy.capabilities import PETTY_CASH, SCORECARD, capability_on

LIMIT = 200  # records per list; `truncated` names the lists that had more
DEFAULT_DAYS = 30
SCORECARD_PERMISSION = "tenant.oversight.scorecard.read"
_FIGURE_LIST = {
    F.COLLECTIONS: "collections",
    F.FLOATS_ISSUED: "floats",
    F.PENDING_FLOATS: "floats",
    F.TRANSFERS_IN: "transfers_in",
    F.IN_TRANSIT_IN: "transfers_in",
    F.TRANSFERS_OUT: "transfers_out",
    F.IN_TRANSIT_OUT: "transfers_out",
    F.VERIFIED_HANDOVERS: "remittances",
    F.CLAIMED_UNVERIFIED_HANDOVERS: "remittances",
    F.APPROVED_SPENDING: "spending",
    F.PENDING_SPENDING: "spending",
    F.ADJUSTMENTS: "custody_adjustments",
    F.PENDING_ADJUSTMENTS: "custody_adjustments",
    F.WRITTEN_OFF: "differences",
}


class EmployeeRecordDto(BaseModel):
    record_type: str
    id: uuid.UUID | None
    reference: str | None = None
    status: str | None = None
    occurred_at: datetime
    amount: Decimal | None = None
    unit: str | None = None
    currency: str | None = None
    label: str | None = None
    counterparty_staff_id: uuid.UUID | None = None
    counterparty_staff_name: str | None = None
    route: str | None = None


class EmployeeIdentityDto(BaseModel):
    staff_member_id: uuid.UUID
    full_name: str
    kind: str
    employee_code: str | None
    phone: str | None
    is_active: bool
    user_id: uuid.UUID | None
    login_email: str | None
    roles: list[str]


class EmployeeAccountabilityDto(BaseModel):
    identity: EmployeeIdentityDto
    date_from: date
    date_to: date
    cash_held: list[CashCustodyBalanceDto]
    # DEC-033: petty cash funds this person holds now (kept apart from the collections custody above)
    petty_cash_funds: list[PettyCashBalanceDto] = []
    collections: list[EmployeeRecordDto]
    floats: list[EmployeeRecordDto]
    transfers_in: list[EmployeeRecordDto]
    transfers_out: list[EmployeeRecordDto]
    remittances: list[EmployeeRecordDto]
    spending: list[EmployeeRecordDto]
    retentions: list[EmployeeRecordDto]
    differences: list[EmployeeRecordDto]
    custody_adjustments: list[EmployeeRecordDto]
    reports_submitted: list[EmployeeRecordDto]
    approvals_made: list[EmployeeRecordDto]
    adjustments_requested: list[EmployeeRecordDto]
    adjustments_decided: list[EmployeeRecordDto]
    scorecard_items: list[EmployeeRecordDto]
    scorecard_visible: bool
    truncated: list[str]


def _flow_record(row: Any, at: datetime) -> EmployeeRecordDto:
    return EmployeeRecordDto(
        record_type=row.record_type,
        id=row.id,
        reference=row.reference,
        status=row.status,
        occurred_at=at,
        amount=row.amount,
        unit=row.unit,
        currency=row.currency,
        label=row.key,
        route=record_route(row.record_type, row.id),
    )


class EmployeeAccountability:
    def __init__(self, s: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = s, ctx, ctx.tenant_id, now

    def build(
        self, staff_member_id: uuid.UUID, date_from: date | None, date_to: date | None
    ) -> EmployeeAccountabilityDto:
        staff = self._s.get(StaffMember, staff_member_id)
        if staff is None:
            raise NotFound("Staff member not found")
        tz = tenant_settings(self._s, self._tid).timezone
        last = date_to or local_date(tz, self._now)
        first = date_from or last - timedelta(days=DEFAULT_DAYS - 1)
        start, end = local_bounds(tz, first, last)
        user = (
            self._s.execute(
                select(AppUser).where(AppUser.keycloak_subject == staff.keycloak_subject)
            ).scalar_one_or_none()
            if staff.keycloak_subject
            else None
        )
        lists: dict[str, list[EmployeeRecordDto]] = {name: [] for name in set(_FIGURE_LIST.values())}
        custody = CashCustodyService(self._s, self._ctx, self._now)
        held = custody.balances(staff.id)
        for balance in held:
            for t in custody.transactions(staff.id, balance.currency, first, last, _FIGURE_LIST):
                lists[_FIGURE_LIST[t.figure]].append(
                    EmployeeRecordDto(
                        record_type=t.entity_type,
                        id=t.entity_id,
                        reference=t.reference,
                        status=t.status,
                        occurred_at=t.occurred_at,
                        amount=t.amount,
                        unit="MONEY",
                        currency=t.currency,
                        label=t.figure.value,
                        counterparty_staff_id=t.counterparty_staff_id,
                        route=record_route(t.entity_type, t.entity_id),
                    )
                )
        self._refused(staff.id, start, end, lists)
        lists["retentions"] = self._retentions(staff.id, start, end)
        lists["differences"] = [*lists["differences"], *self._variances(staff.id, start, end)]
        truncated: list[str] = []
        for name, rows in lists.items():
            rows.sort(key=lambda r: r.occurred_at, reverse=True)
            if len(rows) > LIMIT:
                truncated.append(name)
                lists[name] = rows[:LIMIT]
        people = self._people(user.id, start, end, truncated) if user is not None else dict(_NO_PERSON)
        scorecard_visible = SCORECARD_PERMISSION in self._ctx.permissions and capability_on(
            self._s, self._tid, SCORECARD, self._now
        )
        scorecard = self._scorecard(staff.id, first, last) if scorecard_visible else []
        if len(scorecard) > LIMIT:
            truncated.append("scorecard_items")
        return EmployeeAccountabilityDto(
            identity=EmployeeIdentityDto(
                staff_member_id=staff.id,
                full_name=staff.full_name,
                kind=staff.kind.value,
                employee_code=staff.employee_code,
                phone=staff.phone,
                is_active=staff.is_active,
                user_id=user.id if user else None,
                login_email=user.email if user else None,
                roles=self._roles(user.id) if user else [],
            ),
            date_from=first,
            date_to=last,
            cash_held=held,
            petty_cash_funds=self._funds(staff.id),
            collections=lists["collections"],
            floats=lists["floats"],
            transfers_in=lists["transfers_in"],
            transfers_out=lists["transfers_out"],
            remittances=lists["remittances"],
            spending=lists["spending"],
            retentions=lists["retentions"],
            differences=lists["differences"],
            custody_adjustments=lists["custody_adjustments"],
            scorecard_items=scorecard[:LIMIT],
            scorecard_visible=scorecard_visible,
            truncated=sorted(truncated),
            **people,
        )

    def _funds(self, staff_id: uuid.UUID) -> list[PettyCashBalanceDto]:
        if not capability_on(self._s, self._tid, PETTY_CASH, self._now):
            return []
        ledger = FundLedger(self._s, self._now)
        rows = self._s.execute(
            select(PettyCashFund)
            .where(PettyCashFund.holder_staff_id == staff_id, PettyCashFund.is_active.is_(True))
            .order_by(PettyCashFund.code)
        ).scalars()
        return [ledger.balance(f) for f in rows]

    def _roles(self, user_id: uuid.UUID) -> list[str]:
        return sorted(
            self._s.execute(
                select(Role.key)
                .join(TenantMembership, TenantMembership.role_id == Role.id)
                .where(
                    TenantMembership.user_id == user_id,
                    TenantMembership.tenant_id == self._tid,
                    TenantMembership.effective_to.is_(None),
                )
            ).scalars()
        )

    def _refused(
        self, staff_id: uuid.UUID, start: datetime, end: datetime, lists: dict[str, list[EmployeeRecordDto]]
    ) -> None:
        """Remittances the company refused and transfers the receiver disputed: no custody movement, still history."""
        h, t = CashHandover, CashTransfer
        for row in self._s.execute(
            select(h).where(
                h.staff_member_id == staff_id,
                h.status == SettlementStatus.REJECTED,
                h.handed_at >= start,
                h.handed_at < end,
            )
        ).scalars():
            lists["remittances"].append(
                EmployeeRecordDto(
                    record_type="cash_handover",
                    id=row.id,
                    reference=row.remittance_number,
                    status=row.status.value,
                    occurred_at=row.handed_at,
                    amount=row.amount,
                    unit="MONEY",
                    currency=row.currency,
                    route=record_route("cash_handover", row.id),
                )
            )
        for transfer in self._s.execute(
            select(t).where(
                or_(t.from_staff_id == staff_id, t.to_staff_id == staff_id),
                t.status == CashTransferStatus.DISPUTED,
                t.transferred_at >= start,
                t.transferred_at < end,
            )
        ).scalars():
            outgoing = transfer.from_staff_id == staff_id
            lists["transfers_out" if outgoing else "transfers_in"].append(
                EmployeeRecordDto(
                    record_type="cash_transfer",
                    id=transfer.id,
                    reference=transfer.transfer_number,
                    status=transfer.status.value,
                    occurred_at=transfer.transferred_at,
                    amount=transfer.amount_declared,
                    unit="MONEY",
                    currency=transfer.currency,
                    counterparty_staff_id=transfer.to_staff_id if outgoing else transfer.from_staff_id,
                    route=record_route("cash_transfer", transfer.id),
                )
            )

    def _retentions(self, staff_id: uuid.UUID, start: datetime, end: datetime) -> list[EmployeeRecordDto]:
        r = CashRetention
        rows = self._s.execute(
            select(r).where(r.staff_member_id == staff_id, r.created_at >= start, r.created_at < end)
        ).scalars()
        return [
            EmployeeRecordDto(
                record_type="cash_retention",
                id=row.id,
                reference=row.retention_number,
                status=row.status.value,
                occurred_at=row.created_at,
                amount=row.amount,
                unit="MONEY",
                currency=row.currency,
                label=row.reason,
                route=record_route("cash_retention", row.id),
            )
            for row in rows
        ]

    def _variances(self, staff_id: uuid.UUID, start: datetime, end: datetime) -> list[EmployeeRecordDto]:
        v = CashVariance
        rows = self._s.execute(
            select(v).where(v.staff_member_id == staff_id, v.opened_at >= start, v.opened_at < end)
        ).scalars()
        return [
            EmployeeRecordDto(
                record_type="cash_variance",
                id=row.id,
                status=row.status.value,
                occurred_at=row.opened_at,
                amount=row.amount,
                unit=row.unit.value,
                currency=row.currency,
                label=row.source_type.value,
                counterparty_staff_id=row.counterparty_staff_id,
                route=record_route("cash_variance", row.id),
            )
            for row in rows
        ]

    def _people(self, user_id: uuid.UUID, start: datetime, end: datetime, truncated: list[str]) -> dict[str, Any]:
        d = DailyOperationalReport
        reports = list(
            self._s.execute(
                select(d)
                .where(d.submitted_by == user_id, d.submitted_at >= start, d.submitted_at < end)
                .order_by(d.submitted_at.desc(), d.id)
                .limit(LIMIT + 1)
            ).scalars()
        )
        if len(reports) > LIMIT:
            truncated.append("reports_submitted")
        decided, more_decided = history(self._s, user_id, "decided", start, end, LIMIT)
        requested, more_requested = history(self._s, user_id, "requested", start, end, LIMIT, adjustments_only=True)
        adjusted, more_adjusted = history(self._s, user_id, "decided", start, end, LIMIT, adjustments_only=True)
        for name, more in (
            ("approvals_made", more_decided),
            ("adjustments_requested", more_requested),
            ("adjustments_decided", more_adjusted),
        ):
            if more:
                truncated.append(name)
        return {
            "reports_submitted": [
                EmployeeRecordDto(
                    record_type="daily_report",
                    id=r.id,
                    status=r.status.value,
                    occurred_at=r.submitted_at,
                    amount=r.total_hours,
                    unit="HOURS",
                    route=record_route("daily_report", r.id),
                )
                for r in reports[:LIMIT]
            ],
            "approvals_made": [_flow_record(r, r.decided_at) for r in decided],
            "adjustments_requested": [_flow_record(r, r.requested_at) for r in requested],
            "adjustments_decided": [_flow_record(r, r.decided_at) for r in adjusted],
        }

    def _scorecard(self, staff_id: uuid.UUID, first: date, last: date) -> list[EmployeeRecordDto]:
        detail = ScorecardService(self._s, self._ctx, self._now).detail(staff_id, first, last, None)
        return [
            EmployeeRecordDto(
                record_type=r.record_type,
                id=r.record_id,
                status=r.status,
                occurred_at=r.at,
                amount=r.amount if r.amount is not None else r.hours,
                unit="MONEY" if r.amount is not None else ("HOURS" if r.hours is not None else None),
                currency=r.currency,
                label=str(r.item),
                route=record_route(r.record_type, r.record_id),
            )
            for r in detail.records
        ]


_NO_PERSON: dict[str, Any] = {
    "reports_submitted": [],
    "approvals_made": [],
    "adjustments_requested": [],
    "adjustments_decided": [],
}
