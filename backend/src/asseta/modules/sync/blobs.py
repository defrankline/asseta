"""Resumable, checksum-verified evidence upload for devices on unreliable networks.

Chunks are staged in the database (tenant RLS), assembled on completion, verified against the declared SHA-256,
stored content-addressed in object storage and registered as a `capture_attachment` (same as the online path).
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from asseta.core.config import get_settings
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.storage import ObjectStore, sha256_hex, sniff_image
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.models import CaptureAttachment
from asseta.modules.sync.dto import BlobSessionDto, BlobStartIn
from asseta.modules.sync.models import BlobChunk, BlobUploadSession, DeviceSession

CHUNK_SIZE = 256 * 1024
SESSION_TTL = timedelta(days=7)


class BlobService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def _dto(self, row: BlobUploadSession) -> BlobSessionDto:
        received = list(
            self._s.execute(
                select(BlobChunk.chunk_index).where(BlobChunk.session_id == row.id).order_by(BlobChunk.chunk_index)
            ).scalars()
        )
        return BlobSessionDto(
            id=row.id,
            chunk_size=row.chunk_size,
            total_chunks=-(-row.size_bytes // row.chunk_size),
            received_chunks=received,
            status=row.status,
            attachment_id=row.attachment_id,
            expires_at=row.expires_at,
        )

    def start(self, device: DeviceSession, body: BlobStartIn) -> BlobSessionDto:
        if body.size_bytes > get_settings().max_image_bytes:
            raise BusinessRuleViolation("File too large", code="FILE_TOO_LARGE")
        existing = (
            self._s.execute(select(CaptureAttachment).where(CaptureAttachment.sha256 == body.sha256)).scalars().first()
        )
        row = BlobUploadSession(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            device_session_id=device.id,
            sha256=body.sha256,
            size_bytes=body.size_bytes,
            chunk_size=CHUNK_SIZE,
            purpose=body.purpose,
            status="COMPLETE" if existing else "OPEN",
            attachment_id=existing.id if existing else None,
            expires_at=self._now + SESSION_TTL,
        )
        self._s.add(row)  # already-known content: nothing to upload (dedupe)
        self._s.flush()
        return self._dto(row)

    def _open(self, session_id: uuid.UUID) -> BlobUploadSession:
        row = self._s.execute(
            select(BlobUploadSession).where(BlobUploadSession.id == session_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("Upload session not found")
        if row.expires_at < self._now:
            raise BusinessRuleViolation("Upload session expired", code="UPLOAD_EXPIRED")
        return row

    def put_chunk(self, session_id: uuid.UUID, index: int, data: bytes) -> BlobSessionDto:
        row = self._open(session_id)
        total = -(-row.size_bytes // row.chunk_size)
        if row.status == "COMPLETE":
            return self._dto(row)
        if not 0 <= index < total:
            raise BusinessRuleViolation("Chunk index out of range", code="BAD_CHUNK")
        expected = row.chunk_size if index < total - 1 else row.size_bytes - row.chunk_size * (total - 1)
        if len(data) != expected:
            raise BusinessRuleViolation(f"Chunk {index} must be {expected} bytes", code="BAD_CHUNK")
        if self._s.get(BlobChunk, (row.id, index)) is None:  # re-sent chunk after a network drop: idempotent
            self._s.add(BlobChunk(session_id=row.id, chunk_index=index, tenant_id=self._tid, data=data))
            self._s.flush()
        return self._dto(row)

    def complete(self, session_id: uuid.UUID, store: ObjectStore) -> BlobSessionDto:
        row = self._open(session_id)
        if row.status == "COMPLETE":
            return self._dto(row)
        chunks = list(
            self._s.execute(
                select(BlobChunk).where(BlobChunk.session_id == row.id).order_by(BlobChunk.chunk_index)
            ).scalars()
        )
        total = -(-row.size_bytes // row.chunk_size)
        if [c.chunk_index for c in chunks] != list(range(total)):
            raise Conflict("Upload incomplete", code="UPLOAD_INCOMPLETE")
        data = b"".join(c.data for c in chunks)
        if sha256_hex(data) != row.sha256:
            self._s.execute(delete(BlobChunk).where(BlobChunk.session_id == row.id))
            raise BusinessRuleViolation("Checksum mismatch; upload restarted", code="CHECKSUM_MISMATCH")
        content_type = sniff_image(data)
        key = f"tenants/{self._tid}/evidence/{row.sha256}"
        store.put_immutable(key, data, content_type, row.sha256)
        attachment = CaptureAttachment(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            object_key=key,
            sha256=row.sha256,
            content_type=content_type,
            size_bytes=len(data),
            purpose=row.purpose,
            uploaded_by=self._ctx.user_id,
        )
        self._s.add(attachment)
        self._s.flush()
        row.status, row.attachment_id = "COMPLETE", attachment.id
        self._s.execute(delete(BlobChunk).where(BlobChunk.session_id == row.id))
        self._s.flush()
        return self._dto(row)
