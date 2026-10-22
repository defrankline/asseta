"""Permission + menu declarations for the platform console and tenant billing views."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires

TENANT_READ = requires("platform.tenant.read", S.PLATFORM, "View tenants")
TENANT_CREATE = requires("platform.tenant.create", S.PLATFORM, "Onboard tenants")
TENANT_UPDATE = requires("platform.tenant.update", S.PLATFORM, "Edit tenant company details")
TENANT_VERIFY = requires("platform.tenant.verify", S.PLATFORM, "Verify tenant company records")
SUB_READ = requires("platform.subscription.read", S.PLATFORM, "View subscriptions, enrollments, rates")
SUB_MANAGE = requires("platform.subscription.manage", S.PLATFORM, "Change subscription lifecycle/entitlements")
PRICING_MANAGE = requires("platform.pricing.manage", S.PLATFORM, "Negotiate tenant rate versions")
ENROLLMENT_MANAGE = requires("platform.enrollment.manage", S.PLATFORM, "End/adjust billable asset enrollments")
INVOICE_READ = requires("platform.invoice.read", S.PLATFORM, "View platform invoices")
INVOICE_GENERATE = requires("platform.invoice.generate", S.PLATFORM, "Generate subscription invoices")
PAYMENT_READ = requires("platform.payment.read", S.PLATFORM, "View platform payments")
PAYMENT_MANAGE = requires("platform.payment.manage", S.PLATFORM, "Record and verify platform payments")
CREDIT_MANAGE = requires("platform.credit.manage", S.PLATFORM, "Apply credits/override pending charges")
INVOICE_RAISE = requires("platform.invoice.raise", S.PLATFORM, "Raise ad-hoc platform invoices with catalog lines")
INVOICE_VOID = requires("platform.invoice.void", S.PLATFORM, "Void platform invoices (reversal)")
CATALOG_READ = requires("platform.catalog.read", S.PLATFORM, "View the platform product catalog")
CATALOG_MANAGE = requires("platform.catalog.manage", S.PLATFORM, "Manage platform products and prices")
SMS_WALLET_READ = requires("platform.sms_wallet.read", S.PLATFORM, "View tenant SMS wallets")
DASHBOARD_READ = requires("platform.dashboard.read", S.PLATFORM, "View platform dashboard")
SYSTEM_READ = requires("platform.system.read", S.PLATFORM, "View system/integration health")

TENANT_BILLING_READ = requires("tenant.billing.read", S.TENANT, "View own subscription and invoices")
TENANT_BILLING_ENROLL = requires("tenant.billing.enroll", S.TENANT, "Enroll/unenroll machines as billable assets")

# (key, label, path, order, permission, side-nav group)
for key, label, path, order, permission, group in (
    ("platform.dashboard", "Dashboard", "/platform", 10, "platform.dashboard.read", "platform.overview"),
    ("platform.system", "System status", "/platform/system", 90, "platform.system.read", "platform.overview"),
    ("platform.tenants", "Tenants", "/platform/tenants", 20, "platform.tenant.read", "platform.tenants"),
    ("platform.invoices", "Invoices", "/platform/invoices", 30, "platform.invoice.read", "platform.billing"),
    ("platform.catalog", "Products", "/platform/catalog", 35, "platform.catalog.read", "platform.billing"),
    ("platform.payments", "Payments", "/platform/payments", 40, "platform.payment.read", "platform.billing"),
    (
        "platform.sms_wallets",
        "SMS wallets",
        "/platform/sms-wallets",
        45,
        "platform.sms_wallet.read",
        "platform.billing",
    ),
    ("tenant.billing", "Subscription", "/tenant/subscription", 90, "tenant.billing.read", "tenant.admin"),
):
    scope = S.PLATFORM if key.startswith("platform.") else S.TENANT
    CATALOG.register_menu(MenuDef(key, scope, label, path, order, permission, group))
