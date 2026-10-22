"""Platform product catalog (DEC-022) with the full DEC-021 lifecycle: list/search, details, create, edit (optimistic
version), deactivate/reactivate with a reason. Products are never deleted; invoice lines snapshot their terms."""

import uuid
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.search import ilike_any
from asseta.modules.platform_billing.dto_commerce import ProductDto, ProductFieldsIn, ProductIn, ProductUpdateIn
from asseta.modules.platform_billing.enums import ProductType
from asseta.modules.platform_billing.models_catalog import PlatformProduct
from asseta.modules.platform_billing.repository import BillingRepository

LABEL = "Product"


def product_query(q: str | None, include_inactive: bool, product_type: ProductType | None) -> Select[PlatformProduct]:
    stmt = select(PlatformProduct).order_by(PlatformProduct.code)
    if (cond := ilike_any(q, PlatformProduct.code, PlatformProduct.name)) is not None:
        stmt = stmt.where(cond)
    if not include_inactive:
        stmt = stmt.where(PlatformProduct.is_active.is_(True))
    if product_type is not None:
        stmt = stmt.where(PlatformProduct.product_type == product_type)
    return stmt


def product_dto(p: PlatformProduct) -> ProductDto:
    dto = ProductDto.model_validate(p)
    dto.prices = {k: Decimal(v) for k, v in sorted(p.prices.items())}
    return dto


class CatalogService:
    def __init__(self, session: Session, actor: AuditActor):
        self._s, self._actor = session, actor
        self._audit = AuditService(session)

    def get(self, product_id: uuid.UUID, lock: bool = False) -> PlatformProduct:
        stmt = select(PlatformProduct).where(PlatformProduct.id == product_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Product not found")
        return row

    def _validate(self, product_type: ProductType, body: ProductFieldsIn) -> dict[str, str]:
        if product_type is ProductType.SMS_BUNDLE and not body.sms_credits:
            raise BusinessRuleViolation("SMS bundles need sms_credits per unit", code="SMS_CREDITS_REQUIRED")
        if product_type is not ProductType.SMS_BUNDLE and body.sms_credits is not None:
            raise BusinessRuleViolation("Only SMS bundles carry sms_credits", code="SMS_CREDITS_NOT_ALLOWED")
        if product_type is ProductType.SUBSCRIPTION_FEE and body.prices:
            raise BusinessRuleViolation(
                "Subscription fees are priced by the tenant's negotiated rate, not a list price",
                code="SUBSCRIPTION_PRICE_FROM_RATE",
            )
        repo = BillingRepository(self._s)
        for code in body.prices:
            repo.currency(code)
        return {k: format(v, "f") for k, v in body.prices.items()}

    def create(self, body: ProductIn) -> ProductDto:
        prices = self._validate(body.product_type, body)
        row = PlatformProduct(
            id=uuid.uuid4(),
            code=body.code,
            name=body.name,
            description=body.description,
            product_type=body.product_type,
            sms_credits=body.sms_credits,
            prices=prices,
            taxable=body.taxable and body.product_type is not ProductType.SUBSCRIPTION_FEE,
            is_active=True,
            created_by=self._actor.user_id,
        )
        self._s.add(row)
        flush_versioned(self._s, LABEL, "DUPLICATE_PRODUCT_CODE", "A product with this code already exists")
        dto = product_dto(row)
        self._record("platform.product.created", row, None, dto.model_dump(mode="json"))
        return dto

    def update(self, product_id: uuid.UUID, body: ProductUpdateIn) -> ProductDto:
        row = self.get(product_id, lock=True)
        check_version(row.version, body.version, LABEL)
        prices = self._validate(row.product_type, body)
        before = product_dto(row).model_dump(mode="json")
        row.name, row.description, row.sms_credits, row.prices = body.name, body.description, body.sms_credits, prices
        row.taxable = body.taxable and row.product_type is not ProductType.SUBSCRIPTION_FEE
        flush_versioned(self._s, LABEL)
        dto = product_dto(row)
        self._record("platform.product.updated", row, before, dto.model_dump(mode="json"))
        return dto

    def set_active(self, product_id: uuid.UUID, active: bool, reason: str, version: int | None) -> ProductDto:
        row = self.get(product_id, lock=True)
        check_version(row.version, version, LABEL)
        if active:
            mark_active(row, LABEL)
        else:
            mark_inactive(row, self._actor.user_id, reason, LABEL)
        flush_versioned(self._s, LABEL)
        action = "reactivated" if active else "deactivated"
        self._record(f"platform.product.{action}", row, None, {"is_active": active}, reason)
        return product_dto(row)

    def _record(
        self,
        action: str,
        row: PlatformProduct,
        before: dict[str, object] | None,
        after: dict[str, object],
        reason: str | None = None,
    ) -> None:
        self._audit.record(
            actor=self._actor,
            action=action,
            entity_type="platform_product",
            entity_id=row.id,
            tenant_id=None,
            before=before,
            after=after,
            reason=reason,
        )
