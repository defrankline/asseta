import { PERMISSIONS } from '../../../access/permissionCodes';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import { OVERSIGHT_ROUTES } from '../../../navigation/oversightRoutes';
import { machineDetailPath } from '../../../navigation/routes';
import type { KpiRow } from '../dashboard/KpiCard';
import { asList, asNumber, asRecord, asText, count, linkIf, type Can, type Tile } from './tileKit';

const daysText = (v: unknown, prefix: string) =>
  v === null || v === undefined ? undefined : `${prefix} ${String(asNumber(v))} days`;

/** Item lines shown on a tile (the rest are on the list page). */
const ITEM_LINES = 5;

/** "<code> <name>" for a machine, falling back to whichever is present. */
const machineLabel = (i: Record<string, unknown>) =>
  [asText(i.machine_code, ''), asText(i.machine_name, '')].filter((x) => x !== '').join(' ');

/** One line per idle machine: "TR-01 Tractor", value its idle days. */
function idleItems(items: Record<string, unknown>[], canMachine: boolean): KpiRow[] {
  return items.slice(0, ITEM_LINES).map((i) => {
    const machineId = asText(i.machine_id, '');
    const name = machineLabel(i);
    const valueText = `${String(asNumber(i.idle_days))} days`;
    return {
      key: `machine-${machineId}`,
      label: name === '' ? 'Machine' : name,
      value: valueText,
      valueText,
      to: canMachine && machineId !== '' ? machineDetailPath(machineId) : undefined,
    };
  });
}

/**
 * Idle machines (DEC-031 M2): active machines with no approved machine-report hours and no engine
 * hours for the company's days.
 */
export function idleMachinesTile(s: AccountabilitySummaryDto, can: Can): Tile | null {
  if (!s.idle_machines) return null;
  const i = asRecord(s.idle_machines);
  const to = linkIf(can(PERMISSIONS.tenantOversightRead), OVERSIGHT_ROUTES.idleMachines);
  const n = asNumber(i.count);
  const after = i.after_days;
  return {
    key: 'idle_machines',
    title: 'Idle machines',
    value: n,
    valueText: String(n),
    to,
    description:
      daysText(i.longest_idle_days, 'Longest idle') ??
      (after === null || after === undefined
        ? 'Active machines without work'
        : `No reported work or engine hours for ${String(asNumber(after))} days`),
    rows: [
      count('idle', 'Idle', n, to),
      ...idleItems(asList(i.items), can(PERMISSIONS.tenantMachineRead)),
    ],
  };
}
