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
