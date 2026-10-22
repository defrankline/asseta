import { apiClient, toListParams } from '../client';
import type {
  AdHocInvoiceIn,
  CreditAdjustmentIn,
  InvoiceDto,
  InvoiceKind,
  InvoiceStatus,
  ListQuery,
  Page,
  VoidInvoiceIn,
} from '../types';
import { parseResponse } from '../validation';
import { invoiceSchema, pageSchema } from './billingSchemas';

const invoicePageSchema = pageSchema(invoiceSchema);

export interface InvoiceListQuery extends ListQuery {
  tenant_id?: string;
  status?: InvoiceStatus;
  kind?: InvoiceKind;
}

export const platformInvoiceService = {
  /** GET /platform/invoices (listPlatformInvoices). Server filters: tenant_id, status, kind. */
  async list(query: InvoiceListQuery, signal?: AbortSignal): Promise<Page<InvoiceDto>> {
    const { tenant_id, status, kind, ...rest } = query;
    const data = await apiClient.get<unknown>('/platform/invoices', {
      params: toListParams({ ...rest, filters: { tenant_id, status, kind } }),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(invoicePageSchema, data, 'invoice page');
  },

  /** GET /platform/invoices/{invoice_id} (getPlatformInvoice), including immutable lines. */
  async get(invoiceId: string, signal?: AbortSignal): Promise<InvoiceDto> {
    const data = await apiClient.get<unknown>(
      `/platform/invoices/${encodeURIComponent(invoiceId)}`,
      signal ? { signal } : undefined,
    );
    return parseResponse(invoiceSchema, data, 'invoice');
  },

  /** POST /platform/credit-adjustments (applyCredit); returns the updated invoice. */
  async applyCredit(body: CreditAdjustmentIn, idempotencyKey: string): Promise<InvoiceDto> {
    const data = await apiClient.post<unknown>('/platform/credit-adjustments', body, {
      idempotencyKey,
    });
    return parseResponse(invoiceSchema, data, 'invoice');
  },

  /**
   * POST /platform/invoices/preview (previewAdHocInvoice): server-computed lines and totals
   * (tax, discounts, the subscription period); nothing is saved.
   */
  async preview(body: AdHocInvoiceIn, idempotencyKey: string): Promise<InvoiceDto> {
    const data = await apiClient.post<unknown>('/platform/invoices/preview', body, {
      idempotencyKey,
    });
    return parseResponse(invoiceSchema, data, 'invoice preview');
  },

  /** POST /platform/invoices (raiseAdHocInvoice). */
  async raise(body: AdHocInvoiceIn, idempotencyKey: string): Promise<InvoiceDto> {
    const data = await apiClient.post<unknown>('/platform/invoices', body, { idempotencyKey });
    return parseResponse(invoiceSchema, data, 'invoice');
  },

  /** POST /platform/invoices/{id}/void (voidPlatformInvoice): reversal with a reason. */
  async void(invoiceId: string, body: VoidInvoiceIn, idempotencyKey: string): Promise<InvoiceDto> {
    const data = await apiClient.post<unknown>(
      `/platform/invoices/${encodeURIComponent(invoiceId)}/void`,
      body,
      { idempotencyKey },
    );
    return parseResponse(invoiceSchema, data, 'invoice');
  },
};
