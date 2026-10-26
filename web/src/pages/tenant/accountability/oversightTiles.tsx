import { PERMISSIONS } from '../../../access/permissionCodes';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import { OVERSIGHT_ROUTES } from '../../../navigation/oversightRoutes';
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
    rows: [count('jobs', 'Jobs', n, to), ...perCurrency('worth', amounts, to)],
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
    rows: [count('idle', 'Idle', n, to), count('planned', 'With a planned job', planned, to)],
  };
}
