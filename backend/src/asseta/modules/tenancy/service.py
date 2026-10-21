"""Platform-owner tenant onboarding: company record, settings, Keycloak tenant role groups + initial owner,
negotiated agreement, first rate version and subscription (PENDING_ACTIVATION)."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.identity.idp import IdentityProviderAdmin
from asseta.modules.platform_billing.enums import AgreementStatus, SubscriptionStatus
from asseta.modules.platform_billing.models_commercial import (
    CommercialAgreement,
    SubscriptionRateVersion,
    SubscriptionStatusEvent,
    TenantSubscription,
)
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.platform_billing.subscription_service import default_billing_start
from asseta.modules.tenancy.dto import OnboardResultDto, TenantDto, TenantOnboardIn, VerificationIn
from asseta.modules.tenancy.models import (
    Tenant,
    TenantAccessState,
    TenantSettings,
    TenantStatus,
    VerificationStatus,
)

OWNER_ROLE_KEY = "owner"


class TenantOnboardingService:
    def __init__(self, session: Session, actor: AuditActor, idp: IdentityProviderAdmin):
        self._s = session
        self._actor = actor
        self._idp = idp
        self._audit = AuditService(session)
        self._repo = BillingRepository(session)

    def onboard(self, body: TenantOnboardIn) -> OnboardResultDto:
        self._repo.currency(body.currency)
        self._repo.currency(body.subscription.rate.currency)
        if (
            body.registration_number
            and self._s.execute(select(Tenant.id).where(Tenant.registration_number == body.registration_number)).first()
        ):
            raise Conflict("A tenant with this registration number exists", code="TENANT_EXISTS")
        tenant_id = uuid.uuid4()
        tenant = Tenant(
            id=tenant_id,
            legal_name=body.legal_name,
            display_name=body.display_name,
            registration_number=body.registration_number,
            verification_status=VerificationStatus.UNVERIFIED,
            contact_name=body.contact_name,
            contact_email=str(body.contact_email),
            contact_phone=body.contact_phone,
            status=TenantStatus.ONBOARDING,
            access_state=TenantAccessState.FULL,
            access_state_reason="Onboarding",
        )
        self._s.add(tenant)
        self._s.add(
            TenantSettings(tenant_id=tenant_id, timezone=body.timezone, currency=body.currency, locale=body.locale)
        )
        try:
            self._s.flush()
        except IntegrityError as exc:
            raise Conflict("Tenant could not be created (duplicate)", code="TENANT_EXISTS") from exc

        setup = body.subscription
        agreement = CommercialAgreement(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            status=AgreementStatus.DRAFT,
            agreement_number=f"AGR-{self._repo.next_number('commercial_agreement_number_seq'):06d}",
            signed_reference=setup.signed_reference,
            payment_terms_days=setup.payment_terms_days,
            trial_days=setup.trial_days,
        )
        self._s.add(agreement)
        self._s.flush()
        billing_start = default_billing_start(setup.start_date, setup.trial_days)
        self._s.add(
            SubscriptionRateVersion(
                id=uuid.uuid4(),
                agreement_id=agreement.id,
                tenant_id=tenant_id,
                version=1,
                effective_from=billing_start,
                reason="Initial negotiated rate",
                created_by=self._actor.user_id,
                **setup.rate.model_dump(),
            )
        )
        sub = TenantSubscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            agreement_id=agreement.id,
            status=SubscriptionStatus.PENDING_ACTIVATION,
            start_date=setup.start_date,
            billing_start_date=billing_start,
            billing_anchor_day=billing_start.day,
        )
        self._s.add(sub)
        self._s.flush()
        self._s.add(
            SubscriptionStatusEvent(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                tenant_id=tenant_id,
                from_status=None,
                to_status=SubscriptionStatus.PENDING_ACTIVATION.value,
                effective_date=setup.start_date,
                reason="Tenant onboarded",
                actor_user_id=self._actor.user_id,
            )
        )

        # Identity last: if Keycloak fails the DB transaction rolls back; group creation is idempotent.
        sync = AuthzSyncService(self._idp)
        groups = sync.provision_tenant_roles(tenant_id, self._s)
        owner = self._idp.create_user(str(body.owner.email), body.owner.first_name, body.owner.last_name)
        self._idp.add_user_to_group(owner.subject, groups[OWNER_ROLE_KEY])
        sync.pull_role_mirror(self._s)

        dto = TenantDto.model_validate(tenant)
        self._audit.record(
            actor=self._actor,
            action="platform.tenant.onboarded",
            entity_type="tenant",
            entity_id=tenant_id,
            tenant_id=tenant_id,
            after={**dto.model_dump(mode="json"), "subscription_id": str(sub.id), "owner_email": str(body.owner.email)},
        )
        OutboxWriter(self._s).emit(
            topic="asseta.platform.tenant",
            event_type="TenantOnboarded",
            key=str(tenant_id),
            payload={"tenant_id": str(tenant_id), "subscription_id": str(sub.id)},
            tenant_id=tenant_id,
        )
        return OnboardResultDto(
            tenant=dto,
            subscription_id=sub.id,
            owner_email=str(body.owner.email),
            owner_temporary_password=owner.temporary_password,
        )

    def verify(self, tenant_id: uuid.UUID, body: VerificationIn) -> TenantDto:
        tenant = self._s.get(Tenant, tenant_id, with_for_update=True)
        if tenant is None:
            raise NotFound("Tenant not found")
        before = tenant.verification_status.value
        tenant.verification_status, tenant.verification_note = body.status, body.note
        self._audit.record(
            actor=self._actor,
            action="platform.tenant.verification",
            entity_type="tenant",
            entity_id=tenant_id,
            tenant_id=tenant_id,
            before={"verification_status": before},
            after={"verification_status": body.status.value},
            reason=body.note,
        )
        self._s.flush()
        return TenantDto.model_validate(tenant)
