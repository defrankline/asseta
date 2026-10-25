import { Navigate, useLocation } from 'react-router';
import { RECORD_LIST_ROUTES } from '../navigation/recordRoutes';
import { ROUTES } from '../navigation/routes';

/** Older notification links used `/tenant/cash/<list>`; open the same list on the console path. */
const LEGACY_CASH: Readonly<Record<string, string>> = {
  handovers: RECORD_LIST_ROUTES.CASH_REMITTANCE,
  transfers: RECORD_LIST_ROUTES.CASH_TRANSFER,
  floats: RECORD_LIST_ROUTES.CASH_FLOAT,
  variances: RECORD_LIST_ROUTES.CASH_VARIANCE,
  retentions: RECORD_LIST_ROUTES.CASH_RETENTION,
  adjustments: RECORD_LIST_ROUTES.CUSTODY_ADJUSTMENT,
};

export function LegacyCashRedirect() {
  const { pathname } = useLocation();
  const rest = pathname.replace(/^\/tenant\/cash\/?/, '').split('/');
  const list = LEGACY_CASH[rest[0] ?? ''];
  const target =
    list === undefined ? ROUTES.tenantCashCustody : rest[1] ? `${list}/${rest[1]}` : list;
  return <Navigate replace to={target} />;
}
