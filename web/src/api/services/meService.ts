import { array, mixed, number, object, string, type Schema } from 'yup';
import { apiClient } from '../client';
import type { MenuDto, MeResponse, TenantAccess, TenantAccessState } from '../types';
import { parseResponse } from '../validation';

const menuSchema: Schema<MenuDto> = object({
  key: string().required(),
  label: string().required(),
  path: string().required(),
  order: number().required(),
});

const tenantSchema: Schema<TenantAccess> = object({
  tenant_id: string().uuid().required(),
  name: string().required(),
  status: mixed<TenantAccess['status']>().oneOf(['ONBOARDING', 'ACTIVE', 'CLOSED']).required(),
  access_state: mixed<TenantAccessState>().oneOf(['FULL', 'READ_ONLY', 'BLOCKED']).required(),
  permissions: array(string().required()).required(),
  menus: array(menuSchema).required(),
});

const meSchema: Schema<MeResponse> = object({
  user_id: string().uuid().required(),
  email: string().required(),
  display_name: string().required(),
  platform_permissions: array(string().required()).required(),
  platform_menus: array(menuSchema).required(),
  tenants: array(tenantSchema).required(),
});

export const meService = {
  async getMe(signal?: AbortSignal): Promise<MeResponse> {
    const data = await apiClient.get<unknown>('/me', signal ? { signal } : undefined);
    return parseResponse(meSchema, data, '/me');
  },
};
