import { lazy, type ReactNode } from 'react';
import { Route } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { ADJUSTMENT_ROUTES } from '../navigation/adjustmentRoutes';

/** Adjustments ledger pages (DEC-032 Phase 2), code-split like every tenant page. */
const page = <K extends string>(load: () => Promise<Record<K, () => ReactNode>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));

const AdjustmentsLedgerPage = page(
  () => import('../pages/tenant/finance/adjustments/AdjustmentsLedgerPage'),
  'AdjustmentsLedgerPage',
);
const AdjustmentRequestsPage = page(
  () => import('../pages/tenant/finance/adjustments/AdjustmentRequestsPage'),
  'AdjustmentRequestsPage',
);
const loadDetail = () => import('../pages/tenant/finance/adjustments/AdjustmentDetailPages');
const AdjustmentEntryDetailPage = page(loadDetail, 'AdjustmentEntryDetailPage');
const AdjustmentRequestDetailPage = page(loadDetail, 'AdjustmentRequestDetailPage');

type Guard = (permission: string, page: ReactNode) => ReactNode;

/** The ledger, its requests and one page per record (notifications open the request). */
export function adjustmentRouteElements(guard: Guard): ReactNode[] {
  const routes: [string, ReactNode][] = [
    [ADJUSTMENT_ROUTES.ledger, <AdjustmentsLedgerPage key="l" />],
    [ADJUSTMENT_ROUTES.requests, <AdjustmentRequestsPage key="r" />],
    [ADJUSTMENT_ROUTES.requestDetail, <AdjustmentRequestDetailPage key="rd" />],
    [ADJUSTMENT_ROUTES.entryDetail, <AdjustmentEntryDetailPage key="ed" />],
  ];
  return routes.map(([path, element]) => (
    <Route key={path} path={path} element={guard(PERMISSIONS.tenantAdjustmentRead, element)} />
  ));
}
