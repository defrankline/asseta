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
  /** Edit tenant company details. */
  platformTenantUpdate: 'platform.tenant.update',
  /** Approved tracker driver/model catalog: view; create, edit, withdraw / restore. */
  platformTrackerModelRead: 'platform.tracker_model.read',
  platformTrackerModelManage: 'platform.tracker_model.manage',
  /** Telemetry gateways: view (never their keys); create, deactivate / reactivate. */
  platformGatewayRead: 'platform.gateway.read',
  platformGatewayManage: 'platform.gateway.manage',
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
  /** Managed-service mandates (DEC-018): view; grant, staff and end. */
  platformMandateRead: 'platform.mandate.read',
  platformMandateManage: 'platform.mandate.manage',
  /** DEC-022: product catalog, ad-hoc invoices (raise / void), tenant SMS wallets. */
  platformCatalogRead: 'platform.catalog.read',
  platformCatalogManage: 'platform.catalog.manage',
  platformInvoiceRaise: 'platform.invoice.raise',
  platformInvoiceVoid: 'platform.invoice.void',
  platformSmsWalletRead: 'platform.sms_wallet.read',
  /** Own platform inbox and preferences; SMS delivery log and test-send. */
  platformNotificationRead: 'platform.notification.read',
  platformNotificationManage: 'platform.notification.manage',
  /** Governed ML (ADR-007): view model versions, evaluations, readiness, drift and settings. */
  platformMlRead: 'platform.ml.read',
  /** Approve, deploy, roll back and disable models; the inference switch; run snapshots/training. */
  platformMlManage: 'platform.ml.manage',
  /** Platform and billing audit trail (who changed what, when). */
  platformAuditRead: 'platform.audit.read',

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
  /** Customers and contracts (read); write also covers rate-card versions. */
  tenantCustomerRead: 'tenant.customer.read',
  tenantCustomerWrite: 'tenant.customer.write',
  /** Jobs, work logs and job summaries (read). */
  tenantJobRead: 'tenant.job.read',
  /** Create jobs and SUBMIT them for approval. */
  tenantJobWrite: 'tenant.job.write',
  /** APPROVE and CANCEL jobs. */
  tenantJobApprove: 'tenant.job.approve',
  /** START / COMPLETE jobs, work logs and customer acknowledgements. */
  tenantJobLog: 'tenant.job.log',
  /** Meter readings, evidence and exceptions (read). */
  tenantMeterRead: 'tenant.meter.read',
  /** Capture readings, upload evidence and request meter resets. */
  tenantMeterCapture: 'tenant.meter.capture',
  /** Review meter/GPS exceptions. */
  tenantMeterReview: 'tenant.meter.review',
  /** Decide meter resets and reading corrections. */
  tenantMeterApprove: 'tenant.meter.approve',
  /** Users & roles (Keycloak group membership): view; invite and grant/revoke roles. */
  tenantAccessRead: 'tenant.access.read',
  tenantAccessManage: 'tenant.access.manage',
  /** The managed-service mandate held over this tenant: view; revoke. */
  tenantManagedServiceRead: 'tenant.managed_service.read',
  tenantManagedServiceRevoke: 'tenant.managed_service.revoke',
  /** Expenses, receipts, categories and fuel events (read). */
  tenantExpenseRead: 'tenant.expense.read',
  /** Create, edit, deactivate and reactivate expense categories. */
  tenantExpenseCategoryManage: 'tenant.finance.expense_category',
  /** Record expenses (receipts/GPS) and fuel events. */
  tenantExpenseWrite: 'tenant.expense.write',
  /** Approval requests (read); approve / reject expenses above policy limits. */
  tenantApprovalRead: 'tenant.approval.read',
  tenantApprovalExpense: 'tenant.approval.expense',
  /** Hire invoices, customer payments, balances, statements and cash custody (read). */
  tenantFinanceRead: 'tenant.finance.read',
  /** Draft, issue and void customer hire invoices. */
  tenantFinanceInvoice: 'tenant.finance.invoice',
  /** Record customer payments and allocate them to invoices. */
  tenantFinancePayment: 'tenant.finance.payment',
  /** Verify or reject customer payments and cash handovers (never your own). */
  tenantFinanceVerify: 'tenant.finance.verify',
  /** Issue cash floats and record custody for any supervisor. */
  tenantFinanceCash: 'tenant.finance.cash',
  /** Machine / job / customer profitability. */
  tenantFinanceReport: 'tenant.finance.report',
  /** Own tenant inbox and preferences; tenant-wide defaults and the SMS delivery log. */
  tenantNotificationRead: 'tenant.notification.read',
  tenantNotificationManage: 'tenant.notification.manage',
  /** Record cash collections and handovers (own custody). */
  tenantCollectionRecord: 'tenant.collection.record',
  /** Colleagues' display names on records (recorded / decided / requested by). */
  tenantDirectoryRead: 'tenant.directory.read',
  /** Investigation cases with linked evidence, notes and outcomes (read). */
  tenantCaseRead: 'tenant.case.read',
  /** Assign, annotate and reopen investigation cases. */
  tenantCaseManage: 'tenant.case.manage',
  /** Resolve investigation cases with a recorded outcome (never a case built on your own records). */
  tenantCaseResolve: 'tenant.case.resolve',
  /** Deterministic risk signals and their evidence (read). */
  tenantSignalRead: 'tenant.signal.read',
  /** The tenant's audit log (who changed what, when). */
  tenantAuditRead: 'tenant.audit.read',
} as const;
