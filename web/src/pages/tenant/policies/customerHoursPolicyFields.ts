/** Customer hours policy fields (CUSTOMER_HOURS; mirrors backend CustomerHoursPolicy). */
import type { FieldOption, PolicyFieldDef } from './policyFields';

const BILLING_MODE_OPTIONS: readonly FieldOption[] = [
  { value: 'INVOICE', label: 'Invoice after the work' },
  { value: 'PREPAID_HOURS', label: 'Prepaid customer hours' },
];

export const CUSTOMER_HOURS_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'enabled',
    label: 'Customer hours switched on',
    kind: 'bool',
    help: 'Off: no purchases or prepaid jobs; jobs are invoiced.',
  },
  { key: 'walk_in_allowed', label: 'Walk-in customers allowed', kind: 'bool' },
  {
    key: 'billing_modes',
    label: 'Billing methods allowed on jobs',
    kind: 'multiEnum',
    options: BILLING_MODE_OPTIONS,
    help: 'The default billing below must be one of these.',
  },
  {
    key: 'default_billing_mode',
    label: 'Default billing of new jobs',
    kind: 'enum',
    options: BILLING_MODE_OPTIONS,
  },
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
    key: 'over_consumption',
    label: 'When a prepaid job has no hours left',
    kind: 'enum',
    options: [
      { value: 'BLOCK_START', label: 'Do not let the job start' },
      { value: 'FLAG_EXCESS', label: 'Allow it and flag the excess' },
    ],
  },
  {
    key: 'overrun_exception_blocking',
    label: 'Excess hours block the job until reviewed',
    kind: 'bool',
  },
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
  {
    key: 'drawdown',
    label: 'Take prepaid hours from the balance',
    kind: 'enum',
    options: [
      { value: 'AT_COMPLETION', label: 'When the job is completed' },
      { value: 'DAILY', label: 'Every day from the readings (final at completion)' },
    ],
    help: 'Daily: the balance goes down each day the machine works; completion replaces the daily figures.',
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
];
