import type { MenuDto, MeResponse, TenantAccess } from '../api/types';
import { isGranted, type ConsoleMode } from '../session/permissions';
import { ACCOUNT_NAV, PLATFORM_NAV, type NavItem } from './routes';

function sortMenus(menus: readonly MenuDto[]): NavItem[] {
  return [...menus]
    .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label))
    .map((m) => ({ key: m.key, label: m.label, path: m.path }));
}

function dedupeByPath(items: readonly NavItem[]): NavItem[] {
  const seen = new Set<string>();
  return items.filter((i) => (seen.has(i.path) ? false : (seen.add(i.path), true)));
}

/**
 * Side navigation for the current mode. Menus are server-filtered (role_menus) and rendered in
 * `order`; built-in platform items are additionally filtered by platform permissions.
 * BLOCKED tenants get no tenant menus. Deny by default.
 */
export function buildNav(
  mode: ConsoleMode,
  activeTenant: TenantAccess | null,
  permissions: ReadonlySet<string>,
  me: MeResponse | null = null,
): NavItem[] {
  let items: NavItem[] = [];
  if (mode.kind === 'tenant' && activeTenant !== null && activeTenant.access_state !== 'BLOCKED') {
    items = sortMenus(activeTenant.menus);
  } else if (mode.kind === 'platform') {
    const builtIn = PLATFORM_NAV.filter((i) => isGranted(permissions, i.permission)).map(
      ({ key, label, path }) => ({ key, label, path }),
    );
    items = dedupeByPath([...sortMenus(me?.platform_menus ?? []), ...builtIn]);
  }
  return [...items, ...ACCOUNT_NAV];
}
