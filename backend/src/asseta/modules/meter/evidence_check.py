"""Shared evidence checks: the evidence attachments a request names must exist in the tenant (RLS scoped), and a type
whose policy requires evidence needs at least one. Every flow that carries supporting evidence uses this."""

import uuid

from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.modules.meter.models import CaptureAttachment


def check_attachments(session: Session, ids: list[uuid.UUID]) -> None:
    for attachment_id in ids:
        if session.get(CaptureAttachment, attachment_id) is None:
            raise NotFound("Evidence attachment not found", code="ATTACHMENT_NOT_FOUND")


def require_evidence(session: Session, required: bool, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """The evidence ids, validated and deduplicated; refused when the policy requires one and there is none."""
    unique = list(dict.fromkeys(ids))
    if required and not unique:
        raise BusinessRuleViolation("Attach the supporting evidence", code="EVIDENCE_REQUIRED")
    check_attachments(session, unique)
    return unique
