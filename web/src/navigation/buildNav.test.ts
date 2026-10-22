import { describe, expect, it } from 'vitest';
import { makeMe, TENANT_A } from '../test/fixtures';
import { makeGroupedTenantMe, TENANT_MENUS } from '../test/navFixtures';
import { activeGroupKey, buildNav, navItems } from './buildNav';

const TENANT = { kind: 'tenant', tenantId: TENANT_A } as const;
const PLATFORM = { kind: 'platform' } as const;

function tenantOf(me: ReturnType<typeof makeMe>) {
  const [first] = me.tenants;
  if (first === undefined) throw new Error('fixture needs a tenant');
  return first;
}

describe('buildNav', () => {
  it('groups tenant menus parent -> children in group order, Overview first', () => {
    const me = makeGroupedTenantMe();
    const groups = buildNav(TENANT, tenantOf(me), me);
    expect(groups.map((g) => g.label)).toEqual([
      'Overview',
      'Operations',
      'Fleet',
      'Finance',
      'Administration',
    ]);
    expect(groups[1]?.items.map((i) => i.label)).toEqual(['Jobs', 'Customers']);
    // My access joins Administration, last.
    expect(groups.at(-1)?.items.map((i) => i.path)).toEqual(['/tenant/policies', '/me']);
    // The landing page (HomeRedirect) is the first item: the Dashboard, then the Fleet map.
    expect(groups[0]?.items.map((i) => i.label)).toEqual(['Dashboard', 'Fleet map']);
    expect(navItems(groups)[0]?.path).toBe('/tenant/dashboard');
  });

  it('drops groups without visible menus and menus whose group was not listed', () => {
    const finance = TENANT_MENUS.filter((m) => m.group === 'tenant.finance');
    const orphan = {
      key: 'x',
      label: 'Orphan',
      path: '/tenant/x',
      order: 1,
      group: 'tenant.unknown',
    };
    const me = makeGroupedTenantMe([...finance, orphan]);
    const groups = buildNav(TENANT, tenantOf(me), me);
    expect(groups.map((g) => [g.key, g.items.map((i) => i.label)])).toEqual([
      ['tenant.finance', ['Hire finance']],
      ['tenant.admin', ['My access']],
    ]);
  });

  it('orders platform groups with Dashboard as the landing page', () => {
    const me = makeMe({
      platform_permissions: ['platform.tenant.read', 'platform.dashboard.read'],
      platform_menus: [
        {
          key: 'platform.tenants',
          label: 'Tenants',
          path: '/platform/tenants',
          order: 20,
          group: 'platform.tenants',
        },
        {
          key: 'platform.dashboard',
          label: 'Dashboard',
          path: '/platform',
          order: 10,
          group: 'platform.overview',
        },
      ],
      platform_menu_groups: [
        { key: 'platform.tenants', label: 'Tenants', order: 20 },
        { key: 'platform.overview', label: 'Overview', order: 10 },
      ],
    });
    const groups = buildNav(PLATFORM, null, me);
    expect(groups.map((g) => g.key)).toEqual([
      'platform.overview',
      'platform.tenants',
      'platform.admin',
    ]);
    expect(navItems(groups).map((i) => i.path)).toEqual(['/platform', '/platform/tenants', '/me']);
  });

  it('hides tenant menus for BLOCKED tenants', () => {
    const me = makeGroupedTenantMe();
    const blocked = { ...tenantOf(me), access_state: 'BLOCKED' as const };
    expect(navItems(buildNav(TENANT, blocked, me)).map((i) => i.path)).toEqual(['/me']);
    expect(navItems(buildNav({ kind: 'none' }, null, me)).map((i) => i.path)).toEqual(['/me']);
  });

  it('finds the group of the active route by longest path prefix', () => {
    const me = makeGroupedTenantMe();
    const groups = buildNav(TENANT, tenantOf(me), me);
    expect(activeGroupKey(groups, '/tenant/customers/abc')).toBe('tenant.operations');
    expect(activeGroupKey(groups, '/tenant/fleet')).toBe('tenant.overview');
    expect(activeGroupKey(groups, '/tenant/fleetwide')).toBeNull();
  });
});
