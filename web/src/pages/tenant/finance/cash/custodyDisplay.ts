/** Labels, tones and error hints of the cash custody chain controls (neutral wording throughout). */
import { cashTabPath, financeTabPath, ROUTES } from '../../../../navigation/routes';
import type { CashCustodyEntryDto } from '../../../../api/types';
import type {
  CustodyTransactionDto,
  CashDecisionStatus,
  CashAckMethod,
  CashReasonKind,
  CashTransferStatus,
  CashVarianceDto,
  CustodyAdjustmentKind,
  ReconciliationFigure,
  VarianceOutcome,
  VarianceSource,
  VarianceStatus,
} from '../../../../api/custodyTypes';
import type { StatusTone } from '../../../../components/display/StatusChip';
import type { Option } from '../../shared/display';
import { FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';

const options = <T extends string>(labels: Readonly<Record<T, string>>): readonly Option<T>[] =>
  (Object.keys(labels) as T[]).map((value) => ({ value, label: labels[value] }));

export const TRANSFER_STATUS_LABELS: Readonly<Record<CashTransferStatus, string>> = {
  PENDING_ACKNOWLEDGEMENT: 'Awaiting acknowledgement',
  ACKNOWLEDGED: 'Acknowledged',
  DISPUTED: 'Disputed',
};
export const TRANSFER_STATUS_TONES: Readonly<Record<CashTransferStatus, StatusTone>> = {
  PENDING_ACKNOWLEDGEMENT: 'warning',
  ACKNOWLEDGED: 'success',
  DISPUTED: 'error',
};
export const TRANSFER_STATUS_OPTIONS = options(TRANSFER_STATUS_LABELS);

export const ACK_METHOD_LABELS: Readonly<Record<CashAckMethod, string>> = {
  RECEIVER: 'By the receiver',
  ON_BEHALF: 'On the receiver’s behalf',
  RECORDER_IS_RECEIVER: 'Recorded by the receiver',
  NOT_REQUIRED: 'Not required (policy)',
};

export type FloatAckStatus = CashCustodyEntryDto['ack_status'];
export const FLOAT_ACK_LABELS: Readonly<Record<FloatAckStatus, string>> = {
  NOT_REQUIRED: 'Not required',
  PENDING: 'Awaiting acknowledgement',
  ACKNOWLEDGED: 'Acknowledged',
  DISPUTED: 'Disputed',
};
export const FLOAT_ACK_TONES: Readonly<Record<FloatAckStatus, StatusTone>> = {
  NOT_REQUIRED: 'default',
  PENDING: 'warning',
  ACKNOWLEDGED: 'success',
  DISPUTED: 'error',
};

export const VARIANCE_STATUS_LABELS: Readonly<Record<VarianceStatus, string>> = {
  OPEN: 'Open',
  WRITE_OFF_PROPOSED: 'Write-off proposed',
  RESOLVED: 'Resolved',
};
export const VARIANCE_STATUS_TONES: Readonly<Record<VarianceStatus, StatusTone>> = {
  OPEN: 'warning',
  WRITE_OFF_PROPOSED: 'info',
  RESOLVED: 'success',
};
export const VARIANCE_STATUS_OPTIONS = options(VARIANCE_STATUS_LABELS);
export const VARIANCE_OUTCOME_LABELS: Readonly<Record<VarianceOutcome, string>> = {
  RECOVERED: 'Recovered',
  CORRECTED_ERROR: 'Corrected error',
  WRITTEN_OFF: 'Written off',
};
export const VARIANCE_OUTCOME_OPTIONS = options(VARIANCE_OUTCOME_LABELS);

/** SURPLUS: more was received than declared (a negative difference) — neutral wording, never blame. */
export const VARIANCE_KIND_LABELS: Readonly<Record<CashVarianceDto['kind'], string>> = {
  SHORTFALL: 'Shortfall',
  SURPLUS: 'Surplus to explain',
};
export const VARIANCE_SOURCE_LABELS: Readonly<Record<VarianceSource, string>> = {
  TRANSFER: 'Transfer',
  REMITTANCE: 'Remittance',
  FLOAT: 'Float',
};
export const VARIANCE_SOURCE_OPTIONS = options(VARIANCE_SOURCE_LABELS);

export const DECISION_STATUS_LABELS: Readonly<Record<CashDecisionStatus, string>> = {
  PENDING: 'Awaiting decision',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
};
export const DECISION_STATUS_TONES: Readonly<Record<CashDecisionStatus, StatusTone>> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'error',
};
export const DECISION_STATUS_OPTIONS = options(DECISION_STATUS_LABELS);

export const ADJUSTMENT_KIND_LABELS: Readonly<Record<CustodyAdjustmentKind, string>> = {
  ADJUSTMENT: 'Adjustment',
  REVERSAL: 'Reversal of a record',
};
export const ADJUSTMENT_KIND_OPTIONS = options(ADJUSTMENT_KIND_LABELS);

export const REASON_KIND_LABELS: Readonly<Record<CashReasonKind, string>> = {
  VARIANCE: 'Variance',
  WRITE_OFF: 'Write-off',
  RETENTION: 'Retention',
  ADJUSTMENT: 'Adjustment',
};
export const REASON_KIND_OPTIONS = options(REASON_KIND_LABELS);

