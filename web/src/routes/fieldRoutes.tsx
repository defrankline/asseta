import type { ReactNode } from 'react';
import { Route } from 'react-router';
import { CAPABILITY, CAPABILITY_FEATURE } from '../access/capabilities';
import { PERMISSIONS } from '../access/permissionCodes';
import { RequireCapability } from '../access/RequireCapability';
import { ROUTES } from '../navigation/routes';
import { FieldCashPage, FieldExpensesPage, FieldFuelPage, FieldReadingsPage } from './lazyPages';

type Guard = (permission: string, page: ReactNode) => ReactNode;

/** Field work pages a supervisor uses from a browser: readings, fuel (when on), expenses, cash. */
export function fieldRouteElements(guard: Guard): ReactNode[] {
  return [
    <Route
      key="readings"
      path={ROUTES.fieldReadings}
      element={guard(PERMISSIONS.tenantMeterCapture, <FieldReadingsPage />)}
    />,
    <Route
      key="fuel"
      path={ROUTES.fieldFuel}
      element={
        <RequireCapability capability={CAPABILITY.fuel} feature={CAPABILITY_FEATURE.FUEL}>
          {guard(PERMISSIONS.tenantExpenseWrite, <FieldFuelPage />)}
        </RequireCapability>
      }
    />,
    <Route
      key="expenses"
      path={ROUTES.fieldExpenses}
      element={guard(PERMISSIONS.tenantExpenseWrite, <FieldExpensesPage />)}
    />,
    <Route
      key="cash"
      path={ROUTES.fieldCash}
      element={guard(PERMISSIONS.tenantCollectionRecord, <FieldCashPage />)}
    />,
  ];
}
