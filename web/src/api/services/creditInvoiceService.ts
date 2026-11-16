import { array, object, string, type Schema } from 'yup';
import type {
  CreditInvoiceDto,
  CreditInvoicePaymentDto,
  CreditInvoicePaymentIn,
  CustomerHoursSummaryDto,
} from '../hoursTypes';
import type { Page } from '../types';
import { PAYMENT_METHODS } from './financeSchemas';
import { bool, id, int, nullableId, nullableText, oneOf, text } from './schemaKit';
import {
  seg,
  tenantGet,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const optionalText = () => string().nullable().default(null);

const invoicePaymentSchema: Schema<CreditInvoicePaymentDto> = object({
  id: id(),
  payment_id: id(),
  amount: text(),
  method: oneOf(PAYMENT_METHODS),
  reference: nullableText(),
  collection_number: optionalText(),
  payment_status: text(),
  received_at: text(),
  received_by_staff_id: nullableId(),
  received_by_staff_name: optionalText(),
  recorded_by: nullableId(),
  recorded_by_name: optionalText(),
  created_at: text(),
  counts: bool(),
});

export const creditInvoiceSchema: Schema<CreditInvoiceDto> = object({
  id: id(),
  invoice_number: text(),
  purchase_id: id(),
  purchase_number: optionalText(),
  customer_id: id(),
  customer_name: optionalText(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  currency: text(),
  hours: text(),
  unit_price: text(),
  amount: text(),
  paid: text(),
  paid_verified: text(),
  balance: text(),
  payment_terms_days: int(),
  issued_at: text(),
  due_date: text(),
  status: oneOf(['UNPAID', 'PART_PAID', 'PAID', 'CANCELLED'] as const),
  overdue: bool(),
  days_overdue: int(),
  created_by: nullableId(),
  created_by_name: optionalText(),
  payments: array(invoicePaymentSchema).default([]),
});

export const customerHoursSchema: Schema<CustomerHoursSummaryDto> = object({
  customer_id: id(),
  customer_name: optionalText(),
  bought: text(),
  activated: text(),
  used: text(),
  left: text(),
  awaiting_activation: text(),
  credit_owed: text(),
});

const T = '/tenant';
const invoicePage = tenantPageSchema(creditInvoiceSchema);

/** Credit invoices (ADR-008): the credit part of an order, paid in full or in parts. */
export const creditInvoiceService = {
  /**
   * GET /tenant/credit-invoices (listCreditInvoices). Filters: `customer_id`, `purchase_id`, `status`,
   * `overdue`, `date_from` / `date_to` (issue day); `q` = invoice / order number or customer.
   */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CreditInvoiceDto>> {
    return tenantPage(`${T}/credit-invoices`, invoicePage, query, 'credit invoices', signal);
  },
  /** GET /tenant/credit-invoices/{id} (getCreditInvoice), with its payments. */
  get(invoiceId: string, signal?: AbortSignal): Promise<CreditInvoiceDto> {
    return tenantGet(
      `${T}/credit-invoices/${seg(invoiceId)}`,
      creditInvoiceSchema,
      'credit invoice',
      signal,
    );
  },
  /** POST /tenant/credit-invoices/{id}/payments (recordCreditInvoicePayment): returns the invoice. */
  recordPayment(
    invoiceId: string,
    body: CreditInvoicePaymentIn,
    idempotencyKey: string,
  ): Promise<CreditInvoiceDto> {
    return tenantSend(
      'post',
      `${T}/credit-invoices/${seg(invoiceId)}/payments`,
      body,
      creditInvoiceSchema,
      'credit invoice',
      idempotencyKey,
    );
  },
  /** GET /tenant/customer-hours (listCustomerHours): bought / used / left and credit owed per customer. */
  customerHours(customerId?: string, signal?: AbortSignal): Promise<CustomerHoursSummaryDto[]> {
    return tenantList(`${T}/customer-hours`, customerHoursSchema, 'customer hours', signal, {
      customer_id: customerId,
    });
  },
};
