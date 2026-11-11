/** Petty cash policy fields (PETTY_CASH; mirrors backend PettyCashPolicy, DEC-033). */
import type { PolicyFieldDef } from './policyFields';

export const PETTY_CASH_FIELDS: readonly PolicyFieldDef[] = [
  { key: 'enabled', label: 'Petty cash funds', kind: 'bool' },
  {
    key: 'max_expense_amount',
    label: 'Approval always needed above',
    kind: 'nullableDecimal',
    help: 'An expense paid from a fund above this amount always needs an approver. Leave empty for no maximum.',
  },
  {
    key: 'overspend_allowed_offline',
    label: 'Keep offline overspends for approval',
    kind: 'bool',
    help: 'On: an offline expense above what the fund had is kept pending and flagged. Off: it is held for review.',
  },
  {
    key: 'count_every_days',
    label: 'Count every fund every',
    kind: 'nullableNumber',
    unit: 'days',
    help: 'Leave empty for no count schedule.',
  },
  { key: 'count_witness_required', label: 'A count needs a witness', kind: 'bool' },
  { key: 'return_evidence_required', label: 'Evidence on returns', kind: 'bool' },
  { key: 'funding_evidence_required', label: 'Evidence on fundings and top-ups', kind: 'bool' },
  { key: 'advances_enabled', label: 'Cash advances', kind: 'bool' },
  {
    key: 'advance_clear_within_days',
    label: 'Clear an advance within',
    kind: 'number',
    unit: 'days',
  },
];
