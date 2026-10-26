import { PERMISSIONS } from '../../../access/permissionCodes';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import { OVERSIGHT_ROUTES } from '../../../navigation/oversightRoutes';
import { jobDetailPath, machineDetailPath } from '../../../navigation/routes';
import { formatMoney } from '../../../utils/money';
import type { KpiRow } from '../dashboard/KpiCard';
import {
  asList,
  asNumber,
  asRecord,
  asText,
  count,
  linkIf,
  perCurrency,
  type Can,
  type Tile,
} from './tileKit';

const daysText = (v: unknown, prefix: string) =>
  v === null || v === undefined ? undefined : `${prefix} ${String(asNumber(v))} days`;

/** Item lines shown on a tile (the rest are on the list page). */
const ITEM_LINES = 5;

/** "<code> <name>" for a machine, falling back to whichever is present. */
const machineLabel = (i: Record<string, unknown>) =>
  [asText(i.machine_code, ''), asText(i.machine_name, '')].filter((x) => x !== '').join(' ');

/** One line per unbilled job: "J-001 · Customer · TR-01", value the job's worth (or its days). */
function unbilledItems(items: Record<string, unknown>[], canJob: boolean): KpiRow[] {
  return items.slice(0, ITEM_LINES).map((i) => {
    const jobId = asText(i.job_id, '');
    const label = [asText(i.job_number, ''), asText(i.customer_name, ''), machineLabel(i)]
      .filter((x) => x !== '')
      .join(' · ');
    const days = `${String(asNumber(i.days_unbilled))} days`;
    const total = i.total === null || i.total === undefined ? null : asText(i.total);
    const valueText =
      total === null ? days : `${formatMoney(total, asText(i.currency, ''))}, ${days}`;
    return {
      key: `job-${jobId}`,
      label: label === '' ? 'Job' : label,
      value: valueText,
      valueText,
      to: canJob && jobId !== '' ? jobDetailPath(jobId) : undefined,
    };
  });
}

/** One line per idle machine: "TR-01 Tractor (planned J-002)", value its idle days. */
function idleItems(items: Record<string, unknown>[], canMachine: boolean): KpiRow[] {
  return items.slice(0, ITEM_LINES).map((i) => {
    const machineId = asText(i.machine_id, '');
    const planned = asText(i.planned_job_number, '');
    const name = machineLabel(i);
    const valueText = `${String(asNumber(i.idle_days))} days`;
    return {
      key: `machine-${machineId}`,
      label: `${name === '' ? 'Machine' : name}${planned === '' ? '' : ` (planned ${planned})`}`,
      value: valueText,
      valueText,
      to: canMachine && machineId !== '' ? machineDetailPath(machineId) : undefined,
    };
  });
}

/** Unbilled work (DEC-031 M2): completed, billing-ready jobs not invoiced after the company's days. */
export function unbilledWorkTile(s: AccountabilitySummaryDto, can: Can): Tile | null {
  if (!s.unbilled_work) return null;
  const u = asRecord(s.unbilled_work);
  const to = linkIf(can(PERMISSIONS.tenantOversightRead), OVERSIGHT_ROUTES.unbilledWork);
  const n = asNumber(u.count);
  const after = u.after_days;
  const amounts = asList(u.amounts).map((a) => ({
    currency: asText(a.currency, ''),
    count: asNumber(a.count),
    amount: asText(a.amount),
  }));
  return {
    key: 'unbilled_work',
    title: 'Unbilled work',
    value: n,
    valueText: String(n),
    to,
    description:
      daysText(u.oldest_days, 'Oldest') ??
      (after === null || after === undefined
        ? 'Completed jobs not yet invoiced'
        : `Completed jobs not invoiced after ${String(asNumber(after))} days`),
    rows: [
      count('jobs', 'Jobs', n, to),
      ...perCurrency('worth', amounts, to),
      ...unbilledItems(asList(u.items), can(PERMISSIONS.tenantJobRead)),
    ],
  };
}

/** Idle machines (DEC-031 M2): active machines with no job and no engine hours for the company's days. */
export function idleMachinesTile(s: AccountabilitySummaryDto, can: Can): Tile | null {
  if (!s.idle_machines) return null;
  const i = asRecord(s.idle_machines);
  const to = linkIf(can(PERMISSIONS.tenantOversightRead), OVERSIGHT_ROUTES.idleMachines);
  const n = asNumber(i.count);
  const planned = asList(i.items).filter((m) => typeof m.planned_job_id === 'string').length;
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
        : `No job or engine hours for ${String(asNumber(after))} days`),
    rows: [
      count('idle', 'Idle', n, to),
      count('planned', 'With a planned job', planned, to),
      ...idleItems(asList(i.items), can(PERMISSIONS.tenantMachineRead)),
    ],
  };
}
