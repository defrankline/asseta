import { CAPABILITY } from '../../../access/capabilities';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';

/** Tiles of the customer hours capability (not shown when the tenant switched it off). */
export const CUSTOMER_HOURS_TILES: ReadonlySet<string> = new Set([
  'customer_hours',
  'hours_awaiting_activation',
]);

/** Tiles of the engine-hour controls (not shown when the tenant switched them off). */
export const ENGINE_HOURS_TILES: ReadonlySet<string> = new Set([
  'engine_hours',
  'unexplained_hours',
  'missing_daily_reports',
]);

/** Tiles of the revenue checks (not shown when the tenant switched them off). */
export const REVENUE_TILES: ReadonlySet<string> = new Set(['revenue_differences']);

/** Tiles that belong wholly to a capability: never mentioned while it is switched off. */
export const CAPABILITY_TILES: Readonly<Record<string, ReadonlySet<string>>> = {
  [CAPABILITY.customerHours]: CUSTOMER_HOURS_TILES,
  [CAPABILITY.engineHours]: ENGINE_HOURS_TILES,
  [CAPABILITY.revenue]: REVENUE_TILES,
};

/** True when the tile belongs to a switched-off capability. */
export function tileOfDisabledCapability(key: string, disabled: ReadonlySet<string>): boolean {
  return [...disabled].some((c) => CAPABILITY_TILES[c]?.has(key) === true);
}

export interface TileOptions {
  /** False when the tenant's policy switches customer hours off (`/me` disabled_capabilities). */
  customerHours?: boolean;
  /** Capabilities switched off (`/me`); merged with the summary's own `disabled_capabilities`. */
  disabled?: Iterable<string>;
}

/** Capabilities switched off for this summary: its own list, `/me`'s, and the explicit flags. */
export function disabledCapabilities(
  s: AccountabilitySummaryDto,
  { customerHours = true, disabled = [] }: TileOptions = {},
): ReadonlySet<string> {
  const off = new Set<string>([...(s.disabled_capabilities ?? []), ...disabled]);
  if (!customerHours) off.add(CAPABILITY.customerHours);
  return off;
}
