import type {
  FulfilmentStatus,
  InvoiceDto,
  InvoiceKind,
  InvoiceLineDto,
  InvoiceLineType,
} from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';
import { compareDecimal, isDecimalString, isZeroDecimal } from '../../../utils/money';

export const INVOICE_KIND_LABELS: Readonly<Record<InvoiceKind, string>> = {
  SUBSCRIPTION: 'Subscription',
  AD_HOC: 'Ad hoc',
};

export const INVOICE_KIND_TONES: Readonly<Record<string, StatusTone>> = {
  SUBSCRIPTION: 'default',
  AD_HOC: 'info',
};

export type LinePaymentState = 'UNPAID' | 'PARTIALLY_PAID' | 'PAID';

export const LINE_PAYMENT_TONES: Readonly<Record<LinePaymentState, StatusTone>> = {
  UNPAID: 'default',
  PARTIALLY_PAID: 'warning',
  PAID: 'success',
};

export const FULFILMENT_TONES: Readonly<Record<string, StatusTone>> = {
  FULFILLED: 'success',
  REVERSED: 'default',
  REVERSAL_FLAGGED: 'error',
  AWAITING: 'info',
};

export const FULFILMENT_LABELS: Readonly<Record<FulfilmentStatus | 'AWAITING', string>> = {
  FULFILLED: 'Fulfilled',
  REVERSED: 'Reversed',
  REVERSAL_FLAGGED: 'Reversal flagged for review',
  AWAITING: 'Awaiting full payment',
};

/** Line types whose full payment has an effect in another area (ADR-006). */
const FULFILLABLE: ReadonlySet<InvoiceLineType> = new Set([
  'SUBSCRIPTION_FEE',
  'SMS_BUNDLE',
  'SERVICE',
]);

export const VOID_ERROR_HINTS: Readonly<Record<string, string>> = {
  INVOICE_ALREADY_VOIDED: 'This invoice is already void; reload to see it.',
};

/**
 * Payment state of a line from the server's `payable` and `paid` (exact decimal comparison, no
 * arithmetic); null when the line takes no money (e.g. a credit line).
 */
export function linePaymentState(line: InvoiceLineDto): LinePaymentState | null {
  const payable = line.payable ?? null;
  const paid = line.paid ?? '0';
  if (payable === null || !isDecimalString(payable) || !isDecimalString(paid)) return null;
  if (isZeroDecimal(payable) || compareDecimal(payable, '0') < 0) return null;
  if (compareDecimal(paid, payable) >= 0) return 'PAID';
  return isZeroDecimal(paid) ? 'UNPAID' : 'PARTIALLY_PAID';
}

/** Fulfilment shown for a line: the server status, or "awaiting" for an unfulfilled live line. */
export function lineFulfilment(
  invoice: InvoiceDto,
  line: InvoiceLineDto,
): FulfilmentStatus | 'AWAITING' | null {
  if (line.fulfilment_status != null) return line.fulfilment_status;
  if (!FULFILLABLE.has(line.line_type) || invoice.status === 'VOIDED') return null;
  return 'AWAITING';
}

export function invoiceTitle(invoice: InvoiceDto): string {
  return invoice.invoice_number ?? 'Invoice';
}
