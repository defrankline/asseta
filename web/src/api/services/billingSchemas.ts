/**
 * Runtime (Yup) response schemas for the platform billing / tenancy endpoints. Each schema is
 * annotated with its generated contract type, so contract drift fails `npm run typecheck`.
 */
import { array, boolean, mixed, number, object, string, type Schema } from 'yup';
import type {
  ChargePreviewDto,
  CurrencyTotalsDto,
  EnrollmentDto,
  EnrollmentEndReason,
  EnrollmentResultDto,
  EntitlementDto,
  FulfilmentStatus,
  GenerateInvoicesDto,
  InvoiceKind,
  InvoiceDto,
  InvoiceLineDto,
  InvoiceLineType,
  InvoiceStatus,
  OnboardResultDto,
  Page,
  PaymentAllocationDto,
  PaymentDto,
  PaymentMethod,
  PaymentStatus,
  PendingChargeDto,
  PendingChargeStatus,
  PlatformDashboardDto,
  RateVersionDto,
  SubscriptionDto,
  SubscriptionStatus,
  TenantAccessState,
  TenantDto,
  TenantStatus,
  VerificationStatus,
} from '../types';

export const SUBSCRIPTION_STATUSES: readonly SubscriptionStatus[] = [
  'DRAFT',
  'PENDING_ACTIVATION',
  'ACTIVE',
  'PAST_DUE',
  'SUSPENDED',
  'CANCELLED',
  'EXPIRED',
];
export const INVOICE_STATUSES: readonly InvoiceStatus[] = [
  'ISSUED',
  'PARTIALLY_PAID',
  'PAID',
  'VOIDED',
];
export const INVOICE_KINDS: readonly InvoiceKind[] = ['SUBSCRIPTION', 'AD_HOC'];
export const FULFILMENT_STATUSES: readonly FulfilmentStatus[] = [
  'FULFILLED',
  'REVERSED',
  'REVERSAL_FLAGGED',
];
export const PAYMENT_METHODS: readonly PaymentMethod[] = ['CASH', 'BANK_TRANSFER', 'MOBILE_MONEY'];
export const PAYMENT_STATUSES: readonly PaymentStatus[] = ['RECORDED', 'VERIFIED', 'REJECTED'];
export const ENROLLMENT_END_REASONS: readonly EnrollmentEndReason[] = [
  'REMOVED_FROM_FLEET',
  'DISPOSED',
  'SUBSCRIPTION_ENDED',
  'CORRECTION',
];
const LINE_TYPES: readonly InvoiceLineType[] = [
  'ASSET_SUBSCRIPTION',
  'MINIMUM_COMMITMENT',
  'PRORATION_CHARGE',
  'PRORATION_CREDIT',
  'DISCOUNT',
  'TAX',
  'SUBSCRIPTION_FEE',
  'SMS_BUNDLE',
  'SERVICE',
];
const PENDING_STATUSES: readonly PendingChargeStatus[] = ['PENDING', 'INVOICED', 'WAIVED'];
const TENANT_STATUSES: readonly TenantStatus[] = ['ONBOARDING', 'ACTIVE', 'CLOSED'];
const ACCESS_STATES: readonly TenantAccessState[] = ['FULL', 'READ_ONLY', 'BLOCKED'];
const VERIFICATION_STATUSES: readonly VerificationStatus[] = ['UNVERIFIED', 'VERIFIED', 'REJECTED'];

const text = () => string().defined();
const nullableText = () => string().nullable().defined();
const int = () => number().integer().required();
const oneOf = <T extends string>(values: readonly T[]) => mixed<T>().oneOf(values).required();

function isCountMap(value: unknown): value is Record<string, number> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === 'number')
  );
}
const countMap = () => mixed<Record<string, number>>(isCountMap).required();

export const tenantSchema: Schema<TenantDto> = object({
  id: string().required(),
  legal_name: text(),
  display_name: text(),
  registration_number: nullableText(),
  contact_name: text(),
  contact_email: text(),
  contact_phone: nullableText(),
  status: oneOf(TENANT_STATUSES),
  access_state: oneOf(ACCESS_STATES),
  access_state_reason: nullableText(),
  verification_status: oneOf(VERIFICATION_STATUSES),
  created_at: string().required(),
  version: int(),
});

export const onboardResultSchema: Schema<OnboardResultDto> = object({
  tenant: tenantSchema,
  subscription_id: string().required(),
  owner_email: text(),
  owner_temporary_password: text(),
});

const rateFields = {
  id: string().required(),
  version: int(),
  currency: text(),
  cadence: oneOf(['MONTHLY', 'YEARLY'] as const),
  unit_price: text(),
  minimum_billable_assets: int(),
  discount_percent: text(),
  tax_name: nullableText(),
  tax_rate_percent: text(),
  mid_cycle_add: oneOf(['PRORATE_DAILY', 'FULL_PERIOD', 'NEXT_PERIOD'] as const),
  mid_cycle_remove: oneOf(['PRORATE_CREDIT', 'NO_CREDIT'] as const),
  rounding_mode: oneOf(['HALF_UP', 'HALF_EVEN'] as const),
  effective_from: string().required(),
  reason: text(),
  created_at: string().required(),
};
export const rateVersionSchema: Schema<RateVersionDto> = object(rateFields);

