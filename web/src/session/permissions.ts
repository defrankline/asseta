import type { MeResponse, TenantAccess } from '../api/types';

/** Which console the user is operating: platform (owner) scopes or a single tenant's scopes. */
export type ConsoleMode =
  { kind: 'platform' } | { kind: 'tenant'; tenantId: string } | { kind: 'none' };

export const NO_MODE: ConsoleMode = { kind: 'none' };

export function canUsePlatformConsole(me: MeResponse | null): boolean {
  return me !== null && me.platform_permissions.length > 0;
}

export function findTenant(me: MeResponse | null, tenantId: string): TenantAccess | null {
  return me?.tenants.find((t) => t.tenant_id === tenantId) ?? null;
}

/** True when the mode is still valid for this user (tenant membership / platform permissions). */
export function isModeAllowed(me: MeResponse | null, mode: ConsoleMode): boolean {
  if (mode.kind === 'platform') return canUsePlatformConsole(me);
  if (mode.kind === 'tenant') return findTenant(me, mode.tenantId) !== null;
  return false;
}

/** Pick the starting mode: stored preference if still allowed, else first tenant, else platform. */
export function resolveInitialMode(me: MeResponse, stored: ConsoleMode | null): ConsoleMode {
  if (stored !== null && isModeAllowed(me, stored)) return stored;
  const first = me.tenants[0];
  if (first !== undefined) return { kind: 'tenant', tenantId: first.tenant_id };
  if (canUsePlatformConsole(me)) return { kind: 'platform' };
  return NO_MODE;
}

/**
 * Permissions in effect for the current mode. Platform and tenant scopes never mix:
 * platform permissions apply only in platform mode, tenant permissions only for the active tenant.
 */
export function effectivePermissions(
  me: MeResponse | null,
  mode: ConsoleMode,
): ReadonlySet<string> {
  if (me === null) return new Set();
  if (mode.kind === 'platform') return new Set(me.platform_permissions);
  if (mode.kind === 'tenant') {
    const tenant = findTenant(me, mode.tenantId);
    // BLOCKED tenants grant nothing client-side; the API enforces the same.
    if (tenant === null || tenant.access_state === 'BLOCKED') return new Set();
    return new Set(tenant.permissions);
  }
  return new Set();
}

export type PermissionRequirement = string | readonly string[];

/**
 * Deny by default: empty/unknown requirements and empty permission sets never grant access.
 * `match: 'all'` (default) requires every code; `'any'` requires at least one.
 */
export function isGranted(
  granted: ReadonlySet<string>,
  required: PermissionRequirement,
  match: 'all' | 'any' = 'all',
): boolean {
  const codes = (typeof required === 'string' ? [required] : required).filter(
    (c) => c.trim() !== '',
  );
  if (codes.length === 0 || granted.size === 0) return false;
  return match === 'all' ? codes.every((c) => granted.has(c)) : codes.some((c) => granted.has(c));
}

export function serializeMode(mode: ConsoleMode): string {
  return mode.kind === 'tenant' ? `tenant:${mode.tenantId}` : mode.kind;
}

export function parseMode(raw: string | null): ConsoleMode | null {
  if (raw === null) return null;
  if (raw === 'platform') return { kind: 'platform' };
  if (raw.startsWith('tenant:') && raw.length > 'tenant:'.length) {
    return { kind: 'tenant', tenantId: raw.slice('tenant:'.length) };
  }
  return null;
}
