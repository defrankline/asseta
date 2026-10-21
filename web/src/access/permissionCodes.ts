/**
 * Permission codes referenced by console routes and actions. The backend catalog is authoritative;
 * codes here must match codes synced by the API on startup
 * (backend `platform_billing/permissions.py` and the tenant module routers).
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

  // ---- Tenant console (only granted in tenant mode, for the active tenant) ----
  /** Fleet map, positions, history and alerts (read). */
  tenantFleetRead: 'tenant.fleet.read',
  /** Acknowledge / resolve tracking alerts. */
  tenantAlertManage: 'tenant.fleet.alert_manage',
  /** Machines, categories, operating areas. */
  tenantMachineRead: 'tenant.machine.read',
  tenantMachineWrite: 'tenant.machine.write',
  /** Supervisors/operators and machine staff assignments. */
  tenantStaffRead: 'tenant.staff.read',
  tenantStaffWrite: 'tenant.staff.write',
  /** Trackers, capabilities, assignments and ingestion events. */
  tenantTrackerRead: 'tenant.tracker.read',
  tenantTrackerWrite: 'tenant.tracker.write',
  /** Job sites and geofences. */
  tenantGeofenceRead: 'tenant.geofence.read',
  tenantGeofenceWrite: 'tenant.geofence.write',
  tenantPolicyRead: 'tenant.policy.read',
  tenantPolicyManage: 'tenant.policy.manage',
  /** Own subscription and platform invoices (read-only). */
  tenantBillingRead: 'tenant.billing.read',
  /** Enroll a machine as a billable asset (proration preview first). */
  tenantBillingEnroll: 'tenant.billing.enroll',
} as const;
