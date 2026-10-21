import { apiClient } from '../client';
import type {
  ChargePreviewDto,
  EnrollAssetIn,
  EnrollmentResultDto,
  InvoiceDto,
  SubscriptionDto,
} from '../types';
import { parseResponse } from '../validation';
import {
  chargePreviewSchema,
  enrollmentResultSchema,
  invoiceSchema,
  subscriptionSchema,
} from './billingSchemas';
import { tenantGet, tenantList, tenantSend } from './tenantRequest';

export const tenantBillingService = {
  /** GET /tenant/billing/subscription (getMySubscription). */
  subscription(signal?: AbortSignal): Promise<SubscriptionDto> {
    return tenantGet('/tenant/billing/subscription', subscriptionSchema, 'subscription', signal);
  },
  /** GET /tenant/billing/invoices (listMyPlatformInvoices). */
  invoices(signal?: AbortSignal): Promise<InvoiceDto[]> {
    return tenantList('/tenant/billing/invoices', invoiceSchema, 'invoices', signal);
  },
  /** POST /tenant/billing/enrollments/preview (previewEnrollment). Read-only; null = no charge. */
  async previewEnrollment(
    body: EnrollAssetIn,
    idempotencyKey: string,
  ): Promise<ChargePreviewDto | null> {
    const data = await apiClient.post<unknown>('/tenant/billing/enrollments/preview', body, {
      tenantScoped: true,
      idempotencyKey,
    });
    return data === null || data === ''
      ? null
      : parseResponse(chargePreviewSchema, data, 'charge preview');
  },
  /** POST /tenant/billing/enrollments (enrollMachine). */
  enroll(body: EnrollAssetIn, idempotencyKey: string): Promise<EnrollmentResultDto> {
    return tenantSend(
      'post',
      '/tenant/billing/enrollments',
      body,
      enrollmentResultSchema,
      'enrollment result',
      idempotencyKey,
    );
  },
};