/** Records a reversal can name (the server's `ReversibleEntity`). */
export const REVERSIBLE_ENTITY_LABELS = {
  customer_payment: 'Cash collection',
  cash_handover: 'Remittance',
  cash_transfer: 'Transfer',
  supervisor_cash_custody: 'Float / opening balance',
  expense: 'Expense',
  custody_adjustment: 'Custody adjustment',
} as const;
export type ReversibleEntity = keyof typeof REVERSIBLE_ENTITY_LABELS;
export const REVERSIBLE_ENTITY_OPTIONS = options(REVERSIBLE_ENTITY_LABELS);

/** Every reconciliation figure, as labelled on the reconciliation (sign shown separately). */
export const FIGURE_LABELS: Readonly<Record<ReconciliationFigure, string>> = {
  floats_issued: 'Floats issued',
  collections: 'Cash collections',
  transfers_in: 'Transfers received',
  transfers_out: 'Transfers sent',
  approved_spending: 'Approved cash expenses',
  verified_handovers: 'Confirmed remittances',
  adjustments: 'Approved adjustments',
  written_off: 'Written off',
  claimed_unverified_handovers: 'Remittances awaiting confirmation',
  pending_spending: 'Cash expenses pending approval',
  unverified_collections: 'Collections not yet verified',
  in_transit_out: 'Sent, not yet acknowledged',
  in_transit_in: 'Incoming, not yet acknowledged',
  pending_floats: 'Floats awaiting acknowledgement',
  pending_adjustments: 'Adjustments awaiting decision',
};

/** Record types behind a reconciliation transaction. */
export const ENTITY_TYPE_LABELS: Readonly<Record<string, string>> = {
  ...REVERSIBLE_ENTITY_LABELS,
  cash_variance: 'Variance',
};
export const entityTypeLabel = (t: string): string => ENTITY_TYPE_LABELS[t] ?? t.replace(/_/g, ' ');

/** Server error codes of the custody chain → what the user can do (finance hints included). */
export const CUSTODY_ERROR_HINTS: Readonly<Record<string, string>> = {
  ...FINANCE_ERROR_HINTS,
  NOT_CUSTODIAN:
    'You may only record for yourself; recording for another custodian needs office cash permission or the tenant’s permission for recorders.',
  NOT_RECEIVER:
    'Only the receiving custodian (or a recorder on their behalf, when allowed) may answer.',
  TRANSFER_SAME_CUSTODIAN: 'The sender and the receiver must be different people.',
  TRANSFER_ALREADY_DECIDED: 'Someone already answered this transfer. Reload to see it.',
  FLOAT_ALREADY_ACKNOWLEDGED: 'Someone already answered this float. Reload to see it.',
  FLOAT_ACK_NOT_REQUIRED: 'This tenant does not require floats to be acknowledged.',
  AMOUNT_RECEIVED_NOT_ALLOWED: 'Only the receiver states the amount actually received.',
  AMOUNT_RECEIVED_INVALID: 'Enter the amount actually counted (zero or more).',
  VARIANCE_NOT_OPEN: 'The variance is no longer open. Reload to see it.',
  WRITEOFF_APPROVAL_REQUIRED:
    'This tenant requires write-offs to be proposed and then approved by someone else.',
  WRITEOFF_NOT_PROPOSED: 'No write-off is proposed on this variance. Reload to see it.',
  RETENTION_NOT_ALLOWED: 'This tenant does not allow keeping cash; remit the full balance.',
  RETENTION_ALREADY_DECIDED: 'Someone already decided this request. Reload to see it.',
  ADJUSTMENT_ALREADY_DECIDED: 'Someone already decided this adjustment. Reload to see it.',
  REVERSED_RECORD_NOT_FOUND: 'The record to reverse was not found. Check its type and id.',
  REASON_REQUIRED: 'This tenant keeps a reason list for this; choose a reason from it.',
  REASON_INVALID: 'Choose an active reason of the right kind.',
  REASON_NOT_FOUND: 'The reason is no longer available. Choose another.',
  SYNC_CONFLICT_ALREADY_RESOLVED: 'Someone already recorded an outcome. Reload to see it.',
};

/** Tooltip on a disabled decision of your own request (segregation of duties). */
export const OWN_REQUEST_TOOLTIP = 'Someone else must decide your own request';

/** Where the evidence of a transaction's record is opened (office pages only). */
export function transactionRecordPath(t: CustodyTransactionDto): string | null {
  switch (t.entity_type) {
    case 'cash_transfer':
      return cashTabPath('transfers', { id: t.entity_id });
    case 'cash_handover':
      return cashTabPath('handovers');
    case 'supervisor_cash_custody':
      return cashTabPath('floats');
    case 'custody_adjustment':
      return cashTabPath('adjustments');
    case 'cash_variance':
      return cashTabPath('variances', { id: t.entity_id });
    case 'customer_payment':
      return financeTabPath('payments');
    case 'expense':
      return ROUTES.tenantExpenses;
    default:
      return null;
  }
}
