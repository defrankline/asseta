"""Tenant data export requests, status, download links and evidence links (permission-gated, every step audited)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.config import get_settings
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.storage import ObjectStore
from asseta.modules.dataprotection.dto import DownloadLinkDto
from asseta.modules.dataprotection.models import ExportFormat, ExportStatus, TenantDataExport
from asseta.modules.fleet.photos import MachinePhoto
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.models import CaptureAttachment
from asseta.modules.policy.service import PolicyService

ENTITY = "tenant_data_export"
EVIDENCE_SOURCES: dict[str, Any] = {
    "capture_attachment": CaptureAttachment,
    "machine_photo": MachinePhoto,
}


class DataExportService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    def _read_only_note(self) -> dict[str, Any]:
        """Marks an audit entry written while the subscription was read-only (the guideline 9 exemption)."""
        return {"subscription_read_only": True} if self._ctx.read_only else {}

    def request(self, fmt: ExportFormat) -> TenantDataExport:
        policy = PolicyService(self._s).data_protection(self._tid, at=self._now)
        row = TenantDataExport(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            format=fmt,
            status=ExportStatus.QUEUED,
            requested_by=self._ctx.user_id,
            requested_at=self._now,
            attempts=0,
            policy_version=policy.version_stamp,
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("An export is already being prepared", code="EXPORT_IN_PROGRESS") from exc
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="tenant.data_export.requested",
            entity_type=ENTITY,
            entity_id=row.id,
            tenant_id=self._tid,
            after={"format": fmt.value, "status": row.status.value} | self._read_only_note(),
            policy_version=policy.version_stamp,
        )
        return row

    def list_query(self) -> Select[TenantDataExport]:
        return select(TenantDataExport).order_by(TenantDataExport.requested_at.desc(), TenantDataExport.id)

    def get(self, export_id: uuid.UUID) -> TenantDataExport:
        row = self._s.get(TenantDataExport, export_id)
        if row is None:
            raise NotFound("Export not found")
        return row

    def download_link(self, export_id: uuid.UUID, store: ObjectStore) -> DownloadLinkDto:
        row = self.get(export_id)
        if row.status is ExportStatus.EXPIRED or (row.expires_at is not None and row.expires_at <= self._now):
            raise BusinessRuleViolation("This export has expired; request a new one", code="EXPORT_EXPIRED")
        if row.status is not ExportStatus.COMPLETED or row.object_key is None:
            raise BusinessRuleViolation("This export is not ready", code="EXPORT_NOT_READY")
        ttl = get_settings().presigned_url_ttl_seconds
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="tenant.data_export.downloaded",
            entity_type=ENTITY,
            entity_id=row.id,
            tenant_id=self._tid,
            after={"sha256": row.sha256, "size_bytes": row.size_bytes} | self._read_only_note(),
        )
        return DownloadLinkDto(url=store.presigned_get(row.object_key, ttl), expires_in_seconds=ttl)

    def evidence_link(self, source: str, row_id: uuid.UUID, store: ObjectStore) -> DownloadLinkDto:
        model = EVIDENCE_SOURCES.get(source)
        row = self._s.get(model, row_id) if model is not None else None
        if row is None:
            raise NotFound("Evidence file not found")
        ttl = get_settings().presigned_url_ttl_seconds
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="tenant.data_export.evidence_fetched",
            entity_type=source,
            entity_id=row_id,
            tenant_id=self._tid,
            after={"sha256": row.sha256},
        )
        return DownloadLinkDto(url=store.presigned_get(row.object_key, ttl), expires_in_seconds=ttl)
