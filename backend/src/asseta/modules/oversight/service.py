"""People scorecard (DEC-031 M1): list and per-person detail assembled from ScorecardBuilder records, plus each
person's cash held now (cash custody service) and repeat-pattern signals about them."""

import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.errors import NotFound
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.models import CaseSignal, CaseSourceType, RiskSignal, RuleCode
from asseta.modules.oversight.checkins import period
from asseta.modules.oversight.dto import (
    AmountByCurrencyDto,
    CashHeldDto,
    ScorecardDetailDto,
    ScorecardRecordDto,
    ScorecardRowDto,
)
from asseta.modules.oversight.models import SiteCheckin
from asseta.modules.oversight.scorecard import HOURS, ScorecardBuilder, ScoreRecord, day_bounds
from asseta.modules.policy.schemas import ScorecardItem as I

DEFAULT_DAYS = 30


def _totals(records: list[ScoreRecord]) -> list[AmountByCurrencyDto]:
    acc: dict[str, list[Decimal]] = defaultdict(list)
    for r in records:
        if r.currency is not None and r.amount is not None:
            acc[r.currency].append(r.amount)
    return [AmountByCurrencyDto(currency=c, count=len(v), amount=sum(v, Decimal(0))) for c, v in sorted(acc.items())]


class ScorecardService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._b = ScorecardBuilder(session, self._tid, now)

    def _period(self, day_from: date | None, day_to: date | None) -> tuple[date, date]:
        return period(self._now.astimezone(self._b.tz).date(), day_from, day_to, DEFAULT_DAYS)

    def _checkins_required(self, first: date, last: date) -> bool:
        start, end = day_bounds(self._b.tz, first, last)
        return any(p.site_checkin_required for _, _, p in self._b.segments(start, min(end, max(self._now, start))))

    def _patterns(self, start: datetime, end: datetime) -> dict[uuid.UUID, list[RiskSignal]]:
        out: dict[uuid.UUID, list[RiskSignal]] = defaultdict(list)
        for sig in self._s.execute(
            select(RiskSignal).where(
                RiskSignal.rule_code == RuleCode.REPEATED_PATTERN,
                RiskSignal.created_at >= start,
                RiskSignal.created_at < end,
            )
        ).scalars():
            if sig.staff_member_id is not None:
                out[sig.staff_member_id].append(sig)
        return out

    def _row(
        self,
        staff: StaffMember,
        first: date,
        last: date,
        records: list[ScoreRecord],
        checkins_required: bool,
        checkins_made: int,
        patterns: int,
        with_cash: bool,
    ) -> ScorecardRowDto:
        by: dict[I, list[ScoreRecord]] = defaultdict(list)
        for r in records:
            by[r.item].append(r)
        alerts = by[I.ALERT]
        acks = [r.hours for r in alerts if r.hours is not None]
        machines = {r.machine_id for r in records if r.machine_id is not None}
        machines |= self._b.machines_of(staff.id)
        missed = len(by[I.MISSED_CHECKIN])
        return ScorecardRowDto(
            staff_member_id=staff.id,
            staff_member_name=staff.full_name,
            staff_kind=staff.kind.value,
            employee_code=staff.employee_code,
            is_active=staff.is_active,
            day_from=first,
            day_to=last,
            machines=len(machines),
            daily_reports_missing=len(by[I.MISSING_DAILY_REPORT]),
            daily_reports_late=len(by[I.LATE_DAILY_REPORT]),
            unexplained_hours=sum((r.hours or Decimal(0) for r in by[I.UNEXPLAINED_HOURS]), Decimal(0)).quantize(HOURS),
            unexplained_items=len(by[I.UNEXPLAINED_HOURS]),
            alerts=len(alerts),
            alerts_open=sum(1 for r in alerts if r.status == "OPEN"),
            alerts_acknowledged=len(acks),
            avg_hours_to_acknowledge=(sum(acks, Decimal(0)) / len(acks)).quantize(HOURS) if acks else None,
            max_hours_to_acknowledge=max(acks) if acks else None,
            cash_held=self._cash_held(staff.id) if with_cash else [],
            cash_held_too_long=len(by[I.CASH_HELD_TOO_LONG]),
            cash_differences=len(by[I.CASH_DIFFERENCE]),
            cash_difference_totals=_totals(by[I.CASH_DIFFERENCE]),
            cash_differences_near_threshold=sum(1 for r in by[I.CASH_DIFFERENCE] if r.near_threshold),
            revenue_differences=len(by[I.REVENUE_DIFFERENCE]),
            revenue_difference_totals=_totals(by[I.REVENUE_DIFFERENCE]),
            refused_attempts=len(by[I.REFUSED_ATTEMPT]),
            checkins_missed=missed if checkins_required else None,
            checkins_made=checkins_made,
            pattern_signals=patterns,
            items_total=len([r for r in records if r.item is not I.ALERT or r.status == "OPEN"]) + patterns,
        )

    def _cash_held(self, staff_id: uuid.UUID) -> list[CashHeldDto]:
        svc = CashCustodyService(self._s, self._ctx, self._now)
        out = []
        for bal in svc.balances(staff_id):
            amount, since = svc.unremitted_since(staff_id, bal.currency)
            if amount > 0:
                out.append(
                    CashHeldDto(
                        currency=bal.currency,
                        amount=amount,
                        held_since=since,
                        held_days=(self._now - since).days if since else None,
                    )
                )
        return out

    def _made(self, start: datetime, end: datetime) -> dict[uuid.UUID, int]:
        out: dict[uuid.UUID, int] = defaultdict(int)
        for staff_id in self._s.execute(
            select(SiteCheckin.staff_member_id).where(SiteCheckin.captured_at >= start, SiteCheckin.captured_at < end)
        ).scalars():
            out[staff_id] += 1
        return out

    def rows(
        self,
        day_from: date | None,
        day_to: date | None,
        staff_id: uuid.UUID | None,
        site_id: uuid.UUID | None,
        q: str | None,
    ) -> list[ScorecardRowDto]:
        first, last = self._period(day_from, day_to)
        start, end = day_bounds(self._b.tz, first, last)
        per = self._b.collect(first, last)
        people = select(StaffMember).order_by(StaffMember.full_name, StaffMember.id)
        if staff_id:
            people = people.where(StaffMember.id == staff_id)
        if q and q.strip():
            people = people.where(StaffMember.full_name.ilike(f"%{q.strip()}%"))
        at_site = self._b.people_at_site(site_id, start, end) if site_id else None
        required = self._checkins_required(first, last)
        made = self._made(start, end)
        patterns = self._patterns(start, end)
        staff = [
            p
            for p in self._s.execute(people).scalars()
            if (p.is_active or per.get(p.id)) and (at_site is None or p.id in at_site)
        ]
        rows = [
            self._row(
                p, first, last, per.get(p.id, []), required, made.get(p.id, 0), len(patterns.get(p.id, [])), False
            )
            for p in staff
        ]
        rows.sort(key=lambda r: (-r.items_total, r.staff_member_name or "", str(r.staff_member_id)))
        return rows

    def page(
        self,
        day_from: date | None,
        day_to: date | None,
        staff_id: uuid.UUID | None,
        site_id: uuid.UUID | None,
        q: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ScorecardRowDto], int]:
        rows = self.rows(day_from, day_to, staff_id, site_id, q)
        page = rows[offset : offset + limit]
        for r in page:
            r.cash_held = self._cash_held(r.staff_member_id)
        return page, len(rows)

    def detail(
        self, staff_member_id: uuid.UUID, day_from: date | None, day_to: date | None, item: I | None
    ) -> ScorecardDetailDto:
        staff = self._s.get(StaffMember, staff_member_id)
        if staff is None:
            raise NotFound("Staff member not found")
        first, last = self._period(day_from, day_to)
        start, end = day_bounds(self._b.tz, first, last)
        records = self._b.collect(first, last).get(staff.id, [])
        patterns = self._patterns(start, end).get(staff.id, [])
        row = self._row(
            staff,
            first,
            last,
            records,
            self._checkins_required(first, last),
            self._made(start, end).get(staff.id, 0),
            len(patterns),
            True,
        )
        out = [
            ScorecardRecordDto(
                item=r.item,
                record_type=r.record_type,
                record_id=r.record_id,
                at=r.at,
                day=r.day,
                machine_id=r.machine_id,
                job_id=r.job_id,
                currency=r.currency,
                amount=r.amount,
                hours=r.hours,
                status=r.status,
                near_threshold=r.near_threshold,
                detail=r.detail,
            )
            for r in records
            if item is None or r.item is item
        ]
        if item is None:
            cases = dict(
                self._s.execute(
                    select(CaseSignal.source_id, CaseSignal.case_id).where(
                        CaseSignal.source_type == CaseSourceType.RISK_SIGNAL,
                        CaseSignal.source_id.in_([p.id for p in patterns]),
                    )
                ).all()
            )
            out += [
                ScorecardRecordDto(
                    item="PATTERN_SIGNAL",
                    record_type="risk_signal",
                    record_id=p.id,
                    at=p.created_at,
                    day=p.created_at.astimezone(self._b.tz).date(),
                    status=p.status.value,
                    detail={**p.evidence, "case_id": str(cases[p.id]) if p.id in cases else None},
                )
                for p in patterns
            ]
        out.sort(key=lambda r: (r.at, str(r.record_id)), reverse=True)
        return ScorecardDetailDto(row=row, records=out)
