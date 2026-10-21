"""Review/override of computed mid-cycle charges before they are invoiced (audited, never after)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import Conflict, NotFound
from asseta.modules.platform_billing.dto import OverridePendingChargeIn, PendingChargeDto
from asseta.modules.platform_billing.enums import InvoiceLineType, PendingChargeStatus
from asseta.modules.platform_billing.models_ledger import SubscriptionPendingCharge


class PendingChargeService:
    def __init__(self, session: Session, actor: AuditActor):
        self._s = session
        self._actor = actor

    def override(self, pending_id: uuid.UUID, body: OverridePendingChargeIn) -> PendingChargeDto:
        charge = self._s.execute(
            select(SubscriptionPendingCharge).where(SubscriptionPendingCharge.id == pending_id).with_for_update()
        ).scalar_one_or_none()
        if charge is None:
            raise NotFound("Pending charge not found")
        if charge.status is PendingChargeStatus.INVOICED:
            raise Conflict("Charge already invoiced; use a credit adjustment", code="CHARGE_INVOICED")
        is_credit = charge.line_type is InvoiceLineType.PRORATION_CREDIT
        if (is_credit and body.amount > 0) or (not is_credit and body.amount < 0):
            raise Conflict("Override must keep the charge/credit sign", code="SIGN_MISMATCH")
        before = {"amount": str(charge.amount), "status": charge.status.value}
        charge.amount, charge.override_reason = body.amount, body.reason
        charge.status = PendingChargeStatus.PENDING if body.amount != 0 else PendingChargeStatus.WAIVED
        AuditService(self._s).record(
            actor=self._actor,
            action="platform.pending_charge.overridden",
            entity_type="pending_charge",
            entity_id=charge.id,
            tenant_id=charge.tenant_id,
            before=before,
            after={"amount": str(body.amount), "status": charge.status.value},
            reason=body.reason,
        )
        self._s.flush()
        return PendingChargeDto.model_validate(charge)
