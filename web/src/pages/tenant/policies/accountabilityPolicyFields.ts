/** Policy field catalogues for the accountability controls (cash custody chain, oversight dashboard). */
import type { PolicyFieldDef } from './policyFields';

export const CASH_CUSTODY_FIELDS: readonly PolicyFieldDef[] = [
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
];

export const OVERSIGHT_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'security_event_window_days',
    label: 'Refused-attempts window',
    kind: 'int',
    unit: 'days',
  },
];