export const subscriptionSchema: Schema<SubscriptionDto> = object({
  id: string().required(),
  tenant_id: string().required(),
  agreement_id: string().required(),
  agreement_number: text(),
  status: oneOf(SUBSCRIPTION_STATUSES),
  start_date: string().required(),
  billing_start_date: string().required(),
  billing_anchor_day: int(),
  payment_terms_days: int(),
  current_period_start: nullableText(),
  current_period_end: nullableText(),
  cancellation_effective_date: nullableText(),
  manually_suspended: boolean().required(),
  enrolled_assets: int(),
  billable_assets: int(),
  current_rate: object(rateFields).nullable().defined().default(null),
});

export const entitlementSchema: Schema<EntitlementDto> = object({
  tenant_id: string().required(),
  subscription_status: oneOf(SUBSCRIPTION_STATUSES),
  access_state: text(),
  reason: text(),
  policy_version: int(),
  changed: boolean().required(),
});

const enrollmentFields = {
  id: string().required(),
  machine_id: string().required(),
  asset_label: text(),
  effective_from: string().required(),
  effective_to: nullableText(),
  end_reason: mixed<EnrollmentEndReason>().oneOf(ENROLLMENT_END_REASONS).nullable().defined(),
};
export const enrollmentSchema: Schema<EnrollmentDto> = object(enrollmentFields);

const chargePreviewFields = {
  line_type: oneOf(LINE_TYPES),
  amount: text(),
  currency: text(),
  days: int(),
  period_days: int(),
  service_from: nullableText(),
  service_to: nullableText(),
  explanation: text(),
};
export const chargePreviewSchema: Schema<ChargePreviewDto> = object(chargePreviewFields);

export const enrollmentResultSchema: Schema<EnrollmentResultDto> = object({
  enrollment: object(enrollmentFields).required(),
  charge: object(chargePreviewFields).nullable().defined().default(null),
});

export const pendingChargeSchema: Schema<PendingChargeDto> = object({
  id: string().required(),
  enrollment_id: string().required(),
  line_type: oneOf(LINE_TYPES),
  amount: text(),
  computed_amount: text(),
  days: int(),
  period_days: int(),
  service_from: string().required(),
  service_to: string().required(),
  explanation: text(),
  status: oneOf(PENDING_STATUSES),
  override_reason: nullableText(),
});

export const invoiceLineSchema: Schema<InvoiceLineDto> = object({
  line_no: int(),
  line_type: oneOf(LINE_TYPES),
  description: text(),
  machine_id: nullableText(),
  quantity: text(),
  unit_price: text(),
  amount: text(),
  service_from: nullableText(),
  service_to: nullableText(),
  id: string().nullable().optional(),
  product_id: string().nullable().optional(),
  sms_credits: number().integer().nullable().optional(),
  payable: string().nullable().optional(),
  paid: string().nullable().optional(),
  fulfilment_status: mixed<FulfilmentStatus>().oneOf(FULFILMENT_STATUSES).nullable().optional(),
});

export const invoiceSchema: Schema<InvoiceDto> = object({
  id: nullableText(),
  invoice_number: nullableText(),
  tenant_id: string().required(),
  status: mixed<InvoiceStatus>().oneOf(INVOICE_STATUSES).nullable().defined(),
  period_start: string().required(),
  period_end: string().required(),
  due_date: string().required(),
  issued_at: nullableText(),
  currency: text(),
  enrolled_assets: int(),
  billable_assets: int(),
  subtotal: text(),
  discount_total: text(),
  tax_total: text(),
  total: text(),
  amount_paid: text(),
  credits_applied: text(),
  balance: text(),
  lines: array(invoiceLineSchema).required(),
  kind: oneOf(INVOICE_KINDS),
  notes: string().nullable().optional(),
  voided_at: string().nullable().optional(),
  void_reason: string().nullable().optional(),
});

export const generateInvoicesSchema: Schema<GenerateInvoicesDto> = object({
  created: array(invoiceSchema).required(),
  existing_periods: array(string().required()).required(),
});

export const paymentAllocationSchema: Schema<PaymentAllocationDto> = object({
  id: string().required(),
  invoice_id: string().required(),
  line_id: nullableText(),
  amount: text(),
  created_at: string().required(),
  released_at: nullableText(),
  release_reason: nullableText(),
});

export const paymentSchema: Schema<PaymentDto> = object({
  id: string().required(),
  invoice_id: nullableText(),
  allocations: array(paymentAllocationSchema).required(),
  unallocated: string().nullable().optional(),
  tenant_id: string().required(),
  amount: text(),
  currency: text(),
  method: oneOf(PAYMENT_METHODS),
  reference: text(),
  received_on: string().required(),
  status: oneOf(PAYMENT_STATUSES),
  recorded_at: string().required(),
  decided_at: nullableText(),
  decision_note: nullableText(),
});

const currencyTotalsSchema: Schema<CurrencyTotalsDto> = object({
  currency: text(),
  contracted_mrr: text(),
  contracted_arr: text(),
  billable_assets: int(),
  enrolled_assets: int(),
  outstanding_balance: text(),
  open_invoices: int(),
});

export const dashboardSchema: Schema<PlatformDashboardDto> = object({
  as_of: string().required(),
  tenants_by_status: countMap(),
  tenants_by_access: countMap(),
  subscriptions_by_status: countMap(),
  by_currency: array(currencyTotalsSchema).required(),
  churn_events_30d: int(),
});

/** Page envelope schema for any item schema. */
export function pageSchema<T>(item: Schema<T>): Schema<Page<T>> {
  return object({
    items: array(item).required(),
    total: int(),
    page: int(),
    page_size: int(),
  });
}
