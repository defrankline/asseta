import type { ReactNode } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { AccountabilitySummaryDto, CountAmountDto } from '../../../api/custodyTypes';
import { MoneyText } from '../../../components/display/MoneyText';
import {
  cashTabPath,
  financeTabPath,
  IMPLEMENTED_PATHS,
  machineDetailPath,
  ROUTES,
} from '../../../navigation/routes';
import { withQuery } from '../../../navigation/urlFilters';
import { formatMoney } from '../../../utils/money';
import { humanize } from '../../../utils/text';
import type { KpiRow } from '../dashboard/KpiCard';

export type Can = (permission: string) => boolean;

/** Tile keys of `GET /accountability/summary` (also the OVERSIGHT policy's `hidden_dashboard_tiles`). */
export const TILE_LABELS: Readonly<Record<string, string>> = {
  customer_hours: 'Customer hours',
  hours_awaiting_activation: 'Hours awaiting activation',
  engine_hours: 'Engine-hour reconciliation',
  unexplained_hours: 'Unexplained engine hours',
  missing_daily_reports: 'Missing daily reports',
  investigations: 'Open investigations',
  cash: 'Cash per custodian',
  payments: 'Payments awaiting confirmation',
  discrepancies: 'Open discrepancies',
  unauthorized_attempts: 'Refused attempts',
  outstanding_approvals: 'Outstanding approvals',
};

/** Customer-hours and engine-hour pages live with those modules; link only once they are in this build. */
const HOURS_BALANCES = '/tenant/hours/balances';
const HOURS_PURCHASES = '/tenant/hours/purchases';
const HOURS_READ = 'tenant.hours.read';
/** Engine-hour pages (engine hours module). */
const ENGINE_HOURS = '/tenant/engine-hours';
const ENGINE_UNALLOCATED = '/tenant/engine-hours/unallocated';
const engineMachine = (id: string) => `${ENGINE_HOURS}/machines/${encodeURIComponent(id)}`;

const pathOnly = (to: string) => to.split('?')[0] ?? to;
/** A link target only when the page exists in this build and the viewer may open it. */
function linkIf(ok: boolean, to: string, base: string = pathOnly(to)): string | undefined {
  return ok && IMPLEMENTED_PATHS.has(base) ? to : undefined;
}

const asRecord = (v: unknown): Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
const asNumber = (v: unknown): number => (typeof v === 'number' ? v : Number(v ?? 0) || 0);
const asText = (v: unknown, fallback = '0'): string =>
  typeof v === 'string' ? v : typeof v === 'number' ? String(v) : fallback;
const asList = (v: unknown): Record<string, unknown>[] => (Array.isArray(v) ? v.map(asRecord) : []);

const count = (key: string, label: string, n: number, to?: string): KpiRow => ({
  key,
  label,
  value: n,
  valueText: String(n),
  to,
});

/** One row per currency: "<count> · <amount>". */
function perCurrency(key: string, rows: readonly CountAmountDto[], to?: string): KpiRow[] {
  return rows.map((r) => ({
    key: `${key}-${r.currency}`,
    label: `${String(r.count)} in ${r.currency}`,
    value: <MoneyText amount={r.amount} currency={r.currency} />,
    valueText: `${String(r.count)}, ${formatMoney(r.amount, r.currency)}`,
    to,
  }));
}

const totalCount = (rows: readonly CountAmountDto[]) => rows.reduce((n, r) => n + r.count, 0);

export interface Tile {
  key: string;
  title: string;
  value?: ReactNode;
  valueText?: string;
  to?: string | undefined;
  description?: string;
  rows?: KpiRow[];
}

