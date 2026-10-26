import type { ReactNode } from 'react';
import type { CountAmountDto } from '../../../api/custodyTypes';
import { MoneyText } from '../../../components/display/MoneyText';
import { IMPLEMENTED_PATHS } from '../../../navigation/routes';
import { formatMoney } from '../../../utils/money';
import type { KpiRow } from '../dashboard/KpiCard';

/** Building blocks of the accountability tiles (free-form tile JSON read defensively). */

export type Can = (permission: string) => boolean;

export const pathOnly = (to: string) => to.split('?')[0] ?? to;
/** A link target only when the page exists in this build and the viewer may open it. */
export function linkIf(ok: boolean, to: string, base: string = pathOnly(to)): string | undefined {
  return ok && IMPLEMENTED_PATHS.has(base) ? to : undefined;
}

export const asRecord = (v: unknown): Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
export const asNumber = (v: unknown): number => (typeof v === 'number' ? v : Number(v ?? 0) || 0);
export const asText = (v: unknown, fallback = '0'): string =>
  typeof v === 'string' ? v : typeof v === 'number' ? String(v) : fallback;
export const asList = (v: unknown): Record<string, unknown>[] =>
  Array.isArray(v) ? v.map(asRecord) : [];

export const count = (key: string, label: string, n: number, to?: string): KpiRow => ({
  key,
  label,
  value: n,
  valueText: String(n),
  to,
});

/** One row per currency: "<count> · <amount>". */
export function perCurrency(key: string, rows: readonly CountAmountDto[], to?: string): KpiRow[] {
  return rows.map((r) => ({
    key: `${key}-${r.currency}`,
    label: `${String(r.count)} in ${r.currency}`,
    value: <MoneyText amount={r.amount} currency={r.currency} />,
    valueText: `${String(r.count)}, ${formatMoney(r.amount, r.currency)}`,
    to,
  }));
}

export const totalCount = (rows: readonly CountAmountDto[]) =>
  rows.reduce((n, r) => n + r.count, 0);

export interface Tile {
  key: string;
  title: string;
  value?: ReactNode;
  valueText?: string;
  to?: string | undefined;
  description?: string;
  rows?: KpiRow[];
}
