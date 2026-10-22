import { apiClient, toListParams } from '../client';
import type { SmsWalletDto, SmsWalletEntryPage } from '../types';
import { parseResponse } from '../validation';
import { smsWalletEntryPageSchema, smsWalletSchema } from './commerceSchemas';

/**
 * Tenant SMS wallets (DEC-022): credits from fulfilled SMS bundle lines, debits per SMS segment.
 * `tenantId` = a tenant in the platform console; null = the active tenant (tenant console).
 */
function base(tenantId: string | null): { url: string; tenantScoped: boolean } {
  return tenantId === null
    ? { url: '/tenant/billing/sms-wallet', tenantScoped: true }
    : { url: `/platform/tenants/${encodeURIComponent(tenantId)}/sms-wallet`, tenantScoped: false };
}

export const smsWalletService = {
  /** GET …/sms-wallet (getMySmsWallet / getTenantSmsWallet). */
  async get(tenantId: string | null, signal?: AbortSignal): Promise<SmsWalletDto> {
    const { url, tenantScoped } = base(tenantId);
    const data = await apiClient.get<unknown>(url, { tenantScoped, ...(signal ? { signal } : {}) });
    return parseResponse(smsWalletSchema, data, 'SMS wallet');
  },
  /** GET …/sms-wallet/entries (newest first). */
  async entries(
    tenantId: string | null,
    query: { page: number; page_size: number },
    signal?: AbortSignal,
  ): Promise<SmsWalletEntryPage> {
    const { url, tenantScoped } = base(tenantId);
    const data = await apiClient.get<unknown>(`${url}/entries`, {
      tenantScoped,
      params: toListParams(query),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(smsWalletEntryPageSchema, data, 'SMS wallet entries');
  },
};
