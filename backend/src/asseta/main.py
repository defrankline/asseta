"""API application factory. Routers are thin; modules own services, repositories and DTOs."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from asseta.api import health
from asseta.core.config import Settings, get_settings
from asseta.core.correlation import CorrelationIdMiddleware
from asseta.core.db import get_sessionmaker
from asseta.core.errors import install_error_handlers
from asseta.core.logging import configure_logging
from asseta.core.request_limits import RequestSizeLimitMiddleware
from asseta.core.sms import SmsClient, build_sms_client
from asseta.core.storage import ObjectStore, S3ObjectStore
from asseta.modules.accountability import router as accountability_router
from asseta.modules.audit_log import router as audit_log_router
from asseta.modules.expenses import router as expenses_router
from asseta.modules.finance import cash_router as finance_cash_router
from asseta.modules.finance import custody_router as finance_custody_router
from asseta.modules.finance import deposit_accounts as finance_deposit_accounts
from asseta.modules.finance import router as finance_router
from asseta.modules.fleet import photos as fleet_photos
from asseta.modules.fleet import router as fleet_router
from asseta.modules.geospatial import router as geospatial_router
from asseta.modules.hours import router as hours_router
from asseta.modules.identity import access as identity_access
from asseta.modules.identity import directory as identity_directory
from asseta.modules.identity import router as identity_router
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.identity.idp import IdentityProviderAdmin
from asseta.modules.identity.keycloak_admin import KeycloakAdminClient
from asseta.modules.identity.tokens import JwksSigningKeyProvider, OidcTokenVerifier, TokenVerifier
from asseta.modules.intelligence import insights_router as intelligence_insights_router
from asseta.modules.intelligence import ml_monitoring_router as intelligence_ml_monitoring_router
from asseta.modules.intelligence import ml_router as intelligence_ml_router
from asseta.modules.intelligence import router as intelligence_router
from asseta.modules.jobs import router as jobs_router
from asseta.modules.managed_service import router as managed_service_router
from asseta.modules.meter import engine_router as meter_engine_router
from asseta.modules.meter import router as meter_router
from asseta.modules.notification import channels_router as notification_channels_router
from asseta.modules.notification import gateway as notification_gateway
from asseta.modules.notification import router as notification_router
from asseta.modules.notification.realtime import RealtimeBroker, RedisBroker
from asseta.modules.overview import router as overview_router
from asseta.modules.platform_billing import commerce_router
from asseta.modules.platform_billing import router as platform_router
from asseta.modules.platform_billing import tenant_router as tenant_billing_router
from asseta.modules.policy import router as policy_router
from asseta.modules.reports import router as reports_router
from asseta.modules.revenue import router as revenue_router
from asseta.modules.sync import router as sync_router
from asseta.modules.telemetry import router as telemetry_router
from asseta.modules.tenancy import router as tenancy_router
from asseta.modules.tracker import router as tracker_router


def build_keycloak_admin(settings: Settings) -> IdentityProviderAdmin:
    return KeycloakAdminClient(
        settings.keycloak_url,
        settings.keycloak_realm,
        settings.keycloak_api_client_id,
        settings.keycloak_api_client_secret.get_secret_value(),
        settings.http_timeout_seconds,
    )


def build_token_verifier(settings: Settings) -> TokenVerifier:
    keys = JwksSigningKeyProvider(settings.jwks_url, settings.jwks_cache_seconds, settings.http_timeout_seconds)
    return OidcTokenVerifier(keys, settings.issuer, settings.keycloak_audience)


def build_object_store(settings: Settings) -> S3ObjectStore:
    return S3ObjectStore(
        settings.s3_endpoint,
        settings.s3_public_endpoint,
        settings.s3_bucket,
        settings.s3_access_key.get_secret_value(),
        settings.s3_secret_key.get_secret_value(),
        settings.http_timeout_seconds,
    )


def create_app(
    settings: Settings | None = None,
    token_verifier: TokenVerifier | None = None,
    idp_admin: IdentityProviderAdmin | None = None,
    object_store: ObjectStore | None = None,
    realtime: RealtimeBroker | None = None,
    sms_client: SmsClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()
    verifier = token_verifier or build_token_verifier(settings)
    idp = idp_admin or build_keycloak_admin(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.keycloak_sync_on_startup:
            with get_sessionmaker().begin() as session:
                AuthzSyncService(idp).full_sync(session)
        structlog.get_logger().info("api_started", environment=settings.environment)
        yield

    app = FastAPI(
        title="Asseta API",
        version="1.0.0",
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
    )
    app.state.token_verifier = verifier
    app.state.idp_admin = idp
    app.state.object_store = object_store or build_object_store(settings)
    app.state.realtime = realtime or RedisBroker(settings.redis_url)  # WebSocket fan-out across API instances
    app.state.sms_client = sms_client or build_sms_client()  # console provider unless ASSETA_SMS_PROVIDER=nextsms
    # Innermost of the three: the 413 still carries CORS headers and the request's correlation id.
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-correlation-id"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(app)
    for router in (
        health.router,
        identity_router.router,
        tenancy_router.router,
        platform_router.router,
        tenant_billing_router.router,
        fleet_router.router,
        policy_router.router,
        tracker_router.router,
        telemetry_router.router,
        geospatial_router.router,
        fleet_photos.router,
        identity_access.router,
        identity_directory.router,
        jobs_router.router,
        meter_router.router,
        meter_engine_router.router,
        revenue_router.router,
        sync_router.router,
        managed_service_router.router,
        finance_router.router,
        finance_cash_router.router,
        finance_custody_router.router,
        finance_deposit_accounts.router,
        accountability_router.router,
        hours_router.router,
        expenses_router.router,
        intelligence_router.router,
        intelligence_ml_router.platform_router,
        intelligence_ml_router.tenant_router,
        intelligence_ml_monitoring_router.router,
        intelligence_insights_router.router,
        commerce_router.router,
        commerce_router.tenant_router,
        notification_router.tenant_router,
        notification_router.platform_router,
        notification_gateway.router,
        notification_channels_router.me_router,
        notification_channels_router.tenant_router,
        notification_channels_router.platform_router,
        overview_router.router,
        reports_router.tenant_router,
        reports_router.platform_router,
        audit_log_router.tenant_router,
        audit_log_router.platform_router,
    ):
        app.include_router(router)
    return app


def run() -> None:
    import uvicorn

    uvicorn.run("asseta.main:create_app", factory=True, host="0.0.0.0", port=8000)  # noqa: S104
