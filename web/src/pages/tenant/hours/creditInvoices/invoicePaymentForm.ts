import { mixed, object, string, type ObjectSchema } from 'yup';
import type { CreditInvoicePaymentIn } from '../../../../api/hoursTypes';
import type { AttachmentDto, HirePaymentMethod } from '../../../../api/types';
import { PAYMENT_METHODS } from '../../../../api/services/financeSchemas';
import { compareDecimal } from '../../../../utils/money';
import { positiveDecimalField } from '../../../platform/shared/validators';
import { FINANCE_ERROR_HINTS } from '../../shared/financeDisplay';
import { optionalText, orNull } from '../../shared/formRules';

/** Record a payment of a credit invoice: full (the balance) or part, by cash, bank or mobile money. */
export interface InvoicePaymentValues {
  amount: string;
  method: HirePaymentMethod;
  reference: string;
  received_at: string;
  /** Office only: the staff member holding the cash ('' = me). */
  staff_member_id: string;
  note: string;
  evidence: AttachmentDto | null;
  /** The invoice balance (never sent): the amount may not exceed it. */
  balance: string;
}

export const PAY_FIELDS = ['amount', 'method', 'reference'] as const;
export const DETAIL_FIELDS = ['received_at', 'staff_member_id', 'note'] as const;

export function emptyInvoicePayment(balance: string, now: string): InvoicePaymentValues {
  return {
    amount: balance,
    method: 'CASH',
    reference: '',
    received_at: now,
    staff_member_id: '',
    note: '',
    evidence: null,
    balance,
  };
}

export const OVER_BALANCE_TEXT = 'The amount is more than the balance of the invoice.';

export const invoicePaymentSchema: ObjectSchema<InvoicePaymentValues> = object({
  amount: positiveDecimalField('Amount').test('balance', OVER_BALANCE_TEXT, function (v) {
    const { balance } = this.parent as InvoicePaymentValues;
    return balance === '' || compareDecimal(v.trim(), balance) <= 0;
  }),
  method: mixed<HirePaymentMethod>()
    .oneOf([...PAYMENT_METHODS])
    .required('Choose the method'),
  reference: optionalText('Reference', 120).test(
    'reference',
    'Reference is required for bank and mobile money',
    function (v) {
      return (this.parent as InvoicePaymentValues).method === 'CASH' || v.trim() !== '';
    },
  ),
  received_at: string()
    .required('Received at is required')
    .test('instant', 'Enter a valid date and time', (v) => !Number.isNaN(Date.parse(v))),
  staff_member_id: string().ensure(),
  note: optionalText('Note', 1000),
  evidence: mixed<AttachmentDto>().nullable().defined(),
  balance: string().ensure(),
});

/** recordCreditInvoicePayment body. */
export function toInvoicePaymentPayload(
  v: InvoicePaymentValues,
  clientId: string,
  options: { office: boolean },
): CreditInvoicePaymentIn {
  return {
    client_id: clientId,
    amount: v.amount.trim(),
    method: v.method,
    reference: v.method === 'CASH' ? orNull(v.reference) : v.reference.trim(),
    received_at: v.received_at,
    staff_member_id: options.office && v.method === 'CASH' ? orNull(v.staff_member_id) : null,
    note: orNull(v.note),
    evidence_attachment_ids: v.evidence === null ? [] : [v.evidence.id],
  };
}

/** Refusals of an invoice payment in plain words. */
export const INVOICE_PAYMENT_HINTS: Readonly<Record<string, string>> = {
  ...FINANCE_ERROR_HINTS,
  INVOICE_NOT_FOUND: 'This invoice no longer exists. Reload the page.',
  INVOICE_OVERPAYMENT: 'The amount is more than what is left to pay. Lower the amount.',
  INVOICE_PAID: 'This invoice is already paid in full.',
  INVOICE_CANCELLED:
    'This invoice is cancelled (its order was cancelled or its credit was rejected); it takes no payments.',
  PAYMENT_NOT_PERMITTED:
    'Your company lets the office record bank and mobile-money payments. Record cash, or ask the office.',
};
