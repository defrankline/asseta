import type { ReactNode } from 'react';
import { Route } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import {
  RECORD_LIST_ROUTES,
  recordRoutePattern,
  type RecordKind,
} from '../navigation/recordRoutes';
import { LegacyCashRedirect } from './LegacyCashRedirect';
import type { CashTabKey } from '../pages/tenant/finance/cash/CashCustodyPage';
import {
  CashCustodyPage,
  CashFloatDetailPage,
  CashRemittanceDetailPage,
  CashRetentionDetailPage,
  CashTransferDetailPage,
  CashVarianceDetailPage,
  CustodyAdjustmentDetailPage,
  RemittanceOverdueDetailPage,
} from './lazyPages';

type Guard = (permission: string, page: ReactNode) => ReactNode;
type GuardAny = (permissions: readonly string[], page: ReactNode) => ReactNode;

/** Field recorders open the records of their own custody; office readers open any. */
const CUSTODY_READERS = [PERMISSIONS.tenantCollectionRecord, PERMISSIONS.tenantFinanceRead];

/** Cash record kinds: their cash custody tab and detail page. */
const CASH_RECORDS: readonly [RecordKind, CashTabKey, ReactNode, boolean][] = [
  ['CASH_TRANSFER', 'transfers', <CashTransferDetailPage key="t" />, true],
  ['CASH_FLOAT', 'floats', <CashFloatDetailPage key="f" />, true],
  ['CASH_REMITTANCE', 'handovers', <CashRemittanceDetailPage key="r" />, true],
  ['CASH_VARIANCE', 'variances', <CashVarianceDetailPage key="v" />, true],
  ['CASH_RETENTION', 'retentions', <CashRetentionDetailPage key="k" />, true],
  ['CUSTODY_ADJUSTMENT', 'adjustments', <CustodyAdjustmentDetailPage key="a" />, true],
  // Overdue flags are an office view (finance read only).
  ['REMITTANCE_OVERDUE', 'overdue', <RemittanceOverdueDetailPage key="o" />, false],
];

/**
 * Cash custody list routes (the cash custody page on that list) and the exact-record detail routes
 * notifications and dashboard rows link to (DEC-030 G5).
 */
export function cashRecordRouteElements(guard: Guard, guardAny: GuardAny): ReactNode[] {
  return [
    ...CASH_RECORDS.flatMap(([kind, tab, detail, fieldToo]) => [
      <Route
        key={`${kind}-list`}
        path={RECORD_LIST_ROUTES[kind]}
        element={guard(PERMISSIONS.tenantFinanceRead, <CashCustodyPage tab={tab} />)}
      />,
      <Route
        key={`${kind}-detail`}
        path={recordRoutePattern(kind)}
        element={
          fieldToo
            ? guardAny(CUSTODY_READERS, detail)
            : guard(PERMISSIONS.tenantFinanceRead, detail)
        }
      />,
    ]),
    <Route key="legacy-cash" path="/tenant/cash/*" element={<LegacyCashRedirect />} />,
  ];
}
