"""Runs due company deletions: closure requests whose waiting period has passed (or that the platform ran early).

Owner decision: after the waiting period EVERYTHING of the company is deleted (business records and master data:
machines, customers, staff, policies, users' access, files, tracker devices). The platform operator keeps only its own
billing records about the company (`tenant_tables.CLOSURE_KEEP`), the audit of those and of the closure itself, and a
minimal closed tenant row (names, registration number, `deleted_at`, `deletion_request_id`).

The deletion is a sequence of steps, each recorded in `company_deletion_request.steps` when it finishes, so a run that
fails halfway resumes where it stopped (the worker retries with a back-off; every step is idempotent):

  snapshot      who and what to remove outside the database (login subjects, tracker identifiers)
  subscription  the platform subscription is cancelled (billing stops; its records stay)
  identity      Keycloak: users who belong to no other company and hold no platform role are disabled and deleted
                (their app-user row anonymised); others only lose this company's groups; the company's groups go
  objects       every object-store file under `tenants/<id>/` and `platform/ml-models/<id>/`
  traccar       the trackers' Traccar devices (when Traccar admin credentials are configured; otherwise logged)
  database      every row of the company in every tenant-scoped table except CLOSURE_KEEP, one table per transaction
                as the schema owner (guards off only on that table, only while it is emptied; `steps.database.tables`
                is the resume point), then the tenant row is reduced and the request completed

The tenant is marked CLOSED when the deletion starts, so a restart of the API never recreates its Keycloak groups.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

import psycopg
import structlog
from psycopg import sql
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.correlation import set_correlation_id
from asseta.core.db import DbScope, apply_scope
from asseta.core.outbox import OutboxWriter
from asseta.modules.dataprotection.closure_service import STEP_ORDER, TOPIC
from asseta.modules.dataprotection.models import CompanyDeletionRequest, DeletionStatus
from asseta.modules.dataprotection.tenant_tables import CLOSURE_AUDIT_KEEP, closure_plan, guards_off
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.account_deletion import anonymise_user
from asseta.modules.identity.idp import IdentityProviderAdmin
from asseta.modules.identity.models import AppUser, PlatformMembership, TenantMembership
from asseta.modules.tenancy.models import Tenant, TenantAccessState, TenantStatus

log = structlog.get_logger()
WORKER = AuditActor(user_id=None, roles=["system:data-protection"], source="worker")
OBJECT_PREFIXES = ("tenants/{tid}/", "platform/ml-models/{tid}/")
# One sweep at a time across workers (pg_try_advisory_lock key: "company deletion").
SWEEP_LOCK = 0x41535345_44454C
CLOSED_REASON = "Company closed: all its data was deleted"
MAX_PASSES = 3


class FileStore(Protocol):
    def list_keys(self, prefix: str) -> list[str]: ...

    def delete(self, key: str) -> None: ...


class TraccarDevices(Protocol):
    def remove(self, unique_ids: list[str]) -> list[str]:
        """Removes the devices registered with each unique id; one line per id (removed / not registered / error)."""
        ...


class TraccarAdmin:
    """Traccar REST with an admin account (as `scripts/reset-tenant-data.sh --remove-traccar-devices`)."""

    def __init__(self, base_url: str, email: str, password: str, timeout: float = 30.0):
        self._base, self._auth, self._timeout = base_url.rstrip("/"), (email, password), timeout

    def remove(self, unique_ids: list[str]) -> list[str]:
        import httpx

        lines: list[str] = []
        for ext in unique_ids:
            try:
                r = httpx.get(
                    f"{self._base}/api/devices", params={"uniqueId": ext}, auth=self._auth, timeout=self._timeout
                )
                r.raise_for_status()
                found = r.json()
                if not found:
                    lines.append(f"{ext}: not registered")
                    continue
                for d in found:
                    httpx.delete(
                        f"{self._base}/api/devices/{d['id']}", auth=self._auth, timeout=self._timeout
                    ).raise_for_status()
                    lines.append(f"{ext}: removed")
            except httpx.HTTPError as e:
                lines.append(f"{ext}: NOT removed ({type(e).__name__})")
        return lines


@dataclass
class ClosureDeps:
    session_factory: Callable[[], Session]
    store: FileStore
    idp: IdentityProviderAdmin
    owner_dsn: str  # the schema owner's connection (as the migrations use): the guards are switched off per table
    clock: Callable[[], datetime]
    traccar: TraccarDevices | None = None


class StepFailed(Exception):
    def __init__(self, step: str, cause: BaseException):
        self.step = step
        super().__init__(f"{step}: {type(cause).__name__}: {cause}"[:500])


def psycopg_dsn(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _backoff(attempts: int) -> timedelta:
    return timedelta(minutes=min(5 * 2 ** max(attempts - 1, 0), 360))


# --- the sweep -------------------------------------------------------------------------------------------------------
def due_requests(session_factory: Callable[[], Session], now: datetime) -> list[uuid.UUID]:
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        return list(
            s.execute(
                select(CompanyDeletionRequest.id)
                .where(
                    or_(
                        (CompanyDeletionRequest.status == DeletionStatus.REQUESTED)
                        & (CompanyDeletionRequest.scheduled_for <= now),
                        (CompanyDeletionRequest.status == DeletionStatus.IN_PROGRESS)
                        & (
                            CompanyDeletionRequest.next_attempt_at.is_(None)
                            | (CompanyDeletionRequest.next_attempt_at <= now)
                        ),
                    )
                )
                .order_by(CompanyDeletionRequest.scheduled_for)
            ).scalars()
        )


def run_due_closures(deps: ClosureDeps) -> int:
    """Runs every due deletion; returns how many completed. One sweep at a time (advisory lock); a failed deletion
    records its error and is retried after a back-off, from the step where it stopped."""
    with psycopg.connect(deps.owner_dsn, autocommit=True) as lock_conn:
        row = lock_conn.execute("SELECT pg_try_advisory_lock(%s)", (SWEEP_LOCK,)).fetchone()
        if not row or not row[0]:
            return 0
        try:
            completed = 0
            for request_id in due_requests(deps.session_factory, deps.clock()):
                set_correlation_id(str(uuid.uuid4()))
                try:
                    completed += int(execute(deps, request_id))
                except Exception as exc:
                    log.exception("company_deletion_failed", request_id=str(request_id))
                    _record_failure(deps, request_id, exc)
            return completed
        finally:
            lock_conn.execute("SELECT pg_advisory_unlock(%s)", (SWEEP_LOCK,))


def _record_failure(deps: ClosureDeps, request_id: uuid.UUID, exc: Exception) -> None:
    now = deps.clock()
    with deps.session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        row = s.get(CompanyDeletionRequest, request_id, with_for_update=True)
        if row is None or row.status is not DeletionStatus.IN_PROGRESS:
            return
        row.last_error = str(exc)[:500] if isinstance(exc, StepFailed) else f"{type(exc).__name__}: {exc}"[:500]
        row.next_attempt_at = now + _backoff(row.attempts)


def execute(deps: ClosureDeps, request_id: uuid.UUID) -> bool:
    """Runs (or resumes) one deletion to the end. True when it completed in this call."""
    tenant_id = _start(deps, request_id)
    if tenant_id is None:
        return False
    steps: dict[str, Callable[[ClosureDeps, uuid.UUID, uuid.UUID], dict[str, Any]]] = {
        "snapshot": _snapshot,
        "subscription": _subscription,
        "identity": _identity,
        "objects": _objects,
        "traccar": _traccar,
        "database": _database,
    }
    assert tuple(steps) == STEP_ORDER
    for name, step in steps.items():
        if name in _steps(deps, request_id):
            continue
        try:
            result = step(deps, request_id, tenant_id)
        except Exception as exc:
            raise StepFailed(name, exc) from exc
        if name != "database":  # the database step completes the request in its own last transaction
            _mark(deps, request_id, name, result)
    log.info("company_deletion_completed", request_id=str(request_id), tenant_id=str(tenant_id))
    return True


def _steps(deps: ClosureDeps, request_id: uuid.UUID) -> dict[str, Any]:
    with deps.session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        row = s.get(CompanyDeletionRequest, request_id)
        return dict(row.steps or {}) if row is not None else {}


def _mark(deps: ClosureDeps, request_id: uuid.UUID, name: str, result: dict[str, Any]) -> None:
    with deps.session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        row = s.get(CompanyDeletionRequest, request_id, with_for_update=True)
        assert row is not None
        row.steps = {**(row.steps or {}), name: {"at": deps.clock().isoformat(), **result}}
        row.last_error, row.next_attempt_at = None, None


def _start(deps: ClosureDeps, request_id: uuid.UUID) -> uuid.UUID | None:
    """REQUESTED -> IN_PROGRESS (audited); the tenant is marked CLOSED. Counts the attempt."""
    now = deps.clock()
    with deps.session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        row = s.get(CompanyDeletionRequest, request_id, with_for_update=True)
        if row is None or row.status not in (DeletionStatus.REQUESTED, DeletionStatus.IN_PROGRESS):
            return None
        if row.status is DeletionStatus.REQUESTED:
            if row.scheduled_for > now:
                return None
            row.status, row.started_at = DeletionStatus.IN_PROGRESS, now
            AuditService(s).record(
                actor=WORKER,
                action="platform.company_closure.started",
                entity_type="company_deletion_request",
                entity_id=row.id,
                tenant_id=row.tenant_id,
                after={"status": row.status.value, "scheduled_for": row.scheduled_for.isoformat()},
                reason="Waiting period over" if row.execute_now_at is None else "Run early by the platform",
            )
        row.attempts += 1
        row.version += 1
        tenant = s.get(Tenant, row.tenant_id, with_for_update=True)
        assert tenant is not None
        tenant.status = TenantStatus.CLOSED
        return row.tenant_id


# --- steps -----------------------------------------------------------------------------------------------------------
def _snapshot(deps: ClosureDeps, _: uuid.UUID, tid: uuid.UUID) -> dict[str, Any]:
    from asseta.modules.tracker.models import Tracker

    prefix = f"/tenants/{tid}/"
    with deps.session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        subjects = set(
            s.execute(
                select(AppUser.keycloak_subject)
                .join(TenantMembership, TenantMembership.user_id == AppUser.id)
                .where(TenantMembership.tenant_id == tid)
            ).scalars()
        )
        subjects |= {
            x
            for x in s.execute(
                select(StaffMember.keycloak_subject).where(
                    StaffMember.tenant_id == tid, StaffMember.keycloak_subject.is_not(None)
                )
            ).scalars()
            if x
        }
        trackers = [
            ext for ext in s.execute(select(Tracker.external_id).where(Tracker.tenant_id == tid)).scalars() if ext
        ]
    for group in deps.idp.list_role_groups():
        if group.path.startswith(prefix):
            subjects |= {m.subject for m in deps.idp.list_group_members(group.group_id)}
    return {"subjects": sorted(subjects), "trackers": sorted(trackers)}


def _subscription(deps: ClosureDeps, _: uuid.UUID, tid: uuid.UUID) -> dict[str, Any]:
    from asseta.modules.platform_billing.dto import TransitionIn
    from asseta.modules.platform_billing.enums import ALLOWED_TRANSITIONS, SubscriptionStatus
    from asseta.modules.platform_billing.models_commercial import TenantSubscription
    from asseta.modules.platform_billing.subscription_service import SubscriptionService

    today: date = deps.clock().date()
    cancelled: list[str] = []
    with deps.session_factory() as s, s.begin():
        apply_scope(s, DbScope.PLATFORM, None, None)
        subs = s.execute(
            select(TenantSubscription).where(TenantSubscription.tenant_id == tid).with_for_update()
        ).scalars()
        for sub in list(subs):
            if SubscriptionStatus.CANCELLED not in ALLOWED_TRANSITIONS.get(sub.status, frozenset()):
                continue
            body = TransitionIn(
                to_status=SubscriptionStatus.CANCELLED,
                effective_date=today,
                reason="Company closed at the owner's request: all its data is deleted",
            )
            SubscriptionService(s, WORKER).transition(sub, body, today)
            cancelled.append(str(sub.id))
    return {"cancelled": cancelled}


def _identity(deps: ClosureDeps, request_id: uuid.UUID, tid: uuid.UUID) -> dict[str, Any]:
    prefix = f"/tenants/{tid}/"
    subjects: list[str] = _steps(deps, request_id)["snapshot"]["subjects"]
    now = deps.clock()
    deleted = kept = 0
    for subject in subjects:
        elsewhere = [g for g in deps.idp.user_group_paths(subject) if not g.startswith(prefix)]
        with deps.session_factory() as s, s.begin():
            apply_scope(s, DbScope.SYSTEM, None, None)
            user = s.execute(select(AppUser).where(AppUser.keycloak_subject == subject)).scalar_one_or_none()
            in_db_elsewhere = user is not None and (
                s.execute(
                    select(TenantMembership.id).where(
                        TenantMembership.user_id == user.id,
                        TenantMembership.tenant_id != tid,
                        TenantMembership.effective_to.is_(None),
                    )
                ).first()
                is not None
                or s.execute(
                    select(PlatformMembership.id).where(
                        PlatformMembership.user_id == user.id, PlatformMembership.effective_to.is_(None)
                    )
                ).first()
                is not None
            )
            if elsewhere or in_db_elsewhere:
                kept += 1  # only this company's groups go (deleted below, with their memberships)
                continue
            deps.idp.disable_user(subject)
            deps.idp.delete_user(subject)
            if user is not None:
                anonymise_user(s, user, now, None)
            deleted += 1
    deps.idp.delete_group(f"/tenants/{tid}")
    return {"accounts_deleted": deleted, "accounts_kept": kept}


def _objects(deps: ClosureDeps, _: uuid.UUID, tid: uuid.UUID) -> dict[str, Any]:
    deleted = 0
    for pattern in OBJECT_PREFIXES:
        for key in deps.store.list_keys(pattern.format(tid=tid)):
            deps.store.delete(key)
            deleted += 1
    return {"files_deleted": deleted}


def _traccar(deps: ClosureDeps, request_id: uuid.UUID, tid: uuid.UUID) -> dict[str, Any]:
    trackers: list[str] = _steps(deps, request_id)["snapshot"]["trackers"]
    if not trackers:
        return {"devices": 0}
    if deps.traccar is None:
        log.warning("company_deletion_traccar_skipped", tenant_id=str(tid), devices=trackers)
        return {"devices": len(trackers), "skipped": "Traccar admin credentials not configured: devices left there"}
    lines = deps.traccar.remove(trackers)
    return {"devices": len(trackers), "removed": sum(1 for x in lines if x.endswith(": removed"))}


# --- the database step (schema owner, one table per transaction) ------------------------------------------------------
def _tx(conn: psycopg.Connection[Any]) -> None:
    conn.execute("SET LOCAL lock_timeout = '10s'")
    conn.execute("SET LOCAL statement_timeout = '600s'")
    conn.execute("SELECT set_config('app.scope', 'system', true)")


def _count(conn: psycopg.Connection[Any], table: str, tid: uuid.UUID) -> int:
    row = conn.execute(
        sql.SQL("SELECT count(*) FROM {} WHERE tenant_id = %s").format(sql.Identifier(table)), (tid,)
    ).fetchone()
    return int(row[0]) if row else 0


def _progress(conn: psycopg.Connection[Any], request_id: uuid.UUID, table: str, rows: int) -> None:
    conn.execute(
        "UPDATE company_deletion_request SET steps = jsonb_set(steps, '{database_tables}',"
        " coalesce(steps->'database_tables', '{}'::jsonb) || jsonb_build_object(%s::text, %s::int)) WHERE id = %s",
        (table, rows, request_id),
    )


def _delete_table(conn: psycopg.Connection[Any], request_id: uuid.UUID, table: str, tid: uuid.UUID) -> int:
    """Empties one table of the company in one transaction, with its progress. Raises ForeignKeyViolation while a
    row of it is still referenced (the caller retries it after the others)."""
    with conn.transaction():
        _tx(conn)
        n = _count(conn, table, tid)
        if n:
            with guards_off(conn, [table]):
                conn.execute(sql.SQL("DELETE FROM {} WHERE tenant_id = %s").format(sql.Identifier(table)), (tid,))
        _progress(conn, request_id, table, n)
    return n


def _database(deps: ClosureDeps, request_id: uuid.UUID, tid: uuid.UUID) -> dict[str, Any]:
    with psycopg.connect(deps.owner_dsn, autocommit=True) as conn:
        with conn.transaction(force_rollback=True):
            _tx(conn)
            plan = closure_plan(conn)  # fails closed on a table nobody classified
        done: dict[str, int] = dict(_steps(deps, request_id).get("database_tables") or {})
        with conn.transaction():  # an issued platform invoice line keeps every printed field, only the pointer goes
            _tx(conn)
            charged = conn.execute(
                "SELECT count(*) FROM platform_invoice_line WHERE tenant_id = %s AND pending_charge_id IN"
                " (SELECT id FROM subscription_pending_charge WHERE tenant_id = %s)",
                (tid, tid),
            ).fetchone()
            if charged and charged[0]:
                with guards_off(conn, ["platform_invoice_line"]):
                    conn.execute(
                        "UPDATE platform_invoice_line SET pending_charge_id = NULL WHERE tenant_id = %s AND"
                        " pending_charge_id IN (SELECT id FROM subscription_pending_charge WHERE tenant_id = %s)",
                        (tid, tid),
                    )
        deleted = dict(done)
        for _ in range(MAX_PASSES):
            pending = [t for t in plan.delete if t not in done]
            while pending:
                failed: list[str] = []
                last: Exception | None = None
                for table in pending:
                    try:
                        deleted[table] = deleted.get(table, 0) + _delete_table(conn, request_id, table, tid)
                        done[table] = deleted[table]
                    except psycopg.errors.ForeignKeyViolation as e:
                        failed.append(table)
                        last = e
                if failed and len(failed) == len(pending):
                    raise RuntimeError(f"rows still referenced in {', '.join(failed)}: {last}")
                pending = failed
            with conn.transaction(force_rollback=True):
                _tx(conn)
                left = {t: n for t in plan.delete if (n := _count(conn, t, tid))}
            if not left:
                break
            done = {t: n for t, n in done.items() if t not in left}  # written meanwhile (a late device): again
        else:
            raise RuntimeError(f"rows keep appearing in {', '.join(sorted(left))}")
        with conn.transaction():
            _tx(conn)
            with guards_off(conn, ["audit_event"]):
                audit = conn.execute(
                    "DELETE FROM audit_event WHERE tenant_id = %s AND NOT (action LIKE ANY(%s))",
                    (tid, list(CLOSURE_AUDIT_KEEP)),
                ).rowcount
            idem = conn.execute("DELETE FROM idempotency_record WHERE scope_key = %s", (str(tid),)).rowcount
            grants = conn.execute(
                "DELETE FROM role_template_grant WHERE group_path LIKE %s", (f"/tenants/{tid}/%",)
            ).rowcount
    return _finish(deps, request_id, tid, deleted, audit, idem + grants)


def _finish(
    deps: ClosureDeps, request_id: uuid.UUID, tid: uuid.UUID, deleted: dict[str, int], audit: int, other: int
) -> dict[str, Any]:
    """The minimal closed tenant row, the completed request (identifiers of people and devices dropped from its
    record), the closure audit event and the platform notification, in one transaction."""
    now = deps.clock()
    rows = sum(deleted.values()) + audit + other
    with deps.session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        row = s.get(CompanyDeletionRequest, request_id, with_for_update=True)
        tenant = s.get(Tenant, tid, with_for_update=True)
        assert row is not None and tenant is not None
        tenant.status, tenant.access_state = TenantStatus.CLOSED, TenantAccessState.BLOCKED
        tenant.access_state_reason, tenant.access_state_changed_at = CLOSED_REASON, now
        tenant.contact_name, tenant.contact_email, tenant.contact_phone = "", "", None
        tenant.verification_note = tenant.live_note = None
        tenant.live_marked_by = None
        tenant.keycloak_group_id = None
        tenant.deleted_at, tenant.deletion_request_id = now, row.id
        steps = dict(row.steps or {})
        snapshot = steps.get("snapshot") or {}
        steps["snapshot"] = {
            "at": snapshot.get("at"),
            "accounts": len(snapshot.get("subjects") or []),
            "trackers": len(snapshot.get("trackers") or []),
        }
        steps.pop("database_tables", None)
        steps["database"] = {
            "at": now.isoformat(),
            "rows_deleted": rows,
            "tables": {t: n for t, n in sorted(deleted.items()) if n},
            "audit_events_deleted": audit,
        }
        row.steps = steps
        row.status, row.completed_at, row.last_error, row.next_attempt_at = DeletionStatus.COMPLETED, now, None, None
        row.version += 1
        identity = steps.get("identity") or {}
        files = (steps.get("objects") or {}).get("files_deleted", 0)
        summary = {
            "rows_deleted": rows,
            "files_deleted": files,
            "accounts_deleted": identity.get("accounts_deleted", 0),
            "accounts_kept": identity.get("accounts_kept", 0),
            "traccar": steps.get("traccar"),
            "subscription": steps.get("subscription"),
        }
        AuditService(s).record(
            actor=WORKER,
            action="platform.company_closure.completed",
            entity_type="company_deletion_request",
            entity_id=row.id,
            tenant_id=tid,
            after=summary,
            reason=f"All data of {tenant.display_name} deleted",
        )
        OutboxWriter(s).emit(
            topic=TOPIC,
            event_type="CompanyDeleted",
            key=str(tid),
            payload={
                "request_id": str(row.id),
                "tenant_id": str(tid),
                "tenant_name": tenant.display_name,
                "rows_deleted": rows,
                "objects_deleted": files,
                "accounts_deleted": identity.get("accounts_deleted", 0),
            },
            tenant_id=None,  # a platform event: the company's own notification audiences no longer exist
        )
    return summary
