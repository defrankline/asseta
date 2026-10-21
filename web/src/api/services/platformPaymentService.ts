import { apiClient, toListParams } from '../client';
import type { ListQuery, Page, PaymentDecisionIn, PaymentDto, RecordPaymentIn } from '../types';
import { parseResponse } from '../validation';
import { pageSchema, paymentSchema } from './billingSchemas';

const paymentPageSchema = pageSchema(paymentSchema);

export interface PaymentListQuery extends ListQuery {
  invoice_id?: string;
}

export const platformPaymentService = {
  /** GET /platform/payments (listPlatformPayments). Server filter: invoice_id. */
  async list(query: PaymentListQuery, signal?: AbortSignal): Promise<Page<PaymentDto>> {
    const { invoice_id, ...rest } = query;
    const data = await apiClient.get<unknown>('/platform/payments', {
      params: toListParams({ ...rest, filters: { invoice_id } }),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(paymentPageSchema, data, 'payment page');
  },

  /** POST /platform/payments (recordPlatformPayment). */
  async record(body: RecordPaymentIn, idempotencyKey: string): Promise<PaymentDto> {
    const data = await apiClient.post<unknown>('/platform/payments', body, { idempotencyKey });
    return parseResponse(paymentSchema, data, 'payment');
  },

  /** POST /platform/payments/{payment_id}/decision (decidePlatformPayment): verify or reject. */
  async decide(
    paymentId: string,
    body: PaymentDecisionIn,
    idempotencyKey: string,
  ): Promise<PaymentDto> {
    const data = await apiClient.post<unknown>(
      `/platform/payments/${encodeURIComponent(paymentId)}/decision`,
      body,
      { idempotencyKey },
    );
    return parseResponse(paymentSchema, data, 'payment');
  },
};
