/** Customer hours policy fields (CUSTOMER_HOURS; mirrors backend CustomerHoursPolicy). */
import type { FieldOption, PolicyFieldDef } from './policyFields';

const CASH_ACTIVATION_OPTIONS: readonly FieldOption[] = [
  { value: 'VERIFY', label: 'By the office (Verify)' },
  { value: 'ON_HANDOVER', label: 'When the handover is confirmed' },
  { value: 'ON_RECORDING', label: 'When recorded' },
];

const REPORT_HOURS_SCOPE_OPTIONS: readonly FieldOption[] = [
  { value: 'CUSTOMER', label: 'Any of the customer’s hours' },
  { value: 'MACHINE', label: 'Only the customer’s hours on the reported machine' },
];

export const CUSTOMER_HOURS_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'enabled',
    label: 'Customer hours switched on',
    kind: 'bool',
    help: 'Off: no hours sales, credit invoices or customer lines on machine reports.',
  },
  { key: 'walk_in_allowed', label: 'Walk-in customers allowed', kind: 'bool' },
  {
    key: 'activation_basis',
    label: 'Hours activate from',
    kind: 'multiEnum',
    options: [
      { value: 'VERIFIED_PAYMENT', label: 'Verified payments' },
      { value: 'CREDIT', label: 'Approved credit' },
    ],
  },
  { key: 'partial_activation', label: 'Partial payments activate hours pro rata', kind: 'bool' },
  {
    key: 'hours_increment',
    label: 'Activation step',
    kind: 'decimal',
    unit: 'h',
    help: 'Activated hours are rounded down to this step.',
  },
  {
    key: 'expiry_days',
    label: 'Unused hours expire after',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Counted from activation; leave empty to never expire.',
  },
  { key: 'expiry_warning_days', label: 'Warn before expiry', kind: 'int', unit: 'days' },
  {
    key: 'transfer_requires_approval',
    label: 'Transfers between machines need a second person',
    kind: 'bool',
  },
  {
    key: 'cancellation_requires_approval',
    label: 'Cancellations need a second person',
    kind: 'bool',
  },
  {
    key: 'cancellation_after_consumption_allowed',
    label: 'Cancel the rest of a partly used purchase',
    kind: 'bool',
  },
  { key: 'discount_requires_approval', label: 'Discounts need a second person', kind: 'bool' },
  { key: 'max_discount_percent', label: 'Highest discount', kind: 'decimal', unit: '%' },
  { key: 'credit_allowed', label: 'Credit arrangements allowed', kind: 'bool' },
  { key: 'reason_code_required', label: 'A reason from the tenant list is required', kind: 'bool' },
  { key: 'refund_allowed', label: 'Allow refunds of unused hours', kind: 'bool' },
  {
    key: 'field_noncash_payments',
    label:
      'Field staff may record bank and mobile-money parts of an hours sale (reference required; the office verifies)',
    kind: 'bool',
  },
  {
    key: 'adjustment_evidence_required',
    label: 'Corrections, refunds and reversals need evidence',
    kind: 'bool',
  },
  { key: 'transfer_evidence_required', label: 'Hours transfers need evidence', kind: 'bool' },
  { key: 'credit_evidence_required', label: 'Credit arrangements need evidence', kind: 'bool' },
  {
    key: 'zero_amount_requires_approval',
    label: 'Purchases with nothing to pay need a second person',
    kind: 'bool',
  },
  {
    key: 'variance_sweep_enabled',
    label: 'Check customer-hour records for mismatches',
    kind: 'bool',
  },
  {
    key: 'variance_tolerance_hours',
    label: 'Ignore hour differences up to',
    kind: 'decimal',
    unit: 'h',
  },
  {
    key: 'low_balance_hours',
    label: 'Warn the office when hours left fall to',
    kind: 'nullableDecimal',
    unit: 'h',
    help: 'Once per purchase each time it falls to this level; leave empty for no warning.',
  },
  {
    key: 'low_balance_notify_customer',
    label: 'Also send the customer an SMS (uses SMS credits)',
    kind: 'bool',
  },
  {
    key: 'field_credit_sales',
    label:
      'Field staff may sell hours on credit (a credit invoice is created; the office approves the hours)',
    kind: 'bool',
    help: 'People allowed to activate credit may always record a credit part.',
  },
  {
    key: 'report_hours_scope',
    label: 'Machine reports draw customer hours from',
    kind: 'enum',
    options: REPORT_HOURS_SCOPE_OPTIONS,
  },
  {
    key: 'machine_report_reminder_days',
    label: 'Remind approvers when a machine moved with no report for',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Counted from the meter or tracker; leave empty for no reminder.',
  },
  {
    key: 'cash_activation',
    label: 'When cash on an hours sale counts as verified',
    kind: 'enum',
    options: CASH_ACTIVATION_OPTIONS,
  },
];
