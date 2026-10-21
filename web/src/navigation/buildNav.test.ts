import { describe, expect, it } from 'vitest';
import { effectivePermissions } from '../session/permissions';
import { makeMe, TENANT_A } from '../test/fixtures';
import { buildNav } from './buildNav';

describe('buildNav', () => {
  it('uses ordered platform_menus plus permitted built-ins in platform mode', () => {
    const me = makeMe({
      platform_permissions: ['platform.system.read'],
      platform_menus: [
        { key: 'b', label: 'Billing', path: '/platform/billing', order: 2 },
        { key: 't', label: 'Tenants', path: '/platform/tenants', order: 1 },
      ],
    });
    const mode = { kind: 'platform' } as const;
    const paths = buildNav(mode, null, effectivePermissions(me, mode), me).map((i) => i.path);
    expect(paths).toEqual(['/platform/tenants', '/platform/billing', '/platform/system', '/me']);
  });

  it('hides tenant menus for BLOCKED tenants', () => {
    const me = makeMe();
    const [first] = me.tenants;
    if (first === undefined) throw new Error('fixture needs a tenant');
    const tenant = { ...first, access_state: 'BLOCKED' as const };
    const mode = { kind: 'tenant', tenantId: TENANT_A } as const;
    expect(buildNav(mode, tenant, new Set(), me).map((i) => i.path)).toEqual(['/me']);
    expect(buildNav(mode, first, new Set(), me).map((i) => i.path)).toEqual(['/machines', '/me']);
  });
});