/** The tiles the summary returned (hidden or unavailable ones are null and skipped), each linking to its list. */
export function buildTiles(s: AccountabilitySummaryDto, can: Can): Tile[] {
  const tiles: Tile[] = [];
  const hoursRead = can(HOURS_READ);
  const machineRead = can(PERMISSIONS.tenantMachineRead);
  const meterRead = can(PERMISSIONS.tenantMeterRead);
  /** Engine-hour pages when this build has them, else the machine pages. */
  const engineList = (sub: string) =>
    linkIf(meterRead, sub) ?? linkIf(machineRead, ROUTES.tenantMachines);
  const engineOne = (id: string) =>
    linkIf(meterRead, engineMachine(id), ENGINE_HOURS) ??
    linkIf(machineRead, machineDetailPath(id), ROUTES.tenantMachines);
  const finance = can(PERMISSIONS.tenantFinanceRead);

  if (s.customer_hours) {
    const h = asRecord(s.customer_hours);
    const to = linkIf(hoursRead, HOURS_BALANCES);
    tiles.push({
      key: 'customer_hours',
      title: TILE_LABELS.customer_hours ?? 'Customer hours',
      value: asText(h.remaining),
      valueText: `${asText(h.remaining)} hours remaining`,
      to,
      description: 'Hours remaining across customers and machines',
      rows: [
        {
          key: 'activated',
          label: 'Activated',
          value: asText(h.activated),
          valueText: asText(h.activated),
          to,
        },
        {
          key: 'consumed',
          label: 'Consumed',
          value: asText(h.consumed),
          valueText: asText(h.consumed),
          to,
        },
        {
          key: 'awaiting',
          label: 'Awaiting activation',
          value: asText(h.awaiting_activation),
          valueText: asText(h.awaiting_activation),
          to: linkIf(hoursRead, HOURS_PURCHASES),
        },
        {
          key: 'expired',
          label: 'Expired',
          value: asText(h.expired),
          valueText: asText(h.expired),
          to,
        },
        count(
          'overruns',
          'Open overruns',
          asNumber(h.open_overruns),
          linkIf(
            can(PERMISSIONS.tenantMeterRead),
            withQuery(ROUTES.tenantExceptions, { status: 'OPEN' }),
          ),
        ),
      ],
    });
  }
  if (s.hours_awaiting_activation) {
    const h = asRecord(s.hours_awaiting_activation);
    const to = linkIf(hoursRead, HOURS_PURCHASES);
    tiles.push({
      key: 'hours_awaiting_activation',
      title: TILE_LABELS.hours_awaiting_activation ?? '',
      value: asText(h.hours),
      valueText: `${asText(h.hours)} hours`,
      to,
      description: 'Purchased hours waiting for confirmed payment or approved credit',
      rows: [
        count(
          'awaiting_payment',
          'Purchases awaiting payment',
          asNumber(h.purchases_awaiting_payment),
          to,
        ),
        count('partly_active', 'Purchases partly active', asNumber(h.purchases_partly_active), to),
      ],
    });
  }
  if (s.engine_hours) {
    const e = asRecord(s.engine_hours);
    const to = engineList(ENGINE_HOURS);
    tiles.push({
      key: 'engine_hours',
      title: TILE_LABELS.engine_hours ?? '',
      value: asNumber(e.machines),
      valueText: `${String(asNumber(e.machines))} machines`,
      to,
      description: 'Machines by reconciliation status',
      rows: Object.entries(asRecord(e.by_status))
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([status, n]) => count(status, humanize(status), asNumber(n), to)),
    });
  }
  if (s.unexplained_hours) {
    const u = asRecord(s.unexplained_hours);
    tiles.push({
      key: 'unexplained_hours',
      title: TILE_LABELS.unexplained_hours ?? '',
      value: asText(u.hours),
      valueText: `${asText(u.hours)} hours`,
      to: engineList(ENGINE_UNALLOCATED),
      description: `${String(asNumber(u.machines))} machines with hours not yet explained`,
      rows: asList(u.items)
        .slice(0, 5)
        .map((i) => ({
          key: asText(i.machine_id, ''),
          label: `${asText(i.machine_code, '')} (oldest ${String(asNumber(i.oldest_open_item_days))} d)`,
          value: asText(i.unexplained_hours),
          valueText: `${asText(i.unexplained_hours)} hours`,
          to: engineOne(asText(i.machine_id, '')),
        })),
    });
  }
  if (s.missing_daily_reports) {
    const m = asRecord(s.missing_daily_reports);
    tiles.push({
      key: 'missing_daily_reports',
      title: TILE_LABELS.missing_daily_reports ?? '',
      value: asNumber(m.count),
      valueText: String(asNumber(m.count)),
      to: engineList(ENGINE_HOURS),
      description: 'Working machines without the daily report by the cut-off',
      rows: asList(m.items)
        .slice(0, 5)
        .map((i) => ({
          key: `${asText(i.machine_id, '')}-${asText(i.day, '')}`,
          label: `${asText(i.machine_code, '')} · ${asText(i.day, '')}`,
          value: humanize(asText(i.basis, '')),
          valueText: humanize(asText(i.basis, '')),
          to: engineOne(asText(i.machine_id, '')),
        })),
    });
  }
  if (s.investigations) {
    const i = s.investigations;
    const caseRead = can(PERMISSIONS.tenantCaseRead);
    tiles.push({
      key: 'investigations',
      title: TILE_LABELS.investigations ?? '',
      value: i.open + i.in_review,
      valueText: String(i.open + i.in_review),
      to: linkIf(caseRead, ROUTES.tenantCases),
      rows: [
        count(
          'open',
          'Open',
          i.open,
          linkIf(caseRead, withQuery(ROUTES.tenantCases, { status: 'OPEN' })),
        ),
        count(
          'in_review',
          'In review',
          i.in_review,
          linkIf(caseRead, withQuery(ROUTES.tenantCases, { status: 'IN_REVIEW' })),
        ),
      ],
    });
  }
  if (s.cash) {
    const c = s.cash;
    tiles.push({
      key: 'cash',
      title: TILE_LABELS.cash ?? '',
      value: c.custodians.length,
      valueText: `${String(c.custodians.length)} custodians`,
      to: linkIf(finance, cashTabPath('supervisors')),
      description: 'Outstanding cash held, per custodian',
      rows: c.custodians.slice(0, 6).map((r) => ({
        key: `${r.staff_member_id}-${r.currency}`,
        label: r.staff_name,
        value: <MoneyText amount={r.outstanding} currency={r.currency} />,
        valueText: formatMoney(r.outstanding, r.currency),
        to: linkIf(finance, cashTabPath('custody', { staff_member_id: r.staff_member_id })),
      })),
    });
    tiles.push({
      key: 'cash_pending',
      title: 'Cash awaiting acknowledgement or confirmation',
      value:
        totalCount(c.transfers_awaiting_acknowledgement) +
        totalCount(c.floats_awaiting_acknowledgement) +
        totalCount(c.remittances_awaiting_confirmation),
      valueText: 'items',
      rows: [
        ...perCurrency(
          'transfers',
          c.transfers_awaiting_acknowledgement,
          linkIf(finance, cashTabPath('transfers', { status: 'PENDING_ACKNOWLEDGEMENT' })),
        ).map((r) => ({ ...r, label: `Transfers: ${r.label}` })),
        ...perCurrency(
          'floats',
          c.floats_awaiting_acknowledgement,
          linkIf(finance, cashTabPath('floats')),
        ).map((r) => ({ ...r, label: `Floats: ${r.label}` })),
        ...perCurrency(
          'remittances',
          c.remittances_awaiting_confirmation,
          linkIf(finance, cashTabPath('handovers')),
        ).map((r) => ({ ...r, label: `Remittances: ${r.label}` })),
        count(
          'partial',
          'Partial remittances (window)',
          c.partial_remittances_in_window,
          linkIf(finance, cashTabPath('handovers')),
        ),
      ],
    });
  }
  if (s.payments) {
    const p = s.payments;
    const to = linkIf(finance, financeTabPath('payments'));
    tiles.push({
      key: 'payments',
      title: TILE_LABELS.payments ?? '',
      value: totalCount(p.awaiting_confirmation),
      valueText: String(totalCount(p.awaiting_confirmation)),
      to,
      rows: perCurrency('payments', p.awaiting_confirmation, to),
    });
  }
  if (s.discrepancies) {
    const d = s.discrepancies;
    const variances = linkIf(finance, cashTabPath('variances', { status: 'OPEN' }));
    tiles.push({
      key: 'discrepancies',
      title: TILE_LABELS.discrepancies ?? '',
      value: totalCount(d.open_variances) + d.write_offs_proposed + d.sync_conflicts_unresolved,
      valueText: String(
        totalCount(d.open_variances) + d.write_offs_proposed + d.sync_conflicts_unresolved,
      ),
      rows: [
        ...perCurrency('variances', d.open_variances, variances).map((r) => ({
          ...r,
          label: `Open variances: ${r.label}`,
        })),
        count(
          'writeoffs',
          'Write-offs proposed',
          d.write_offs_proposed,
          linkIf(finance, cashTabPath('variances', { status: 'WRITE_OFF_PROPOSED' })),
        ),
        count(
          'sync',
          'Offline operations to review',
          d.sync_conflicts_unresolved,
          linkIf(can(PERMISSIONS.tenantSyncConflictRead), ROUTES.tenantSyncConflicts),
        ),
      ],
    });
  }
  if (s.unauthorized_attempts) {
    const a = s.unauthorized_attempts;
    const ok = can(PERMISSIONS.tenantSecurityEventRead);
    tiles.push({
      key: 'unauthorized_attempts',
      title: TILE_LABELS.unauthorized_attempts ?? '',
      value: a.permission_denied + a.segregation_of_duties,
      valueText: String(a.permission_denied + a.segregation_of_duties),
      to: linkIf(ok, ROUTES.tenantSecurityEvents),
      description: `Last ${String(a.window_days)} days`,
      rows: [
        count(
          'denied',
          'Missing permission',
          a.permission_denied,
          linkIf(ok, withQuery(ROUTES.tenantSecurityEvents, { kind: 'PERMISSION_DENIED' })),
        ),
        count(
          'sod',
          'Own record (segregation of duties)',
          a.segregation_of_duties,
          linkIf(ok, withQuery(ROUTES.tenantSecurityEvents, { kind: 'SEGREGATION_OF_DUTIES' })),
        ),
      ],
    });
  }
  if (s.outstanding_approvals) {
    const o = s.outstanding_approvals;
    tiles.push({
      key: 'outstanding_approvals',
      title: TILE_LABELS.outstanding_approvals ?? '',
      value: o.total,
      valueText: String(o.total),
      rows: [
        count(
          'requests',
          'Approval requests',
          o.approval_requests,
          linkIf(can(PERMISSIONS.tenantApprovalRead), ROUTES.tenantApprovals),
        ),
        count(
          'payments',
          'Payments to confirm',
          o.payments_to_verify,
          linkIf(finance, financeTabPath('payments')),
        ),
        count(
          'remittances',
          'Remittances to confirm',
          o.remittances_to_verify,
          linkIf(finance, cashTabPath('handovers')),
        ),
        count(
          'retentions',
          'Cash retentions',
          o.cash_retentions,
          linkIf(finance, cashTabPath('retentions', { status: 'PENDING' })),
        ),
        count(
          'adjustments',
          'Custody adjustments',
          o.custody_adjustments,
          linkIf(finance, cashTabPath('adjustments', { status: 'PENDING' })),
        ),
        count(
          'writeoffs',
          'Write-offs',
          o.write_offs,
          linkIf(finance, cashTabPath('variances', { status: 'WRITE_OFF_PROPOSED' })),
        ),
      ],
    });
  }
  return tiles;
}
