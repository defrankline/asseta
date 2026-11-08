/** Routes of the adjustments ledger and its requests (DEC-032 Phase 2). */
export const ADJUSTMENT_ROUTES = {
  ledger: '/tenant/finance/adjustments',
  requests: '/tenant/finance/adjustments/requests',
  entryDetail: '/tenant/finance/adjustments/:entryId',
  requestDetail: '/tenant/finance/adjustments/requests/:requestId',
} as const;

export function adjustmentEntryPath(id: string): string {
  return `${ADJUSTMENT_ROUTES.ledger}/${encodeURIComponent(id)}`;
}

export function adjustmentRequestPath(id: string): string {
  return `${ADJUSTMENT_ROUTES.requests}/${encodeURIComponent(id)}`;
}
