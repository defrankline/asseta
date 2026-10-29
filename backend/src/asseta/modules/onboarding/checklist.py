"""Go-live setup checklist: ordered steps a tenant completes before relying on the system, each computed LIVE from the
tenant's own data (never ticked by hand). Step definitions are generic data (no tenant names, roles or amounts); the
owner's only inputs are "not needed" marks, the "default controls are fine" confirmation and dismissing the banner
(`TenantSetupChoice`, append-only).

Cheap by design: every fact comes from ONE SQL statement of scalar sub-queries plus one read of the owner's choices,
so `/me` can carry the progress for a banner. Capability-dependent steps read the tenant's switched-off capabilities
(the caller passes the set it already resolved)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from asseta.modules.onboarding.models import SetupChoiceAction, TenantSetupChoice
from asseta.modules.policy.capabilities import (
    CASH_CUSTODY,
    CUSTOMER_HOURS,
    ENGINE_HOURS,
    REVENUE_RECONCILIATION,
    disabled_capabilities,
)

SETUP_READ_PERMISSION = "tenant.setup.read"

# Generic permission semantics (catalog codes, not role names): who records in the field and who approves.
FIELD_PERMISSION = "tenant.job.log"
APPROVER_PERMISSION = "tenant.job.approve"
MIN_APPROVERS = 2  # proposer != approver needs a second person who can decide


class StepStatus(StrEnum):
    DONE = "DONE"
    TODO = "TODO"
    NOT_NEEDED = "NOT_NEEDED"  # the owner marked it as not needed for the business
    NOT_APPLICABLE = "NOT_APPLICABLE"  # the capability it configures is switched off


class StepKey(StrEnum):
    COMPANY_SETTINGS = "COMPANY_SETTINGS"
    PEOPLE = "PEOPLE"
    MACHINE_TYPES_AND_RATES = "MACHINE_TYPES_AND_RATES"
    MACHINES = "MACHINES"
    TRACKERS = "TRACKERS"
    SITES = "SITES"
    CUSTOMERS_AND_CONTRACTS = "CUSTOMERS_AND_CONTRACTS"
    CONTROLS_CHOSEN = "CONTROLS_CHOSEN"
    REASON_LISTS = "REASON_LISTS"
    DEPOSIT_ACCOUNTS = "DEPOSIT_ACCOUNTS"
    METER_BASELINES = "METER_BASELINES"
    FIELD_APP_SIGNED_IN = "FIELD_APP_SIGNED_IN"
    FIRST_JOB = "FIRST_JOB"


@dataclass(frozen=True)
class Check:
    """One part of a step (e.g. one reason list), with its own count and the exact page that fixes it."""

    key: str
    label: str
    done: bool
    link: str
    required_permission: str
    done_count: int | None = None
    total_count: int | None = None
    optional: bool = False  # shown as advice; never holds the step back


@dataclass(frozen=True)
class Evaluation:
    done: bool
    done_count: int | None = None
    total_count: int | None = None
    checks: tuple[Check, ...] = ()
    link: str | None = None  # overrides the step's default link (points at the first thing still to do)
    applicable: bool = True


Facts = dict[str, int]


@dataclass(frozen=True)
class StepDef:
    key: StepKey
    title: str
    description: str
    link: str
    required_permission: str
    can_mark_not_needed: bool
    evaluate: Callable[[Facts, frozenset[str], bool], Evaluation] = field(repr=False)


def _count_step(total: int, done: int) -> tuple[bool, int, int]:
    return total > 0 and done == total, done, total


def _company(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    return Evaluation(done=f["settings_set"] > 0)


def _people(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    field_users, linked, approvers = f["field_users"], f["field_users_linked"], f["approvers"]
    checks = (
        Check(
            "FIELD_USERS",
            "At least one person who records work in the field (supervisor login)",
            field_users >= 1,
            "/tenant/access",
            "tenant.access.manage",
            min(field_users, 1),
            1,
        ),
        Check(
            "APPROVERS",
            f"At least {MIN_APPROVERS} people who can approve, so nobody approves their own request",
            approvers >= MIN_APPROVERS,
            "/tenant/access",
            "tenant.access.manage",
            min(approvers, MIN_APPROVERS),
            MIN_APPROVERS,
        ),
        Check(
            "FIELD_USERS_LINKED",
            "Every supervisor login is linked to a staff record",
            field_users >= 1 and linked == field_users,
            "/tenant/staff?kind=SUPERVISOR",
            "tenant.staff.write",
            linked,
            field_users,
        ),
    )
    return _from_checks(checks)


def _rates(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    rated, n, total = _count_step(f["categories"], f["categories_rated"])
    checks = (
        Check(
            "CATEGORIES",
            "At least one machine type (category)",
            f["categories"] > 0,
            "/tenant/machines",
            "tenant.machine.write",
            min(f["categories"], 1),
            1,
        ),
        Check(
            "RATE_CARDS",
            "Every active machine type has a current hourly rate",
            rated,
            "/tenant/customers?section=rate-cards",
            "tenant.customer.write",
            n,
            total,
        ),
    )
    return _from_checks(checks, n, total)


def _machines(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    return Evaluation(done=f["machines"] > 0, done_count=min(f["machines"], 1), total_count=1)


def _trackers(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    total = f["machines"]
    checks = (
        Check(
            "PRIMARY_TRACKER",
            "Every active machine has a tracker fitted as its main tracker",
            total > 0 and f["machines_tracked"] == total,
            "/tenant/machines?missing=tracker",
            "tenant.tracker.write",
            f["machines_tracked"],
            total,
        ),
        Check(
            "ENROLLED",
            "Every active machine is enrolled for tracking on the subscription",
            total > 0 and f["machines_enrolled"] == total,
            "/tenant/machines?missing=enrollment",
            "tenant.billing.enroll",
            f["machines_enrolled"],
            total,
        ),
    )
    _done, n, total = _count_step(total, f["machines_tracked_enrolled"])
    return _from_checks(checks, n, total)


def _sites(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    checks = (
        Check(
            "JOB_SITES",
            "At least one job site",
            f["sites"] > 0,
            "/tenant/geofences?tab=sites",
            "tenant.geofence.write",
            min(f["sites"], 1),
            1,
        ),
        Check(
            "GEOFENCES",
            "Optional: a boundary (geofence) around a site, to be told when a machine leaves it",
            f["geofences"] > 0,
            "/tenant/geofences",
            "tenant.geofence.write",
            min(f["geofences"], 1),
            1,
            optional=True,
        ),
    )
    return _from_checks(checks)


def _customers(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    n = f["customers_with_contract"]
    return Evaluation(done=n > 0, done_count=min(n, 1), total_count=1)


def _controls(f: Facts, _off: frozenset[str], confirmed: bool) -> Evaluation:
    return Evaluation(done=f["tenant_policy_versions"] > 0 or confirmed)


# Reason lists used by switched-on capabilities: (check key, label, facts key, capability, link, permission).
REASON_LISTS: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        "HOURS_REASONS",
        "Customer-hours reasons (discounts, credit, transfers, cancellations)",
        "hours_reasons",
        CUSTOMER_HOURS,
        "/tenant/hours/reasons",
        "tenant.hours.reasons",
    ),
    (
        "ENGINE_HOUR_REASONS",
        "Engine-hour reasons (non-customer work and differences)",
        "engine_reasons",
        ENGINE_HOURS,
        "/tenant/engine-hour-reasons",
        "tenant.meter.reasons",
    ),
    (
        "CASH_REASONS",
        "Cash reasons (differences, write-offs, retentions, adjustments)",
        "cash_reasons",
        CASH_CUSTODY,
        "/tenant/finance/cash?tab=reasons",
        "tenant.finance.reason_manage",
    ),
    (
        "REVENUE_REASONS",
        "Revenue reasons (explaining revenue differences)",
        "revenue_reasons",
        REVENUE_RECONCILIATION,
        "/tenant/revenue-reasons",
        "tenant.revenue.decide",
    ),
)


def _reasons(f: Facts, off: frozenset[str], _c: bool) -> Evaluation:
    checks = tuple(
        Check(key, label, f[fact] > 0, link, perm, min(f[fact], 1), 1)
        for key, label, fact, cap, link, perm in REASON_LISTS
        if cap not in off
    )
    if not checks:
        return Evaluation(done=False, applicable=False)
    return _from_checks(checks, sum(1 for c in checks if c.done), len(checks))


def _deposits(f: Facts, off: frozenset[str], _c: bool) -> Evaluation:
    n = f["deposit_accounts"]
    return Evaluation(done=n > 0, done_count=min(n, 1), total_count=1, applicable=CASH_CUSTODY not in off)


def _baselines(f: Facts, off: frozenset[str], _c: bool) -> Evaluation:
    done, n, total = _count_step(f["machines"], f["machines_baselined"])
    return Evaluation(done=done, done_count=n, total_count=total, applicable=ENGINE_HOURS not in off)


def _devices(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    return Evaluation(done=f["field_devices"] > 0, done_count=min(f["field_devices"], 1), total_count=1)


def _first_job(f: Facts, _off: frozenset[str], _c: bool) -> Evaluation:
    return Evaluation(done=f["jobs_started"] > 0, done_count=min(f["jobs_started"], 1), total_count=1)


def _from_checks(checks: tuple[Check, ...], n: int | None = None, total: int | None = None) -> Evaluation:
    """Done when every check is; the step links to the first check still to do."""
    required = [c for c in checks if not c.optional]
    todo = next((c for c in required if not c.done), None)
    if n is None:
        n, total = sum(1 for c in required if c.done), len(required)
    return Evaluation(
        done=todo is None, done_count=n, total_count=total, checks=checks, link=todo.link if todo else None
    )


STEPS: tuple[StepDef, ...] = (
    StepDef(
        StepKey.COMPANY_SETTINGS,
        "Company settings",
        "Check the company's time zone and currency. Every day, report and amount in the system uses them.",
        "/tenant/subscription",
        "tenant.billing.read",
        False,
        _company,
    ),
    StepDef(
        StepKey.PEOPLE,
        "People and logins",
        "Give your supervisors a login so they can record work in the field, and give at least two people the right "
        "to approve, so nobody approves their own request. Link each supervisor's login to their staff record.",
        "/tenant/access",
        "tenant.access.manage",
        True,
        _people,
    ),
    StepDef(
        StepKey.MACHINE_TYPES_AND_RATES,
        "Machine types and rates",
        "Add your machine types (for example excavators or graders) and the current hourly rate for each type.",
        "/tenant/machines",
        "tenant.machine.write",
        False,
        _rates,
    ),
    StepDef(
        StepKey.MACHINES,
        "Machines",
        "Register the machines you hire out or operate.",
        "/tenant/machines",
        "tenant.machine.write",
        False,
        _machines,
    ),
    StepDef(
        StepKey.TRACKERS,
        "Trackers",
        "Fit a tracker to every active machine and enrol it for tracking, so the system sees where it is and when "
        "the engine runs. Mark this step as not needed if you do not use trackers.",
        "/tenant/trackers",
        "tenant.tracker.write",
        True,
        _trackers,
    ),
    StepDef(
        StepKey.SITES,
        "Job sites",
        "Add the sites where your machines work. Drawing a boundary (geofence) around a site is optional; it lets "
        "the system tell you when a machine leaves the site.",
        "/tenant/geofences?tab=sites",
        "tenant.geofence.write",
        True,
        _sites,
    ),
    StepDef(
        StepKey.CUSTOMERS_AND_CONTRACTS,
        "Customers and contracts",
        "Add at least one customer with an active contract, so jobs can be priced and billed.",
        "/tenant/customers",
        "tenant.customer.write",
        True,
        _customers,
    ),
    StepDef(
        StepKey.CONTROLS_CHOSEN,
        "Choose your controls",
        "Review the rules the system applies (approvals, cash, engine hours, revenue checks) and change any that do "
        "not fit your business, or confirm that the defaults are fine.",
        "/tenant/policies",
        "tenant.policy.manage",
        False,
        _controls,
    ),
    StepDef(
        StepKey.REASON_LISTS,
        "Reason lists",
        "Fill in the reasons people pick from when they explain a difference, for each control you switched on.",
        "/tenant/policies",
        "tenant.policy.manage",
        True,
        _reasons,
    ),
    StepDef(
        StepKey.DEPOSIT_ACCOUNTS,
        "Deposit accounts",
        "Add the bank or mobile-money accounts that field cash is paid into.",
        "/tenant/finance/deposit-accounts",
        "tenant.finance.accounts.manage",
        True,
        _deposits,
    ),
    StepDef(
        StepKey.METER_BASELINES,
        "Hour-meter starting readings",
        "Record and approve the starting hour-meter reading of every active machine, so engine hours can be checked "
        "from day one.",
        "/tenant/meter-baselines?missing=true",
        "tenant.meter.approve",
        True,
        _baselines,
    ),
    StepDef(
        StepKey.FIELD_APP_SIGNED_IN,
        "Field app signed in",
        "Have at least one supervisor install the field app and sign in on their phone.",
        "/tenant/access",
        "tenant.access.manage",
        True,
        _devices,
    ),
    StepDef(
        StepKey.FIRST_JOB,
        "First job",
        "Approve or start your first job. From then on the system checks work, hours and money every day.",
        "/tenant/jobs",
        "tenant.job.approve",
        False,
        _first_job,
    ),
)
STEP_BY_KEY = {s.key: s for s in STEPS}

# ONE statement: every fact as a scalar sub-query, each confined to the tenant (and RLS applies on tenant tables).
_FACTS_SQL = text("""
WITH holders AS (
    SELECT DISTINCT tm.user_id, u.keycloak_subject, rp.permission_code
      FROM tenant_membership tm
      JOIN app_user u ON u.id = tm.user_id AND u.is_active
      JOIN role_permission rp ON rp.role_id = tm.role_id
     WHERE tm.tenant_id = :tid AND tm.effective_to IS NULL
       AND rp.permission_code IN (:field_perm, :approver_perm)
       AND NOT EXISTS (SELECT 1 FROM mandate_assignment ma WHERE ma.tenant_id = :tid AND ma.user_id = tm.user_id)
), field_users AS (
    SELECT DISTINCT user_id, keycloak_subject FROM holders h
     WHERE h.permission_code = :field_perm
       AND NOT EXISTS (SELECT 1 FROM holders a WHERE a.user_id = h.user_id AND a.permission_code = :approver_perm)
), active_machines AS (
    SELECT id FROM machine WHERE tenant_id = :tid AND status = 'ACTIVE'
), tracked AS (
    SELECT DISTINCT ta.machine_id FROM tracker_assignment ta
     WHERE ta.tenant_id = :tid AND ta.is_primary AND ta.effective_from <= :now
       AND (ta.effective_to IS NULL OR ta.effective_to > :now)
), enrolled AS (
    SELECT DISTINCT e.machine_id FROM subscription_asset_enrollment e
     WHERE e.tenant_id = :tid AND e.effective_from <= CAST(:now AS date)
       AND (e.effective_to IS NULL OR e.effective_to > CAST(:now AS date))
)
SELECT
  (SELECT count(*) FROM tenant_settings s
    WHERE s.tenant_id = :tid AND s.timezone <> '' AND s.currency <> '') AS settings_set,
  (SELECT count(*) FROM field_users) AS field_users,
  (SELECT count(*) FROM field_users f WHERE EXISTS (
      SELECT 1 FROM staff_member sm WHERE sm.tenant_id = :tid AND sm.is_active
         AND sm.keycloak_subject = f.keycloak_subject)) AS field_users_linked,
  (SELECT count(DISTINCT user_id) FROM holders WHERE permission_code = :approver_perm) AS approvers,
  (SELECT count(*) FROM machine_category c WHERE c.tenant_id = :tid AND c.is_active) AS categories,
  (SELECT count(*) FROM machine_category c WHERE c.tenant_id = :tid AND c.is_active AND EXISTS (
      SELECT 1 FROM rental_rate_policy r WHERE r.tenant_id = :tid AND r.machine_category_id = c.id
         AND r.effective_from <= :now)) AS categories_rated,
  (SELECT count(*) FROM active_machines) AS machines,
  (SELECT count(*) FROM active_machines m WHERE m.id IN (SELECT machine_id FROM tracked)) AS machines_tracked,
  (SELECT count(*) FROM active_machines m WHERE m.id IN (SELECT machine_id FROM enrolled)) AS machines_enrolled,
  (SELECT count(*) FROM active_machines m
    WHERE m.id IN (SELECT machine_id FROM tracked) AND m.id IN (SELECT machine_id FROM enrolled))
    AS machines_tracked_enrolled,
  (SELECT count(*) FROM job_site js WHERE js.tenant_id = :tid AND js.is_active) AS sites,
  (SELECT count(*) FROM geofence g WHERE g.tenant_id = :tid AND g.is_active) AS geofences,
  (SELECT count(DISTINCT rc.customer_id) FROM rental_contract rc
     JOIN customer cu ON cu.id = rc.customer_id AND cu.is_active
    WHERE rc.tenant_id = :tid AND rc.status = 'ACTIVE') AS customers_with_contract,
  (SELECT count(*) FROM policy_version pv WHERE pv.tenant_id = :tid) AS tenant_policy_versions,
  (SELECT count(*) FROM hours_reason_code x WHERE x.tenant_id = :tid AND x.is_active) AS hours_reasons,
  (SELECT count(*) FROM engine_hour_reason x WHERE x.tenant_id = :tid AND x.is_active) AS engine_reasons,
  (SELECT count(*) FROM cash_reason x WHERE x.tenant_id = :tid AND x.is_active) AS cash_reasons,
  (SELECT count(*) FROM revenue_reason x WHERE x.tenant_id = :tid AND x.is_active) AS revenue_reasons,
  (SELECT count(*) FROM company_deposit_account d WHERE d.tenant_id = :tid AND d.is_active) AS deposit_accounts,
  (SELECT count(*) FROM active_machines m WHERE EXISTS (
      SELECT 1 FROM machine_meter_baseline b WHERE b.tenant_id = :tid AND b.machine_id = m.id
         AND b.status = 'APPROVED')) AS machines_baselined,
  (SELECT count(*) FROM device_session ds WHERE ds.tenant_id = :tid AND ds.status = 'ACTIVE') AS field_devices,
  (SELECT count(*) FROM job j WHERE j.tenant_id = :tid
      AND j.status IN ('APPROVED', 'IN_PROGRESS', 'COMPLETED')) AS jobs_started
