/** Customer hours paths (backend `tenant.hours` menu group and the `tenant.field.hours` field menu). */
export const HOURS_ROUTES = {
  purchases: '/tenant/hours/purchases',
  purchaseDetail: '/tenant/hours/purchases/:purchaseId',
  balances: '/tenant/hours/balances',
  ledger: '/tenant/hours/ledger',
  allocations: '/tenant/hours/allocations',
  transfers: '/tenant/hours/transfers',
  cancellations: '/tenant/hours/cancellations',
  discounts: '/tenant/hours/discounts',
  credit: '/tenant/hours/credit',
  walkIns: '/tenant/hours/walk-ins',
  reasons: '/tenant/hours/reasons',
  field: '/tenant/field/hours',
} as const;

/** Paths with a page in this build (merged into IMPLEMENTED_PATHS). */
export const HOURS_MENU_PATHS: readonly string[] = [
  HOURS_ROUTES.purchases,
  HOURS_ROUTES.balances,
  HOURS_ROUTES.ledger,
  HOURS_ROUTES.allocations,
  HOURS_ROUTES.transfers,
  HOURS_ROUTES.cancellations,
  HOURS_ROUTES.discounts,
  HOURS_ROUTES.credit,
  HOURS_ROUTES.walkIns,
  HOURS_ROUTES.reasons,
  HOURS_ROUTES.field,
];

export function hoursPurchasePath(purchaseId: string): string {
  return `${HOURS_ROUTES.purchases}/${encodeURIComponent(purchaseId)}`;
}

/** Ledger page pre-filtered (e.g. one purchase or job). */
export function hoursLedgerPath(filters: Readonly<Record<string, string>>): string {
  const qs = new URLSearchParams(filters).toString();
  return qs === '' ? HOURS_ROUTES.ledger : `${HOURS_ROUTES.ledger}?${qs}`;
}
