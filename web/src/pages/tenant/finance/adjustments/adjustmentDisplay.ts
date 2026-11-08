/** Labels, tones and refusal texts of the adjustments ledger and its requests (neutral wording). */
import type {
  AdjustmentEntryStatus,
  AdjustmentRequestStatus,
  AdjustmentRequestType,
  AdjustmentType,
  AdjustmentUnit,
  RefundSettlement,
} from '../../../../api/adjustmentTypes';
import type { HirePaymentMethod } from '../../../../api/types';
import {
  ADJUSTMENT_TYPES,
  ENTRY_STATUSES,
  REQUEST_STATUSES,
  REQUEST_TYPES,
} from '../../../../api/services/adjustmentSchemas';
import type { StatusTone } from '../../../../components/display/StatusChip';
import { ADJUSTMENT_ROUTES, adjustmentRequestPath } from '../../../../navigation/adjustmentRoutes';
import { hoursPurchasePath } from '../../../../navigation/hoursRoutes';
import { recordPath } from '../../../../navigation/recordRoutes';
import {
  financeTabPath,
  hireInvoiceDetailPath,
  machineDetailPath,
} from '../../../../navigation/routes';
import { formatMoney } from '../../../../utils/money';
import { HOURS_ERROR_HINTS, hoursText } from '../../hours/hoursDisplay';
import type { Option } from '../../shared/display';

export const ADJUSTMENT_TYPE_LABELS: Readonly<Record<AdjustmentType, string>> = {
  HOURS_TRANSFER: 'Hours transfer',
  HOURS_CANCELLATION: 'Hours cancellation',
  HOURS_CORRECTION: 'Hours correction',
  HOURS_REFUND: 'Hours refund',
  CREDIT_ARRANGEMENT: 'Credit arrangement',
  METER_CORRECTION: 'Meter correction',
  ALLOCATION_CORRECTION: 'Allocation correction',
  ENGINE_HOUR_CLASSIFICATION: 'Engine hour classification',
  NON_REVENUE_APPROVAL: 'Non-revenue approval',
  CASH_WRITE_OFF: 'Cash write-off',
  CASH_VARIANCE_RESOLUTION: 'Cash difference resolved',
  CUSTODY_ADJUSTMENT: 'Custody adjustment',
  INVOICE_VOID: 'Invoice void',
  PAYMENT_REVERSAL: 'Payment reversal',
  COLLECTION_REVERSAL: 'Collection reversal',
  PURCHASE_REVERSAL: 'Purchase reversal',
  ZERO_AMOUNT_ACTIVATION: 'Zero-amount purchase approved',
  HOURS_VARIANCE_RESOLUTION: 'Customer hours difference resolved',
};
export const ADJUSTMENT_TYPE_OPTIONS: readonly Option<AdjustmentType>[] = ADJUSTMENT_TYPES.map(
  (t) => ({ value: t, label: ADJUSTMENT_TYPE_LABELS[t] }),
);

export const ENTRY_STATUS_LABELS: Readonly<Record<AdjustmentEntryStatus, string>> = {
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  REVOKED: 'Revoked',
};
export const ENTRY_STATUS_TONES: Readonly<Record<AdjustmentEntryStatus, StatusTone>> = {
  APPROVED: 'success',
  REJECTED: 'error',
  REVOKED: 'default',
};
export const ENTRY_STATUS_OPTIONS: readonly Option<AdjustmentEntryStatus>[] = ENTRY_STATUSES.map(
  (s) => ({ value: s, label: ENTRY_STATUS_LABELS[s] }),
);

export const REQUEST_TYPE_LABELS: Readonly<Record<AdjustmentRequestType, string>> = {
  HOURS_CORRECTION: 'Hours correction',
  HOURS_REFUND: 'Hours refund',
  PAYMENT_REVERSAL: 'Payment reversal',
  COLLECTION_REVERSAL: 'Collection reversal',
  PURCHASE_REVERSAL: 'Purchase reversal',
  INVOICE_VOID: 'Invoice void',
  ZERO_AMOUNT_ACTIVATION: 'Zero-amount purchase',
};
export const REQUEST_TYPE_OPTIONS: readonly Option<AdjustmentRequestType>[] = REQUEST_TYPES.map(
  (t) => ({ value: t, label: REQUEST_TYPE_LABELS[t] }),
);

export const REQUEST_STATUS_LABELS: Readonly<Record<AdjustmentRequestStatus, string>> = {
  PROPOSED: 'Awaiting decision',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  WITHDRAWN: 'Withdrawn',
};
export const REQUEST_STATUS_TONES: Readonly<Record<AdjustmentRequestStatus, StatusTone>> = {
  PROPOSED: 'warning',
  APPROVED: 'success',
  REJECTED: 'error',
  WITHDRAWN: 'default',
};
export const REQUEST_STATUS_OPTIONS: readonly Option<AdjustmentRequestStatus>[] =
  REQUEST_STATUSES.map((s) => ({ value: s, label: REQUEST_STATUS_LABELS[s] }));

export const SETTLEMENT_LABELS: Readonly<Record<RefundSettlement, string>> = {
  CREDIT: 'Back to the customer’s credit',
  PAY_OUT: 'Paid out to the customer',
};
export const SETTLEMENT_OPTIONS: readonly Option<RefundSettlement>[] = [
  { value: 'CREDIT', label: SETTLEMENT_LABELS.CREDIT },
  { value: 'PAY_OUT', label: SETTLEMENT_LABELS.PAY_OUT },
];

