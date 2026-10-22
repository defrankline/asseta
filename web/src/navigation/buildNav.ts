import type { MenuDto, MenuGroupDto, MeResponse, TenantAccess } from '../api/types';
import type { ConsoleMode } from '../session/permissions';
import { ACCOUNT_GROUP, ACCOUNT_NAV, type NavGroup, type NavItem } from './routes';

function sortMenus(menus: readonly MenuDto[]): MenuDto[] {
  return [...menus].sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
}

/**
 * Parent -> children navigation: server groups in `order`, each holding its menus in `order`.
 * Groups without a visible menu are dropped; a menu whose group the server did not list is never shown
 * (deny by default).
 */
function groupMenus(groups: readonly MenuGroupDto[], menus: readonly MenuDto[]): NavGroup[] {
  const sorted = sortMenus(menus);
  return [...groups]
    .sort((a, b) => a.order - b.order)
    .map((g) => ({
      key: g.key,
      label: g.label,
      items: sorted
        .filter((m) => m.group === g.key)
        .map(({ key, label, path }): NavItem => ({ key, label, path })),
    }))
    .filter((g) => g.items.length > 0);
}

/** Web-only account links (no feature permission) join the console's Administration group, last. */
function withAccountLinks(groups: NavGroup[], groupKey: string): NavGroup[] {
  const host = groups.find((g) => g.key === groupKey);
  if (host === undefined)
    return [...groups, { ...ACCOUNT_GROUP, key: groupKey, items: [...ACCOUNT_NAV] }];
  return groups.map((g) => (g === host ? { ...g, items: [...g.items, ...ACCOUNT_NAV] } : g));
}

/**
 * Side navigation for the current mode. Menus and their groups are server-filtered by permission
 * (`/me`); BLOCKED tenants get no tenant menus. The first item is the console's landing page.
 */
export function buildNav(
  mode: ConsoleMode,
  activeTenant: TenantAccess | null,
  me: MeResponse | null = null,
): NavGroup[] {
  if (mode.kind === 'tenant') {
    const tenant =
      activeTenant !== null && activeTenant.access_state !== 'BLOCKED' ? activeTenant : null;
    return withAccountLinks(
      groupMenus(tenant?.menu_groups ?? [], tenant?.menus ?? []),
      'tenant.admin',
    );
  }
  if (mode.kind === 'platform') {
    return withAccountLinks(
      groupMenus(me?.platform_menu_groups ?? [], me?.platform_menus ?? []),
      'platform.admin',
    );
  }
  return withAccountLinks([], 'account');
}

export function navItems(groups: readonly NavGroup[]): NavItem[] {
  return groups.flatMap((g) => g.items);
}

/** Key of the group whose item best matches `pathname` (longest path prefix), or null. */
export function activeGroupKey(groups: readonly NavGroup[], pathname: string): string | null {
  let best: { key: string; length: number } | null = null;
  for (const g of groups) {
    for (const i of g.items) {
      const hit = pathname === i.path || pathname.startsWith(i.path === '/' ? '/' : `${i.path}/`);
      if (hit && (best === null || i.path.length > best.length)) {
        best = { key: g.key, length: i.path.length };
      }
    }
  }
  return best?.key ?? null;
}
