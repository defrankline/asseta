import { array, boolean, mixed, number, object, string, type Schema } from 'yup';
import { apiClient } from '../client';
import type { components } from '../generated/schema';
import type { MenuDto, MenuGroupDto, MeResponse, TenantAccess, TenantAccessState } from '../types';
import { parseResponse } from '../validation';
import { optionalMandateBadge } from './mandateSchemas';

const menuSchema: Schema<MenuDto> = object({
  key: string().required(),
  label: string().required(),
  path: string().required(),
  order: number().required(),
  group: string().required(),
});

const menuGroupSchema: Schema<MenuGroupDto> = object({
  key: string().required(),
  label: string().required(),
  order: number().required(),
});

const tenantSchema: Schema<TenantAccess> = object({
  tenant_id: string().uuid().required(),
  name: string().required(),
  status: mixed<TenantAccess['status']>().oneOf(['ONBOARDING', 'ACTIVE', 'CLOSED']).required(),
  access_state: mixed<TenantAccessState>().oneOf(['FULL', 'READ_ONLY', 'BLOCKED']).required(),
  /** Why access is limited (e.g. a requested company closure and its deletion date). */
  access_state_reason: string().nullable().optional(),
  permissions: array(string().required()).required(),
  menus: array(menuSchema).required(),
  menu_groups: array(menuGroupSchema).required(),
  /** Set when platform staff reach this tenant through a managed-service mandate. */
  mandate: optionalMandateBadge(),
  /** Capabilities the tenant's policy switches off (e.g. CUSTOMER_HOURS); their menus are omitted. */
  disabled_capabilities: array(string().required()).optional(),
  /** Go-live checklist figures for the dashboard banner (null without `tenant.setup.read`). */
  setup_complete: boolean().nullable().optional(),
  setup_dismissed: boolean().nullable().optional(),
  setup_percent: number().integer().nullable().optional(),
  setup_steps_done: number().integer().nullable().optional(),
  setup_steps_total: number().integer().nullable().optional(),
});

const meSchema: Schema<MeResponse> = object({
  user_id: string().uuid().required(),
  email: string().required(),
  display_name: string().required(),
  platform_permissions: array(string().required()).required(),
  platform_menus: array(menuSchema).required(),
  platform_menu_groups: array(menuGroupSchema).required(),
  tenants: array(tenantSchema).required(),
});

export type AccountDeletionDto = components['schemas']['AccountDeletionDto'];

const accountDeletionSchema: Schema<AccountDeletionDto> = object({
  user_id: string().uuid().required(),
  display_name: string().required(),
  deleted_at: string().required(),
  companies: array(string().required()).required(),
});

export const meService = {
  async getMe(signal?: AbortSignal): Promise<MeResponse> {
    const data = await apiClient.get<unknown>('/me', signal ? { signal } : undefined);
    return parseResponse(meSchema, data, '/me');
  },
  /**
   * Deletes the signed-in person's login for good; their records stay with each company under an
   * anonymous name. Refused for the last owner of a company and for platform accounts.
   */
  async deleteMyAccount(
    reason: string | null,
    idempotencyKey: string,
  ): Promise<AccountDeletionDto> {
    const body: { confirm: true; reason?: string } = { confirm: true };
    if (reason !== null && reason !== '') body.reason = reason;
    const data = await apiClient.post<unknown>('/me/account-deletion', body, { idempotencyKey });
    return parseResponse(accountDeletionSchema, data, 'account deletion');
  },
};
