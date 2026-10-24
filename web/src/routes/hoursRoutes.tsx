import { lazy, type ReactNode } from 'react';
import { Route } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { HOURS_ROUTES } from '../navigation/hoursRoutes';

/** Customer hours pages (accountability design A), code-split like every tenant page. */
const page = <K extends string>(load: () => Promise<Record<K, () => ReactNode>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));

const HoursPurchasesPage = page(
  () => import('../pages/tenant/hours/HoursPurchasesPage'),
  'HoursPurchasesPage',
);
const HoursPurchaseDetailPage = page(
  () => import('../pages/tenant/hours/HoursPurchaseDetailPage'),
  'HoursPurchaseDetailPage',
);
const HoursBalancesPage = page(
  () => import('../pages/tenant/hours/HoursBalancesPage'),
  'HoursBalancesPage',
);
const HoursLedgerPage = page(
  () => import('../pages/tenant/hours/HoursLedgerPage'),
  'HoursLedgerPage',
);
const WorkAllocationsPage = page(
  () => import('../pages/tenant/hours/WorkAllocationsPage'),
  'WorkAllocationsPage',
);
const HoursTransfersPage = page(
  () => import('../pages/tenant/hours/HoursTransfersPage'),
  'HoursTransfersPage',
);
const HoursCancellationsPage = page(
  () => import('../pages/tenant/hours/HoursCancellationsPage'),
  'HoursCancellationsPage',
);
const CustomerDiscountsPage = page(
  () => import('../pages/tenant/hours/CustomerDiscountsPage'),
  'CustomerDiscountsPage',
);
const CreditArrangementsPage = page(
  () => import('../pages/tenant/hours/CreditArrangementsPage'),
  'CreditArrangementsPage',
);
const WalkInCustomersPage = page(
  () => import('../pages/tenant/hours/WalkInCustomersPage'),
  'WalkInCustomersPage',
);
const HoursReasonsPage = page(
  () => import('../pages/tenant/hours/HoursReasonsPage'),
  'HoursReasonsPage',
);
const FieldHoursPage = page(() => import('../pages/tenant/hours/FieldHoursPage'), 'FieldHoursPage');

type Guard = (permission: string, page: ReactNode) => ReactNode;

/** Route elements for the customer hours pages; each is permission-guarded (deny by default). */
export function hoursRouteElements(guard: Guard): ReactNode[] {
  const read = PERMISSIONS.tenantHoursRead;
  const routes: [string, string, ReactNode][] = [
    [HOURS_ROUTES.purchases, read, <HoursPurchasesPage key="p" />],
    [HOURS_ROUTES.purchaseDetail, read, <HoursPurchaseDetailPage key="pd" />],
    [HOURS_ROUTES.balances, read, <HoursBalancesPage key="b" />],
    [HOURS_ROUTES.ledger, read, <HoursLedgerPage key="l" />],
    [HOURS_ROUTES.allocations, read, <WorkAllocationsPage key="a" />],
    [HOURS_ROUTES.transfers, read, <HoursTransfersPage key="t" />],
    [HOURS_ROUTES.cancellations, read, <HoursCancellationsPage key="c" />],
    [HOURS_ROUTES.discounts, read, <CustomerDiscountsPage key="d" />],
    [HOURS_ROUTES.credit, read, <CreditArrangementsPage key="cr" />],
    [HOURS_ROUTES.walkIns, read, <WalkInCustomersPage key="w" />],
    [HOURS_ROUTES.reasons, read, <HoursReasonsPage key="r" />],
    [HOURS_ROUTES.field, PERMISSIONS.tenantHoursPurchase, <FieldHoursPage key="f" />],
  ];
  return routes.map(([path, permission, element]) => (
    <Route key={path} path={path} element={guard(permission, element)} />
  ));
}
