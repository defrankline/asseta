import type { MandateBadgeDto, MandateDetailDto, MeResponse, TenantAccess } from '../api/types';
import { makeMe, TENANT_A, TENANT_B } from './fixtures';

export const MANDATE_ID = '44444444-4444-4444-8444-444444444444';
export const STAFF_ID = '55555555-5555-4555-8555-555555555555';

export const BADGE: MandateBadgeDto = {
  mandate_id: MANDATE_ID,
  reference: 'MSM-2026-0007',
  scope: 'FULL',
  ends_on: null,
};

export function mandatedTenant(overrides: Partial<TenantAccess> = {}): TenantAccess {
  return {
    tenant_id: TENANT_B,
    name: 'Kilimo Haulage',
    status: 'ACTIVE',
    access_state: 'FULL',
    permissions: ['tenant.machine.read'],
    menus: [{ key: 'machines', label: 'Machines', path: '/tenant/machines', order: 1 }],
    mandate: BADGE,
    ...overrides,
  };
}

/** Platform staff: platform permissions plus mandated clients only (as /me returns them). */
export function makePlatformStaffMe(tenants: TenantAccess[] = [mandatedTenant()]): MeResponse {
  return makeMe({
    platform_permissions: ['platform.mandate.read'],
    platform_menus: [
      {
        key: 'platform.managed_service',
        label: 'Managed service',
        path: '/platform/managed-service',
        order: 25,
      },
    ],
    tenants,
  });
}

export function makeMandateDetail(overrides: Partial<MandateDetailDto> = {}): MandateDetailDto {
  return {
    id: MANDATE_ID,
    reference: BADGE.reference,
    tenant_id: TENANT_A,
    tenant_name: 'Tenant A',
    scope: 'FULL',
    starts_on: '2026-10-01',
    ends_on: null,
    consent_reference: 'LTR-889',
    notes: '',
    status: 'IN_FORCE',
    version: 3,
    granted_by: 'owner@asseta.test',
    granted_at: '2026-10-01T08:00:00Z',
    closed_by: null,
    closed_at: null,
    close_reason: null,
    active_staff: 1,
    assignments: [
      {
        id: '66666666-6666-4666-8666-666666666666',
        user_id: STAFF_ID,
        email: 'amina@asseta.test',
        display_name: 'Amina Staff',
        role_key: 'owner',
        assigned_at: '2026-10-01T09:00:00Z',
        removed_at: null,
        is_active: true,
      },
    ],
    ...overrides,
  };
}
