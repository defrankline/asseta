import type { MenuDto, MenuGroupDto, MeResponse } from '../api/types';
import { makeMe, TENANT_A } from './fixtures';

/** Tenant groups as `/me` returns them (daily-workflow order). */
export const TENANT_GROUPS: MenuGroupDto[] = [
  { key: 'tenant.overview', label: 'Overview', order: 10 },
  { key: 'tenant.operations', label: 'Operations', order: 20 },
  { key: 'tenant.fleet', label: 'Fleet', order: 30 },
  { key: 'tenant.finance', label: 'Finance', order: 40 },
  { key: 'tenant.admin', label: 'Administration', order: 90 },
];

export const TENANT_MENUS: MenuDto[] = [
  {
    key: 'tenant.dashboard',
    label: 'Dashboard',
    path: '/tenant/dashboard',
    order: 5,
    group: 'tenant.overview',
  },
  {
    key: 'tenant.machines',
    label: 'Machines',
    path: '/tenant/machines',
    order: 20,
    group: 'tenant.fleet',
  },
  {
    key: 'tenant.fleet_map',
    label: 'Fleet map',
    path: '/tenant/fleet',
    order: 10,
    group: 'tenant.overview',
  },
  {
    key: 'tenant.jobs',
    label: 'Jobs',
    path: '/tenant/jobs',
    order: 15,
    group: 'tenant.operations',
  },
  {
    key: 'tenant.customers',
    label: 'Customers',
    path: '/tenant/customers',
    order: 25,
    group: 'tenant.operations',
  },
  {
    key: 'tenant.finance',
    label: 'Hire finance',
    path: '/tenant/finance',
    order: 66,
    group: 'tenant.finance',
  },
  {
    key: 'tenant.policies',
    label: 'Policies',
    path: '/tenant/policies',
    order: 80,
    group: 'tenant.admin',
  },
];

export function makeGroupedTenantMe(
  menus: MenuDto[] = TENANT_MENUS,
  groups: MenuGroupDto[] = TENANT_GROUPS,
): MeResponse {
  const me = makeMe();
  return {
    ...me,
    tenants: me.tenants.map((t) =>
      t.tenant_id === TENANT_A ? { ...t, menus, menu_groups: groups } : t,
    ),
  };
}
