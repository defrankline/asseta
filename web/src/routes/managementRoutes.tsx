import { lazy, type ReactNode } from 'react';
import { Route } from 'react-router';
import { CAPABILITY } from '../access/capabilities';
import { PERMISSIONS } from '../access/permissionCodes';
import { RequireCapability } from '../access/RequireCapability';
import { ROUTES } from '../navigation/routes';
import {
  AlertsPage,
  ApprovalsPage,
  ExceptionsPage,
  ExpensesPage,
  MeterResetsPage,
  SecurityEventsPage,
} from './lazyPages';

/** Management view (DEC-032 Phase 4) and the record links its figures carry (guideline 8 and 10). */
const page = <K extends string>(load: () => Promise<Record<K, () => ReactNode>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));

const PendingAdjustmentsPage = page(
  () => import('../pages/tenant/accountability/PendingAdjustmentsPage'),
  'PendingAdjustmentsPage',
);
const EmployeeAccountabilityPage = page(
  () => import('../pages/tenant/accountability/EmployeeAccountabilityPage'),
  'EmployeeAccountabilityPage',
);
const LookupResultsPage = page(
  () => import('../pages/tenant/lookup/LookupResultsPage'),
  'LookupResultsPage',
);
const CustomerPaymentsPage = page(
  () => import('../pages/tenant/finance/payments/CustomerPaymentsPage'),
  'CustomerPaymentsPage',
);
const CustomerPaymentDetailPage = page(
  () => import('../pages/tenant/finance/payments/CustomerPaymentDetailPage'),
  'CustomerPaymentDetailPage',
);

type Guard = (permission: string, page: ReactNode) => ReactNode;

/**
 * Pending adjustments, the employee view, the reference lookup, customer payments, and record links of
 * lists without a page per record: the list opens with that record's dialog or drawer.
 */
export function managementRouteElements(guard: Guard): ReactNode[] {
  const routes: [string, string, ReactNode][] = [
    [
      ROUTES.tenantPendingAdjustments,
      PERMISSIONS.tenantAccountabilityRead,
      <PendingAdjustmentsPage key="p" />,
    ],
    [
      ROUTES.tenantEmployeeAccountability,
      PERMISSIONS.tenantAccountabilityEmployeeRead,
      <EmployeeAccountabilityPage key="e" />,
    ],
    [ROUTES.tenantLookup, PERMISSIONS.tenantLookupRead, <LookupResultsPage key="l" />],
    [
      ROUTES.tenantCustomerPayments,
      PERMISSIONS.tenantFinanceRead,
      <CustomerPaymentsPage key="c" />,
    ],
    [
      ROUTES.tenantCustomerPaymentDetail,
      PERMISSIONS.tenantFinanceRead,
      <CustomerPaymentDetailPage key="cd" />,
    ],
    [
      `${ROUTES.tenantExceptions}/:focusId`,
      PERMISSIONS.tenantMeterRead,
      <ExceptionsPage key="x" />,
    ],
    [
      `${ROUTES.tenantApprovals}/:focusId`,
      PERMISSIONS.tenantApprovalRead,
      <ApprovalsPage key="a" />,
    ],
    [
      `${ROUTES.tenantExpenses}/:expenseId`,
      PERMISSIONS.tenantExpenseRead,
      <ExpensesPage key="ex" />,
    ],
    [
      `${ROUTES.tenantSecurityEvents}/:focusId`,
      PERMISSIONS.tenantSecurityEventRead,
      <SecurityEventsPage key="s" />,
    ],
    [
      `${ROUTES.tenantMeterResets}/:focusId`,
      PERMISSIONS.tenantMeterApprove,
      <MeterResetsPage key="m" />,
    ],
  ];
  return [
    ...routes.map(([path, permission, element]) => (
      <Route key={path} path={path} element={guard(permission, element)} />
    )),
    <Route
      key="alert"
      path={`${ROUTES.tenantAlerts}/:focusId`}
      element={
        <RequireCapability capability={CAPABILITY.tracking} feature="Tracking">
          {guard(PERMISSIONS.tenantFleetRead, <AlertsPage />)}
        </RequireCapability>
      }
    />,
  ];
}
