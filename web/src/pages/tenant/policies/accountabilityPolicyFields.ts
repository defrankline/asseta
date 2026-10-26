/** Policy field catalogues for the accountability controls (cash custody chain, oversight dashboard). */
import type { FieldOption, PolicyFieldDef } from './policyFields';

export const CASH_CUSTODY_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'enabled',
    label: 'Cash custody controls switched on',
    kind: 'bool',
    help: 'Off: transfers, acknowledgements, variances, retentions, adjustments, cash reasons and the remittance cut-off are hidden; collections, floats, remittances and reconciliation stay.',
  },
  {
    key: 'recorders_may_record_for_others',
    label: 'Recorders record for any custodian',
    kind: 'bool',
    help: 'Field recorders may record cash for staff without a login (otherwise own custody only).',
  },
  { key: 'transfer_ack_required', label: 'Receiver acknowledges transfers', kind: 'bool' },
  {
    key: 'recorder_receiver_counts_as_ack',
    label: 'Recording a transfer you receive acknowledges it',
    kind: 'bool',
  },
  { key: 'float_ack_required', label: 'Receiver acknowledges floats', kind: 'bool' },
  {
    key: 'remit_full_balance',
    label: 'Remit the full balance',
    kind: 'bool',
    help: 'A remittance leaving unretained cash with the custodian is flagged.',
  },
  {
    key: 'remittance_cutoff_hour',
    label: 'Daily remittance cut-off',
    kind: 'nullableNumber',
    unit: 'h',
    help: 'Tenant-local hour; leave empty for no daily cut-off.',
  },
  {
    key: 'variance_case_threshold',
    label: 'Open a case for differences above',
    kind: 'nullableDecimal',
    help: 'Leave empty to never open a case automatically.',
  },
  { key: 'writeoff_requires_approval', label: 'Write-offs need a second approver', kind: 'bool' },
  { key: 'retention_allowed', label: 'Approved retentions allowed', kind: 'bool' },
  {
    key: 'remittance_reference_required',
    label: 'Require a transaction reference for bank / mobile-money remittances',
    kind: 'bool',
    help: 'Cash handed to the office never needs one.',
  },
  {
    key: 'remittance_evidence_required',
    label: 'Require a photo of the deposit slip or payment confirmation',
    kind: 'bool',
  },
  {
    key: 'remittance_account_required',
    label: 'Require the company account the money was paid into',
    kind: 'bool',
  },
  {
    key: 'max_holding_days',
    label: 'Days a custodian may hold unremitted cash',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Leave empty for no limit. Cash covered by an approved retention does not count. Site and staff overrides allowed.',
  },
];

/** Accountability dashboard tiles (backend `accountability.service.TILES`). */
const DASHBOARD_TILES: readonly FieldOption[] = [
  { value: 'customer_hours', label: 'Customer hours' },
  { value: 'hours_awaiting_activation', label: 'Hours awaiting activation' },
  { value: 'engine_hours', label: 'Engine hours' },
  { value: 'unexplained_hours', label: 'Unexplained engine hours' },
  { value: 'missing_daily_reports', label: 'Missing daily reports' },
  { value: 'revenue_differences', label: 'Revenue differences' },
  { value: 'investigations', label: 'Investigations' },
  { value: 'cash', label: 'Cash' },
  { value: 'payments', label: 'Payments' },
  { value: 'discrepancies', label: 'Discrepancies' },
  { value: 'unauthorized_attempts', label: 'Refused attempts' },
  { value: 'outstanding_approvals', label: 'Outstanding approvals' },
];

export const OVERSIGHT_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'hidden_dashboard_tiles',
    label: 'Hidden dashboard tiles',
    kind: 'multiEnum',
    options: DASHBOARD_TILES,
    minItems: 0,
    help: 'Ticked tiles are hidden from the accountability dashboard.',
  },
  {
    key: 'security_event_window_days',
    label: 'Refused-attempts window',
    kind: 'int',
    unit: 'days',
  },
];
