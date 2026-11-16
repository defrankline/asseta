import type { CreditInvoiceStatus as Status } from '../../../../api/hoursTypes';
import type { StatusTone } from '../../../../components/display/StatusChip';

export const CREDIT_INVOICE_STATUSES: readonly Status[] = [
  'UNPAID',
  'PART_PAID',
  'PAID',
  'CANCELLED',
];
export const CREDIT_INVOICE_STATUS_LABELS: Readonly<Record<Status, string>> = {
  UNPAID: 'Unpaid',
  PART_PAID: 'Part paid',
  PAID: 'Paid',
  CANCELLED: 'Cancelled',
};
export const CREDIT_INVOICE_STATUS_TONES: Readonly<Record<Status, StatusTone>> = {
  UNPAID: 'warning',
  PART_PAID: 'info',
  PAID: 'success',
  CANCELLED: 'default',
};
export const CREDIT_INVOICE_STATUS_OPTIONS = CREDIT_INVOICE_STATUSES.map((s) => ({
  value: s,
  label: CREDIT_INVOICE_STATUS_LABELS[s],
}));

export const OVERDUE_OPTIONS = [
  { value: 'true', label: 'Overdue' },
  { value: 'false', label: 'Not overdue' },
] as const;

/** A money string without a currency, grouped ("1,234,500"; trailing zero decimals dropped). */
export function groupedAmount(value: string): string {
  const [whole = '0', fraction = ''] = value.split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const frac = fraction.replace(/0+$/, '');
  return frac === '' ? grouped : `${grouped}.${frac}`;
}

/** A payment of an invoice in plain words: claimed until verified, or no longer counting. */
export function invoicePaymentStatusText(p: { payment_status: string; counts: boolean }): string {
  if (!p.counts) return 'Does not count (rejected or reversed)';
  if (p.payment_status === 'VERIFIED') return 'Verified';
  return 'Claimed (waiting for verification)';
}
