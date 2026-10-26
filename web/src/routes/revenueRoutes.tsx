import { lazy, type ReactNode } from 'react';
import { Route } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { recordRoutePattern } from '../navigation/recordRoutes';
import { ROUTES } from '../navigation/routes';

/** Revenue-check pages (DEC-031), code-split like every tenant page. */
const page = <K extends string>(load: () => Promise<Record<K, () => ReactNode>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));

const DailySheetPage = page(
  () => import('../pages/tenant/revenue/DailySheetPage'),
  'DailySheetPage',
);
const DailySheetDayPage = page(
  () => import('../pages/tenant/revenue/DailySheetDayPage'),
  'DailySheetDayPage',
);
const RevenueDifferencesPage = page(
  () => import('../pages/tenant/revenue/RevenueDifferencesPage'),
  'RevenueDifferencesPage',
);
const RevenueReasonsPage = page(
  () => import('../pages/tenant/revenue/RevenueReasonsPage'),
  'RevenueReasonsPage',
);
const NonRevenuePage = page(
  () => import('../pages/tenant/revenue/NonRevenuePage'),
  'NonRevenuePage',
);
const loadRecords = () => import('../pages/tenant/revenue/RevenueRecordPages');
const RevenueDifferenceDetailPage = page(loadRecords, 'RevenueDifferenceDetailPage');
const NonRevenueApprovalDetailPage = page(loadRecords, 'NonRevenueApprovalDetailPage');

type Guard = (permission: string, page: ReactNode) => ReactNode;

/** Routes of the revenue checks; `guard` adds the REVENUE_RECONCILIATION capability and permission. */
export function revenueRouteElements(guard: Guard): ReactNode[] {
  const read = PERMISSIONS.tenantRevenueRead;
  const routes: [string, ReactNode][] = [
    [ROUTES.tenantDailySheet, <DailySheetPage key="s" />],
    [ROUTES.tenantDailySheetDay, <DailySheetDayPage key="sd" />],
    [ROUTES.tenantRevenueDifferences, <RevenueDifferencesPage key="d" />],
    [recordRoutePattern('REVENUE_DIFFERENCE'), <RevenueDifferenceDetailPage key="dd" />],
    [ROUTES.tenantRevenueReasons, <RevenueReasonsPage key="r" />],
    [ROUTES.tenantNonRevenueApprovals, <NonRevenuePage key="n" />],
    [recordRoutePattern('NON_REVENUE_APPROVAL'), <NonRevenueApprovalDetailPage key="nd" />],
  ];
  return routes.map(([path, element]) => (
    <Route key={path} path={path} element={guard(read, element)} />
  ));
}