""")


def load_facts(session: Session, tenant_id: uuid.UUID, now: datetime) -> Facts:
    row = session.execute(
        _FACTS_SQL,
        {"tid": tenant_id, "now": now, "field_perm": FIELD_PERMISSION, "approver_perm": APPROVER_PERMISSION},
    ).one()
    return {k: int(v) for k, v in row._mapping.items()}


@dataclass(frozen=True)
class NotNeededMark:
    reason: str | None
    marked_by: uuid.UUID
    marked_at: datetime


@dataclass
class Choices:
    """The owner's current choices, folded from the append-only log (latest row wins)."""

    not_needed: dict[str, NotNeededMark] = field(default_factory=dict)
    controls_confirmed_by: uuid.UUID | None = None
    controls_confirmed_at: datetime | None = None
    dismissed: bool = False
    dismissed_by: uuid.UUID | None = None
    dismissed_at: datetime | None = None


def load_choices(session: Session, tenant_id: uuid.UUID) -> Choices:
    rows = session.execute(
        select(TenantSetupChoice).where(TenantSetupChoice.tenant_id == tenant_id).order_by(TenantSetupChoice.seq)
    ).scalars()
    out = Choices()
    for r in rows:
        if r.action is SetupChoiceAction.STEP_NOT_NEEDED and r.step_key:
            out.not_needed[r.step_key] = NotNeededMark(r.reason, r.recorded_by, r.recorded_at)
        elif r.action is SetupChoiceAction.STEP_NEEDED and r.step_key:
            out.not_needed.pop(r.step_key, None)
        elif r.action is SetupChoiceAction.CONTROLS_CONFIRMED:
            out.controls_confirmed_by, out.controls_confirmed_at = r.recorded_by, r.recorded_at
        elif r.action is SetupChoiceAction.DISMISSED:
            out.dismissed, out.dismissed_by, out.dismissed_at = True, r.recorded_by, r.recorded_at
        elif r.action is SetupChoiceAction.UNDISMISSED:
            out.dismissed, out.dismissed_by, out.dismissed_at = False, None, None
    return out


