import { describe, expect, it } from 'vitest';
import { makeMe, TENANT_A, TENANT_B } from '../test/fixtures';
import { effectivePermissions, isGranted, resolveInitialMode } from './permissions';

describe('isGranted (deny by default)', () => {
  const granted = new Set(['a.read', 'a.write']);
  it('denies empty requirements and empty grants', () => {
    expect(isGranted(granted, [])).toBe(false);
    expect(isGranted(granted, '')).toBe(false);
    expect(isGranted(new Set(), 'a.read')).toBe(false);
  });
  it('supports all/any matching', () => {
    expect(isGranted(granted, ['a.read', 'b.read'])).toBe(false);
    expect(isGranted(granted, ['a.read', 'b.read'], 'any')).toBe(true);
    expect(isGranted(granted, ['a.read', 'a.write'])).toBe(true);
  });
});

describe('effectivePermissions', () => {
  it('never mixes platform and tenant scopes', () => {
    const me = makeMe({ platform_permissions: ['platform.tenant.read'] });
    expect([...effectivePermissions(me, { kind: 'platform' })]).toEqual(['platform.tenant.read']);
    expect([...effectivePermissions(me, { kind: 'tenant', tenantId: TENANT_A })]).toEqual([
      'tenant.machine.read',
    ]);
  });
  it('grants nothing for unknown or BLOCKED tenants', () => {
    const me = makeMe();
    expect(effectivePermissions(me, { kind: 'tenant', tenantId: TENANT_B }).size).toBe(0);
    const blocked = makeMe({
      tenants: makeMe().tenants.map((t) => ({ ...t, access_state: 'BLOCKED' as const })),
    });
    expect(effectivePermissions(blocked, { kind: 'tenant', tenantId: TENANT_A }).size).toBe(0);
  });
});

describe('resolveInitialMode', () => {
  it('ignores a stored mode the user no longer has', () => {
    const me = makeMe();
    expect(resolveInitialMode(me, { kind: 'platform' })).toEqual({
      kind: 'tenant',
      tenantId: TENANT_A,
    });
    expect(resolveInitialMode(me, { kind: 'tenant', tenantId: TENANT_B })).toEqual({
      kind: 'tenant',
      tenantId: TENANT_A,
    });
  });
  it('falls back to platform, then none', () => {
    expect(
      resolveInitialMode(makeMe({ tenants: [], platform_permissions: ['p.x'] }), null),
    ).toEqual({
      kind: 'platform',
    });
    expect(resolveInitialMode(makeMe({ tenants: [] }), null)).toEqual({ kind: 'none' });
  });
});
