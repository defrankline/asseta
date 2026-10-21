import { apiClient, toListParams } from '../client';
import type { CreditAdjustmentIn, InvoiceDto, InvoiceStatus, ListQuery, Page } from '../types';
import { parseResponse } from '../validation';
import { invoiceSchema, pageSchema } from './billingSchemas';

const invoicePageSchema = pageSchema(invoiceSchema);

export interface InvoiceListQuery extends ListQuery {
  tenant_id?: string;
  status?: InvoiceStatus;
}

export const platformInvoiceService = {
  /** GET /platform/invoices (listPlatformInvoices). Server filters: tenant_id, status. */
  async list(query: InvoiceListQuery, signal?: AbortSignal): Promise<Page<InvoiceDto>> {
    const { tenant_id, status, ...rest } = query;
    const data = await apiClient.get<unknown>('/platform/invoices', {
      params: toListParams({ ...rest, filters: { tenant_id, status } }),
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
};
