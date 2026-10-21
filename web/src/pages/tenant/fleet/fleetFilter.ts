import type { Connectivity, MachineMapDto } from '../../../api/types';

/** Fleet map / live status auto-refresh period. */
export const FLEET_REFRESH_MS = 30_000;

export type ConnectivityFilter = Connectivity | 'ALL';

/** Client-side filter (the fleet map endpoint is unpaged): connectivity + free text. */
export function filterFleet(
  machines: readonly MachineMapDto[],
  search: string,
  connectivity: ConnectivityFilter,
): MachineMapDto[] {
  const q = search.trim().toLowerCase();
  return machines.filter((m) => {
    if (connectivity !== 'ALL' && m.connectivity !== connectivity) return false;
    if (q === '') return true;
    return [m.asset_code, m.name, m.operator ?? '', m.supervisor ?? ''].some((v) =>
      v.toLowerCase().includes(q),
    );
  });
}

export function hasPosition(m: MachineMapDto): boolean {
  return m.longitude !== null && m.latitude !== null;
}
