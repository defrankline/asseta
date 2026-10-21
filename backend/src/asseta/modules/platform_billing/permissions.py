"""Permission + menu declarations for the platform console and tenant billing views."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires

TENANT_READ = requires("platform.tenant.read", S.PLATFORM, "View tenants")
TENANT_CREATE = requires("platform.tenant.create", S.PLATFORM, "Onboard tenants")
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
DASHBOARD_READ = requires("platform.dashboard.read", S.PLATFORM, "View platform dashboard")
SYSTEM_READ = requires("platform.system.read", S.PLATFORM, "View system/integration health")

TENANT_BILLING_READ = requires("tenant.billing.read", S.TENANT, "View own subscription and invoices")
TENANT_BILLING_ENROLL = requires("tenant.billing.enroll", S.TENANT, "Enroll/unenroll machines as billable assets")

for menu in (
    MenuDef("platform.dashboard", S.PLATFORM, "Dashboard", "/platform", 10, "platform.dashboard.read"),
    MenuDef("platform.tenants", S.PLATFORM, "Tenants", "/platform/tenants", 20, "platform.tenant.read"),
    MenuDef("platform.invoices", S.PLATFORM, "Invoices", "/platform/invoices", 30, "platform.invoice.read"),
    MenuDef("platform.payments", S.PLATFORM, "Payments", "/platform/payments", 40, "platform.payment.read"),
    MenuDef("platform.system", S.PLATFORM, "System status", "/platform/system", 90, "platform.system.read"),
    MenuDef("tenant.billing", S.TENANT, "Subscription", "/tenant/subscription", 90, "tenant.billing.read"),
):
    CATALOG.register_menu(menu)
