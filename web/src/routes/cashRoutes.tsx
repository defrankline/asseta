import type { ReactNode } from 'react';
import { Route } from 'react-router';
import { CAPABILITY, CAPABILITY_FEATURE, RECORD_KIND_CAPABILITY } from '../access/capabilities';
import { PERMISSIONS } from '../access/permissionCodes';
import { RequireAnyCapability, RequireCapability } from '../access/RequireCapability';
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
  // Field users open their own overdue flag (custodian or that day's recorder); the list is office-only.
  ['REMITTANCE_OVERDUE', 'overdue', <RemittanceOverdueDetailPage key="o" />, true],
];

/** Records of the cash custody controls (DEC-030) show the "not enabled" state when switched off. */
function gated(kind: RecordKind, page: ReactNode, detail = false): ReactNode {
  if (detail && kind === 'CASH_VARIANCE') {
    // Petty cash differences are variances too: their page stays open while petty cash is on,
    // even with the cash custody controls off (the server gates each variance by its source).
    return (
      <RequireAnyCapability
        capabilities={[CAPABILITY.cashCustody, CAPABILITY.pettyCash]}
        feature={CAPABILITY_FEATURE[CAPABILITY.cashCustody]}
      >
        {page}
      </RequireAnyCapability>
    );
  }
  const capability = RECORD_KIND_CAPABILITY[kind];
  return capability === undefined ? (
    page
  ) : (
    <RequireCapability capability={capability} feature={CAPABILITY_FEATURE[capability]}>
      {page}
    </RequireCapability>
  );
}

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
        element={gated(kind, guard(PERMISSIONS.tenantFinanceRead, <CashCustodyPage tab={tab} />))}
      />,
      <Route
        key={`${kind}-detail`}
        path={recordRoutePattern(kind)}
        element={gated(
          kind,
          fieldToo
            ? guardAny(CUSTODY_READERS, detail)
            : guard(PERMISSIONS.tenantFinanceRead, detail),
          true,
        )}
      />,
    ]),
    <Route key="legacy-cash" path="/tenant/cash/*" element={<LegacyCashRedirect />} />,
  ];
}
