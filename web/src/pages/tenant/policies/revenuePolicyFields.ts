/** Revenue reconciliation policy fields (REVENUE_RECONCILIATION; mirrors backend RevenueReconciliationPolicy). */
import type { PolicyFieldDef } from './policyFields';

export const REVENUE_RECONCILIATION_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'enabled',
    label: 'Revenue checks switched on',
    kind: 'bool',
    help: 'Off: no daily machine sheet, no revenue differences, and movement inside a job counts as customer work (as today).',
  },
  {
    key: 'non_revenue_activity_types',
    label: 'Work-log types that are not revenue',
    kind: 'multiEnum',
    minItems: 0,
    options: [
      { value: 'MOBILIZATION', label: 'Movement (mobilization)' },
      { value: 'STANDBY', label: 'Standby' },
      { value: 'DOWNTIME', label: 'Downtime' },
    ],
    help: 'Non-billable time of these types inside a job. Standby billing still follows the contract.',
  },
  {
    key: 'deduct_non_revenue_from_working_hours',
    label: 'Show that time apart from customer work',
    kind: 'bool',
    help: 'On: it is its own bucket on the engine-hour ledger and daily sheet, and is not billed on invoice jobs.',
  },
  {
    key: 'deduct_non_revenue_from_prepaid_hours',
    label: 'Do not take that time from prepaid hours',
    kind: 'bool',
    help: 'On: prepaid jobs do not draw these hours from the customer’s balance.',
  },
  {
    key: 'non_revenue_requires_approval',
    label: 'Non-revenue time needs approval',
    kind: 'bool',
    help: 'On: logged movement or other non-revenue time counts as revenue until explained and approved by a second person.',
  },
  {
    key: 'unexplained_hours_treatment',
    label: 'Unexplained hours outside jobs',
    kind: 'enum',
    options: [
      { value: 'EXPECT_REVENUE', label: 'Expected as revenue until approved' },
      { value: 'EXCLUDE', label: 'Shown only' },
    ],
    help: 'Engine hours outside jobs count as expected revenue until approved as non-customer activity.',
  },
  {
    key: 'unexplained_hours_rate_source',
    label: 'Rate for unexplained hours',
    kind: 'enum',
    options: [
      { value: 'MACHINE_RATE_CARD', label: 'The machine category rate card' },
      { value: 'TENANT_RATE', label: 'A tenant rate' },
    ],
  },
  {
    key: 'unexplained_hours_rate',
    label: 'Tenant rate for unexplained hours',
    kind: 'nullableDecimal',
    unit: '/h',
    help: 'Used when the rate source is a tenant rate.',
  },
  {
    key: 'period',
    label: 'Check period',
    kind: 'enum',
    options: [
      { value: 'DAY', label: 'Each day' },
      { value: 'WEEK', label: 'Each week (Monday to Sunday)' },
      { value: 'JOB', label: 'Each completed job' },
    ],
    help: 'Hours are matched with money once the period has closed (tenant time zone).',
  },
  {
    key: 'tolerance_percent',
    label: 'Tolerance',
    kind: 'decimal',
    unit: '%',
    help: 'A shortfall above this share of the expected revenue is a difference to explain.',
  },
  {
    key: 'tolerance_amount',
    label: 'Tolerance amount',
    kind: 'nullableDecimal',
    help: 'A shortfall above this amount is also a difference to explain. Leave empty to use the percentage only.',
  },
  {
    key: 'case_threshold_amount',
    label: 'Open a case for differences above',
    kind: 'nullableDecimal',
    help: 'Leave empty to never open an investigation case automatically.',
  },
  {
    key: 'basis',
    label: 'Money counted',
    kind: 'enum',
    options: [{ value: 'INVOICED_OR_PREPAID', label: 'Issued invoices and prepaid hours used' }],
  },
  {
    key: 'recheck_days',
    label: 'Re-check closed periods for',
    kind: 'int',
    unit: 'days',
    help: 'Money that arrives later clears an open difference during this time.',
  },
];
