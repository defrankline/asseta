import { apiClient, toListParams } from '../client';
import type {
  ListQuery,
  OnboardResultDto,
  Page,
  SubscriptionDto,
  TenantDto,
  TenantOnboardIn,
  VerificationIn,
} from '../types';
import { parseResponse } from '../validation';
import {
  onboardResultSchema,
  pageSchema,
  subscriptionSchema,
  tenantSchema,
} from './billingSchemas';

const tenantPageSchema = pageSchema(tenantSchema);
const base = '/platform/tenants';

export const tenantService = {
  /** GET /platform/tenants (listTenants). Sort fields: `name`, `created_at` (prefix `-` for desc). */
  async list(query: ListQuery, signal?: AbortSignal): Promise<Page<TenantDto>> {
    const data = await apiClient.get<unknown>(base, {
      params: toListParams(query),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(tenantPageSchema, data, 'tenant page');
  },

  /** GET /platform/tenants/{tenant_id} (getTenant). */
  async get(tenantId: string, signal?: AbortSignal): Promise<TenantDto> {
    const data = await apiClient.get<unknown>(
      `${base}/${encodeURIComponent(tenantId)}`,
      signal ? { signal } : undefined,
    );
    return parseResponse(tenantSchema, data, 'tenant');
  },

  /** POST /platform/tenants (onboardTenant). The response carries a one-time owner password. */
  async onboard(body: TenantOnboardIn, idempotencyKey: string): Promise<OnboardResultDto> {
    const data = await apiClient.post<unknown>(base, body, { idempotencyKey });
    return parseResponse(onboardResultSchema, data, 'onboarding result');
  },

  /** POST /platform/tenants/{tenant_id}/verification (verifyTenant). */
  async verify(tenantId: string, body: VerificationIn, idempotencyKey: string): Promise<TenantDto> {
    const data = await apiClient.post<unknown>(
      `${base}/${encodeURIComponent(tenantId)}/verification`,
      body,
      { idempotencyKey },
    );
    return parseResponse(tenantSchema, data, 'tenant');
  },

  /** GET /platform/tenants/{tenant_id}/subscription (getTenantSubscription). */
  async getSubscription(tenantId: string, signal?: AbortSignal): Promise<SubscriptionDto> {
    const data = await apiClient.get<unknown>(
      `${base}/${encodeURIComponent(tenantId)}/subscription`,
      signal ? { signal } : undefined,
    );
    return parseResponse(subscriptionSchema, data, 'subscription');
  },
};
