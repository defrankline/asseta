"""Repeat-pattern risk signal (DEC-031 M1): when one person collects OVERSIGHT.repeat_pattern_count scorecard items
of one kind (repeat_pattern_items) within repeat_pattern_window_days, a REPEATED_PATTERN signal (subject STAFF) is
stored and joins the person's case through the usual case linker. Evidence lists the records; neutral wording —
a pattern is something to look at, never a verdict. At most one signal per person and kind per window; idempotent
(dedupe on the record that completed the pattern). Off unless the scorecard is on and repeat_pattern_count is set."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import StaffMember
from asseta.modules.intelligence.models import RiskSignal, RuleCode, SignalSeverity, SubjectType
from asseta.modules.intelligence.rules import SignalFinding
from asseta.modules.oversight.scorecard import ScorecardBuilder, ScoreRecord
from asseta.modules.policy.service import PolicyService


def _ref(r: ScoreRecord) -> dict[str, object]:
    return {
        "record_type": r.record_type,
        "record_id": str(r.record_id) if r.record_id else None,
        "at": r.at.isoformat(),
        "machine_id": str(r.machine_id) if r.machine_id else None,
        "currency": r.currency,
        "amount": str(r.amount) if r.amount is not None else None,
    }


def detect_person_patterns(s: Session, tenant_id: uuid.UUID, now: datetime) -> list[SignalFinding]:
    eff = PolicyService(s).oversight(tenant_id, at=now)
    policy = eff.policy
    if not policy.scorecard_enabled or policy.repeat_pattern_count is None or not policy.repeat_pattern_items:
        return []
    window = timedelta(days=policy.repeat_pattern_window_days)
    builder = ScorecardBuilder(s, tenant_id, now)
    per_person = builder.collect_range(now - 2 * window, now)
    kinds = set(policy.repeat_pattern_items)
    covered: dict[tuple[uuid.UUID, str], datetime] = {}
    for sig in s.execute(
        select(RiskSignal).where(
            RiskSignal.rule_code == RuleCode.REPEATED_PATTERN, RiskSignal.window_end > now - 2 * window
        )
    ).scalars():
        if sig.staff_member_id is not None:
            key = (sig.staff_member_id, str(sig.evidence.get("item")))
            covered[key] = max(covered.get(key, sig.window_end), sig.window_end)
    names = dict(s.execute(select(StaffMember.id, StaffMember.full_name)).all())
    out: list[SignalFinding] = []
    for staff_id, records in per_person.items():
        for kind in sorted(kinds):
            mine = [r for r in records if r.item is kind]
            for i, r in enumerate(mine):
                if r.at < now - window:
                    continue
                last = covered.get((staff_id, kind.value))
                if last is not None and last > r.at - window:
                    continue  # already signalled within the window
                inside = [x for x in mine[: i + 1] if x.at > r.at - window]
                if len(inside) < policy.repeat_pattern_count:
                    continue
                out.append(
                    SignalFinding(
                        RuleCode.REPEATED_PATTERN,
                        SignalSeverity.WARNING,
                        SubjectType.STAFF,
                        staff_id,
                        inside[0].at,
                        r.at,
                        f"PATTERN:{staff_id}:{kind.value}:{r.record_id or r.at.isoformat()}",
                        {
                            "item": kind.value,
                            "count": len(inside),
                            "threshold_count": policy.repeat_pattern_count,
                            "window_days": policy.repeat_pattern_window_days,
                            "staff_name": names.get(staff_id),
                            "records": [_ref(x) for x in inside],
                        },
                        policy_version=eff.version_stamp,
                        staff_member_id=staff_id,
                        involved_staff_ids=(staff_id,),
                    )
                )
                covered[(staff_id, kind.value)] = r.at
    return out