export const TREATMENT_LABELS: Readonly<Record<string, string>> = {
  RECEIVABLE: 'Billed to the customer',
  CASE: 'Investigation case opened',
};

/** Refusals of the propose / decide flow, in plain language. */
export const ADJUSTMENT_ERROR_HINTS: Readonly<Record<string, string>> = {
  ...HOURS_ERROR_HINTS,
  EVIDENCE_REQUIRED: 'Your company policy needs supporting evidence: attach it first.',
  REASON_CODE_REQUIRED: 'Your company policy needs a reason from the list.',
  ALREADY_DECIDED: 'This request has already been decided.',
  NOT_PROPOSER: 'Only the person who proposed this can withdraw it.',
  REVERSAL_EXISTS: 'A reversal of this record already exists or awaits a decision.',
  ADJUSTMENT_FIELDS_MISSING: 'Some details of this request are missing.',
  PURCHASE_CANCELLED: 'The purchase is cancelled.',
  HOURS_CORRECTION_INVALID: 'A correction must change the hours.',
  HOURS_CORRECTION_NEGATIVE: 'A correction cannot take the hours on that machine below zero.',
  HOURS_CORRECTION_EXCEEDS_LOT: 'A correction cannot lift the purchase above its activated hours.',
  HOURS_CORRECTION_EXCEEDS_ENTRY: 'A correction cannot give back more than that use of hours.',
  CONSUMED_ENTRY_NOT_FOUND: 'That use of hours is not on this purchase.',
  REFUND_NOT_ALLOWED: 'Refunds are switched off in your company policy.',
  REFUND_SETTLEMENT_REQUIRED: 'Choose how the refund is settled.',
  REFUND_PAYOUT_REQUIRED: 'Record how the refund is paid out.',
  HOURS_REFUND_INVALID: 'Enter the hours to refund.',
  EXCEEDS_REMAINING_HOURS: 'Only unused hours can be refunded.',
  REFUND_EXCEEDS_PAID: 'The refund is more than the verified money on this purchase.',
  STAFF_NOT_FOUND: 'That staff member was not found.',
  PAYMENT_NOT_VERIFIED: 'Only a verified payment can be reversed.',
  PAYMENT_ALREADY_REVERSED: 'This payment has already been reversed.',
  PAYMENT_REVERSED: 'This payment has been reversed.',
  REVERSAL_TYPE_MISMATCH: 'Cash is reversed as a collection; bank or mobile money as a payment.',
  NOTHING_TO_REVERSE: 'There is nothing left to reverse on this record.',
  INVOICE_NOT_ISSUED: 'Only an issued invoice needs a void request.',
};

/** A value in the unit the ledger entry measures. */
export function unitValue(
  value: string | null,
  unit: AdjustmentUnit,
  currency: string | null,
): string {
  if (value === null) return '—';
  if (unit === 'HOURS') return hoursText(value);
  if (unit === 'MONEY' && currency !== null) return formatMoney(value, currency);
  return value;
}

/** The reversal type the API expects for a payment's method. */
export const reversalTypeOf = (method: HirePaymentMethod): AdjustmentRequestType =>
  method === 'CASH' ? 'COLLECTION_REVERSAL' : 'PAYMENT_REVERSAL';

/** Opens the payments tab on one payment's details. */
export const paymentRecordPath = (id: string): string =>
  `${financeTabPath('payments')}&payment_id=${encodeURIComponent(id)}`;

/** The page of a record named by a ledger entry (`original_type` / `source_type`), when it has one. */
export function adjustedRecordPath(type: string, id: string): string | null {
  switch (type) {
    case 'hours_purchase':
      return hoursPurchasePath(id);
    case 'customer_payment':
      return paymentRecordPath(id);
    case 'tenant_hire_invoice':
      return hireInvoiceDetailPath(id);
    case 'machine':
      return machineDetailPath(id);
    case 'adjustment_request':
      return adjustmentRequestPath(id);
    case 'credit_arrangement':
      return recordPath('HOURS_CREDIT', id);
    case 'hours_transfer':
      return recordPath('HOURS_TRANSFER', id);
    case 'hours_cancellation':
      return recordPath('HOURS_CANCELLATION', id);
    case 'cash_variance':
      return recordPath('CASH_VARIANCE', id);
    case 'custody_adjustment':
      return recordPath('CUSTODY_ADJUSTMENT', id);
    case 'work_allocation':
      return recordPath('WORK_ALLOCATION', id);
    case 'work_allocation_correction':
      return recordPath('WORK_ALLOCATION_CORRECTION', id);
    case 'meter_correction':
      return recordPath('METER_CORRECTION', id);
    case 'engine_hour_classification':
      return recordPath('ENGINE_HOURS_CLASSIFICATION', id);
    case 'non_revenue_approval':
      return recordPath('NON_REVENUE_APPROVAL', id);
    default:
      return null;
  }
}

/** Requests touching one record, from that record's page. */
export const requestsOfRecordPath = (originalId: string): string =>
  `${ADJUSTMENT_ROUTES.requests}?original_id=${encodeURIComponent(originalId)}`;
