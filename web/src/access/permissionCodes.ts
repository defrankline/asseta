/**
 * Permission codes referenced by console routes and actions. The backend catalog is authoritative;
 * codes here must match codes synced by the API on startup
 * (backend `platform_billing/permissions.py`).
 */
export const PERMISSIONS = {
  /** Platform operators: view API readiness / dependency health. */
  platformSystemRead: 'platform.system.read',
  platformDashboardRead: 'platform.dashboard.read',
  platformTenantRead: 'platform.tenant.read',
  platformTenantCreate: 'platform.tenant.create',
  platformTenantVerify: 'platform.tenant.verify',
  /** Subscription, enrollments, rate versions and pending charges (read). */
  platformSubscriptionRead: 'platform.subscription.read',
  /** Lifecycle transitions and entitlement evaluation. */
  platformSubscriptionManage: 'platform.subscription.manage',
  platformPricingManage: 'platform.pricing.manage',
  platformEnrollmentManage: 'platform.enrollment.manage',
  platformInvoiceRead: 'platform.invoice.read',
  platformInvoiceGenerate: 'platform.invoice.generate',
  platformPaymentRead: 'platform.payment.read',
  platformPaymentManage: 'platform.payment.manage',
  /** Credit adjustments and pending-charge overrides. */
  platformCreditManage: 'platform.credit.manage',
} as const;
