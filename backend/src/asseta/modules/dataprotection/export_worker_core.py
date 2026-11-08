"""The export job lifecycle: claim the oldest queued export, build it in the tenant's RLS scope, store the ZIP, record
the outcome (audited), and delete expired files. A worker that dies mid-build leaves a RUNNING row: after
RUNNING_TIMEOUT the job is queued again, up to MAX_ATTEMPTS."""

import hashlib
import shutil
import tempfile
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.modules.dataprotection.export_builder import build_zip
from asseta.modules.dataprotection.models import ExportStatus, TenantDataExport
from asseta.modules.policy.service import PolicyService
from asseta.modules.tenancy.models import Tenant

log = structlog.get_logger()
WORKER = AuditActor(None, [], "export-worker")
MAX_ATTEMPTS = 3
RUNNING_TIMEOUT = timedelta(hours=2)


def _digest(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _requeue_stale(s: Session, now: datetime) -> None:
    rows = s.execute(
        select(TenantDataExport)
        .where(TenantDataExport.status == ExportStatus.RUNNING, TenantDataExport.started_at < now - RUNNING_TIMEOUT)
        .with_for_update(skip_locked=True)
    ).scalars()
    for row in rows:
        if row.attempts >= MAX_ATTEMPTS:
            row.status, row.finished_at, row.error_code = ExportStatus.FAILED, now, "EXPORT_ABANDONED"
        else:
            row.status, row.started_at = ExportStatus.QUEUED, None


def claim_next(session_factory: Callable[[], Session], now: datetime) -> uuid.UUID | None:
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        _requeue_stale(s, now)
        row = s.execute(
            select(TenantDataExport)
            .where(TenantDataExport.status == ExportStatus.QUEUED)
            .order_by(TenantDataExport.requested_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()
        if row is None:
            return None
        row.status, row.started_at = ExportStatus.RUNNING, now
        row.attempts += 1
        return row.id


def _meta(s: Session, row: TenantDataExport, now: datetime) -> dict[str, Any]:
    tenant = s.get(Tenant, row.tenant_id)
    assert tenant is not None
    return {
        "export_id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "tenant_name": tenant.display_name,
        "registration_number": tenant.registration_number,
        "generated_at": now.isoformat(),
        "requested_by": str(row.requested_by) if row.requested_by else None,
    }


def _finish(
    session_factory: Callable[[], Session],
    export_id: uuid.UUID,
    tenant_id: uuid.UUID,
    now: datetime,
    **fields: Any,
) -> None:
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.TENANT, tenant_id, None)
        row = s.get(TenantDataExport, export_id)
        assert row is not None
        for key, value in fields.items():
            setattr(row, key, value)
        if row.status is not ExportStatus.EXPIRED:
            row.finished_at = now
        AuditService(s).record(
            actor=WORKER,
            action=f"tenant.data_export.{row.status.value.lower()}",
            entity_type="tenant_data_export",
            entity_id=row.id,
            tenant_id=tenant_id,
            after={k: str(v) for k, v in fields.items() if k != "status"} | {"status": row.status.value},
            policy_version=row.policy_version,
        )


def run_export(session_factory: Callable[[], Session], store: Any, export_id: uuid.UUID, now: datetime) -> None:
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        row = s.get(TenantDataExport, export_id)
        assert row is not None
        tenant_id, fmt = row.tenant_id, row.format
    workdir = Path(tempfile.mkdtemp(prefix="asseta-export-"))
    target = workdir / f"{export_id}.zip"
    try:
        with session_factory() as s, s.begin():
            s.connection(execution_options={"isolation_level": "REPEATABLE READ"})  # one snapshot for every table
            apply_scope(s, DbScope.TENANT, tenant_id, None)
            row = s.get(TenantDataExport, export_id)
            assert row is not None
            built = build_zip(s, tenant_id, fmt, target, _meta(s, row, now))
            retention = PolicyService(s).data_protection(tenant_id, at=now).policy.data_export_retention_days
        sha256, size = _digest(target)
        key = f"tenants/{tenant_id}/exports/{export_id}.zip"
        store.put_file(key, target, "application/zip", sha256)
        _finish(
            session_factory,
            export_id,
            tenant_id,
            now,
            status=ExportStatus.COMPLETED,
            object_key=key,
            sha256=sha256,
            size_bytes=size,
            table_count=len(built.tables),
            row_count=built.row_count,
            evidence_count=built.evidence_count,
            expires_at=now + timedelta(days=retention),
            error_code=None,
        )
    except Exception:
        log.exception("data_export_failed", export_id=str(export_id))
        _finish(session_factory, export_id, tenant_id, now, status=ExportStatus.FAILED, error_code="EXPORT_FAILED")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def expire_exports(session_factory: Callable[[], Session], store: Any, now: datetime) -> int:
    """Deletes the files of exports past their retention. A failed delete is retried on the next pass."""
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        due = [
            (r.id, r.tenant_id, r.object_key)
            for r in s.execute(
                select(TenantDataExport).where(
                    TenantDataExport.status == ExportStatus.COMPLETED, TenantDataExport.expires_at <= now
                )
            ).scalars()
        ]
    expired = 0
    for export_id, tenant_id, key in due:
        try:
            if key:
                store.delete(key)
            _finish(session_factory, export_id, tenant_id, now, status=ExportStatus.EXPIRED, object_key=None)
            expired += 1
        except Exception:
            log.exception("data_export_expiry_failed", export_id=str(export_id))
    return expired


def run_pending(session_factory: Callable[[], Session], store: Any, now: datetime) -> int:
    """One pass: expire what is due and build at most one queued export. Returns exports built."""
    expire_exports(session_factory, store, now)
    export_id = claim_next(session_factory, now)
    if export_id is None:
        return 0
    run_export(session_factory, store, export_id, now)
    return 1


__all__ = ["claim_next", "expire_exports", "run_export", "run_pending"]
