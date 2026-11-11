import type { ReactNode } from 'react';
import { Route } from 'react-router';
import { CAPABILITY, CAPABILITY_FEATURE } from '../access/capabilities';
import { PERMISSIONS } from '../access/permissionCodes';
import { RequireCapability } from '../access/RequireCapability';
import { PETTY_CASH_ROUTES } from '../navigation/pettyCashRoutes';
import {
  FieldPettyCashPage,
  PettyCashAdjustmentDetailPage as AdjustmentDetail,
  PettyCashAdvanceDetailPage as AdvanceDetail,
  PettyCashCountDetailPage as CountDetail,
  PettyCashFundDetailPage as FundDetailPage,
  PettyCashHolderChangeDetailPage as HolderChangeDetail,
  PettyCashMovementDetailPage as MovementDetail,
  PettyCashPage,
} from './lazyPages';

type Guard = (permission: string, page: ReactNode) => ReactNode;

/**
 * Routes of the petty cash pages. Each needs `tenant.pettycash.read` (holders reach their own
 * funds only; the server applies it) and shows a plain "not enabled" state while the tenant's
 * PETTY_CASH capability is off.
 */
export function pettyCashRouteElements(guard: Guard): ReactNode[] {
  const R = PETTY_CASH_ROUTES;
  const routes: [string, ReactNode][] = [
    [R.home, <PettyCashPage key="home" />],
    [R.funds, <PettyCashPage key="funds" tab="funds" />],
    [R.fundDetail, <FundDetailPage key="fund" />],
    [R.movements, <PettyCashPage key="movements" tab="fundings" />],
    [R.movementDetail, <MovementDetail key="movement" />],
    [R.counts, <PettyCashPage key="counts" tab="counts" />],
    [R.countDetail, <CountDetail key="count" />],
    [R.holderChanges, <PettyCashPage key="changes" tab="holder-changes" />],
    [R.holderChangeDetail, <HolderChangeDetail key="change" />],
    [R.adjustments, <PettyCashPage key="adjustments" tab="adjustments" />],
    [R.adjustmentDetail, <AdjustmentDetail key="adjustment" />],
    [R.advances, <PettyCashPage key="advances" tab="advances" />],
    [R.advanceDetail, <AdvanceDetail key="advance" />],
    [R.field, <FieldPettyCashPage key="field" />],
  ];
  return routes.map(([path, element]) => (
    <Route
      key={path}
      path={path}
      element={
        <RequireCapability
          capability={CAPABILITY.pettyCash}
          feature={CAPABILITY_FEATURE[CAPABILITY.pettyCash]}
        >
          {guard(PERMISSIONS.tenantPettyCashRead, element)}
        </RequireCapability>
      }
    />
  ));
}
