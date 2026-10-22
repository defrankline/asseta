"""Tenant SMS wallet: an append-only credit ledger (never a mutable counter alone). Postings are serialized per tenant
with a transaction-scoped advisory lock and are idempotent per (entry type, reference): a retried fulfilment or SMS
delivery finds its existing entry instead of posting twice."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation
from asseta.modules.platform_billing.enums import SmsWalletEntryType
from asseta.modules.platform_billing.models_catalog import SmsWalletEntry


class InsufficientSmsCredits(BusinessRuleViolation):
    code = "SMS_WALLET_EMPTY"


@dataclass(frozen=True)
class Posting:
    entry: SmsWalletEntry
    created: bool


class SmsWalletService:
    def __init__(self, session: Session):
        self._s = session

    def _lock(self, tenant_id: uuid.UUID) -> None:
        self._s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"smswallet:{tenant_id}"})

    def balance(self, tenant_id: uuid.UUID) -> int:
        return int(
            self._s.execute(
                select(func.coalesce(func.sum(SmsWalletEntry.credits), 0)).where(SmsWalletEntry.tenant_id == tenant_id)
            ).scalar_one()
        )

    def existing(self, entry_type: SmsWalletEntryType, reference_id: uuid.UUID) -> SmsWalletEntry | None:
        return self._s.execute(
            select(SmsWalletEntry).where(
                SmsWalletEntry.entry_type == entry_type, SmsWalletEntry.reference_id == reference_id
            )
        ).scalar_one_or_none()

    def post(
        self,
        tenant_id: uuid.UUID,
        entry_type: SmsWalletEntryType,
        credits: int,
        reference_type: str,
        reference_id: uuid.UUID,
        note: str | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> Posting:
        """Credit (> 0) or debit (< 0). A debit larger than the balance raises InsufficientSmsCredits."""
        if credits == 0:
            raise ValueError("credits must be non-zero")
        self._lock(tenant_id)
        found = self.existing(entry_type, reference_id)
        if found is not None:
            return Posting(found, False)
        after = self.balance(tenant_id) + credits
        if after < 0:
            raise InsufficientSmsCredits("The tenant SMS wallet has insufficient credits", code="SMS_WALLET_EMPTY")
        entry = SmsWalletEntry(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entry_type=entry_type,
            credits=credits,
            balance_after=after,
            reference_type=reference_type,
            reference_id=reference_id,
            note=(note or "")[:300] or None,
            created_by=actor_id,
        )
        self._s.add(entry)
        self._s.flush()
        return Posting(entry, True)

    def debit_unused(
        self, tenant_id: uuid.UUID, wanted: int, reference_type: str, reference_id: uuid.UUID, note: str
    ) -> int:
        """Reverse up to `wanted` credits, limited to what is still unused. Returns the credits actually debited."""
        self._lock(tenant_id)
        found = self.existing(SmsWalletEntryType.BUNDLE_REVERSAL, reference_id)
        if found is not None:
            return -found.credits
        take = min(wanted, self.balance(tenant_id))
        if take <= 0:
            return 0
        self.post(tenant_id, SmsWalletEntryType.BUNDLE_REVERSAL, -take, reference_type, reference_id, note)
        return take