@dataclass(frozen=True)
class StepResult:
    step: StepDef
    order: int
    status: StepStatus
    evaluation: Evaluation
    not_needed: NotNeededMark | None


@dataclass(frozen=True)
class ChecklistResult:
    steps: list[StepResult]
    choices: Choices
    facts: Facts

    @property
    def steps_total(self) -> int:
        return sum(1 for s in self.steps if s.status is not StepStatus.NOT_APPLICABLE)

    @property
    def steps_done(self) -> int:
        return sum(1 for s in self.steps if s.status in (StepStatus.DONE, StepStatus.NOT_NEEDED))

    @property
    def percent(self) -> int:
        return 100 if self.steps_total == 0 else (self.steps_done * 100) // self.steps_total

    @property
    def complete(self) -> bool:
        return self.steps_done == self.steps_total


def compute(
    session: Session, tenant_id: uuid.UUID, now: datetime, disabled: frozenset[str] | None = None
) -> ChecklistResult:
    """Every step's status, from the tenant's data now (read in the tenant's RLS scope)."""
    off = disabled if disabled is not None else disabled_capabilities(session, tenant_id, now)
    facts = load_facts(session, tenant_id, now)
    choices = load_choices(session, tenant_id)
    results = []
    for order, step in enumerate(STEPS, start=1):
        ev = step.evaluate(facts, off, choices.controls_confirmed_by is not None)
        mark = choices.not_needed.get(step.key) if step.can_mark_not_needed else None
        if not ev.applicable:
            status = StepStatus.NOT_APPLICABLE
        elif ev.done:
            status = StepStatus.DONE
        elif mark is not None:
            status = StepStatus.NOT_NEEDED
        else:
            status = StepStatus.TODO
        results.append(StepResult(step, order, status, ev, mark))
    return ChecklistResult(results, choices, facts)
