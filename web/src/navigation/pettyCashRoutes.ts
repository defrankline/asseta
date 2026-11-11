/**
 * Petty cash paths (DEC-033): backend menus `tenant.petty_cash` (Finance group) and
 * `tenant.field.petty_cash` (Field work group). Record routes mirror the backend's
 * `notification.rules.RECORDS` / `accountability.links.RECORD_ROUTES` (`<list>/<id>`).
 */
const BASE = '/tenant/finance/petty-cash';

export const PETTY_CASH_ROUTES = {
  /** Backend menu `tenant.petty_cash`: the petty cash page (tabs). */
  home: BASE,
  funds: `${BASE}/funds`,
  fundDetail: `${BASE}/funds/:id`,
  movements: `${BASE}/movements`,
  movementDetail: `${BASE}/movements/:id`,
  counts: `${BASE}/counts`,
  countDetail: `${BASE}/counts/:id`,
  holderChanges: `${BASE}/holder-changes`,
  holderChangeDetail: `${BASE}/holder-changes/:id`,
  adjustments: `${BASE}/adjustments`,
  adjustmentDetail: `${BASE}/adjustments/:id`,
  advances: `${BASE}/advances`,
  advanceDetail: `${BASE}/advances/:id`,
  /** Backend menu `tenant.field.petty_cash`: the holder's own funds. */
  field: '/tenant/field/petty-cash',
} as const;

/** Paths with a page in this build (merged into IMPLEMENTED_PATHS). */
export const PETTY_CASH_MENU_PATHS: readonly string[] = [
  PETTY_CASH_ROUTES.home,
  PETTY_CASH_ROUTES.funds,
  PETTY_CASH_ROUTES.movements,
  PETTY_CASH_ROUTES.counts,
  PETTY_CASH_ROUTES.holderChanges,
  PETTY_CASH_ROUTES.adjustments,
  PETTY_CASH_ROUTES.advances,
  PETTY_CASH_ROUTES.field,
];

export type PettyCashRecord =
  'funds' | 'movements' | 'counts' | 'holder-changes' | 'adjustments' | 'advances';

/** The detail page of one petty cash record. */
export function pettyCashPath(kind: PettyCashRecord, id: string): string {
  return `${BASE}/${kind}/${encodeURIComponent(id)}`;
}

export const pettyCashFundPath = (fundId: string): string => pettyCashPath('funds', fundId);

/** Tabs of the petty cash page. */
export type PettyCashTab =
  'funds' | 'fundings' | 'returns' | 'counts' | 'holder-changes' | 'adjustments' | 'advances';

/** The petty cash page on a tab, with optional list filters (e.g. `fund_id`, `status`). */
export function pettyCashTabPath(
  tab: PettyCashTab,
  params: Readonly<Record<string, string | undefined>> = {},
): string {
  const q = new URLSearchParams({ tab });
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') q.set(k, v);
  return `${BASE}?${q.toString()}`;
}

/** Ledger record types (statement / transaction `entity_type`) → their petty cash detail page. */
const ENTITY_RECORD: Readonly<Record<string, PettyCashRecord>> = {
  petty_cash_movement: 'movements',
  petty_cash_count: 'counts',
  petty_cash_adjustment: 'adjustments',
  petty_cash_advance: 'advances',
  petty_cash_holder_change: 'holder-changes',
  petty_cash_fund: 'funds',
};

/** Where a ledger line opens: a petty cash record, or the expense; null when it has no page. */
export function pettyCashEntityPath(entityType: string, entityId: string): string | null {
  const kind = ENTITY_RECORD[entityType];
  if (kind !== undefined) return pettyCashPath(kind, entityId);
  if (entityType === 'expense') return `/tenant/expenses/${encodeURIComponent(entityId)}`;
  if (entityType === 'cash_variance') {
    return `/tenant/finance/cash/variances/${encodeURIComponent(entityId)}`;
  }
  return null;
}
