import { Button } from '@mui/material';
import { Link as RouterLink, useParams } from 'react-router';
import { CAPABILITY, useCapabilityEnabled } from '../../../../access/capabilities';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import type { CashHandoverDto, CashCustodyEntryDto } from '../../../../api/types';
import type {
  CashRetentionDto,
  CashTransferDto,
  CashVarianceDto,
  CustodyAdjustmentDto,
  RemittanceOverdueDto,
} from '../../../../api/custodyTypes';
import { custodyService } from '../../../../api/services/custodyService';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { RECORD_LIST_ROUTES, type RecordKind } from '../../../../navigation/recordRoutes';
import { cashTabPath, ROUTES } from '../../../../navigation/routes';
import { useSession } from '../../../../session/useSession';
import { formatDate } from '../../../../utils/dates';
import { RecordDetail } from '../../shared/RecordDetail';
import { useRecordById } from '../../shared/useRecordById';
import {
  adjustmentChip,
  adjustmentCustodian,
  adjustmentHistory,
  adjustmentItems,
  useAdjustmentActions,
} from './adjustmentRecord';
import { ADJUSTMENT_KIND_LABELS, VARIANCE_KIND_LABELS } from './custodyDisplay';
import {
  floatChip,
  floatCustodian,
  floatHistory,
  floatItems,
  floatKind,
  useFloatActions,
} from './floatRecord';
import {
  remittanceChip,
  remittanceCustodian,
  remittanceHistory,
  remittanceItems,
  useRemittanceActions,
} from './remittanceRecord';
import { overdueCustodian, overdueHistory, overdueItems } from './remittanceOverdueRecord';
import {
  retentionChip,
  retentionCustodian,
  retentionHistory,
  retentionItems,
  useRetentionActions,
} from './retentionRecord';
import {
  transferChip,
  transferFrom,
  transferHistory,
  transferItems,
  transferTo,
  useTransferActions,
} from './transferRecord';
import {
  useVarianceActions,
  varianceChip,
  varianceCustodian,
  varianceHistory,
  varianceItems,
} from './varianceRecord';

/** Stable loaders (bound to the service) for `useRecordById`. */
const load = {
  transfer: (id: string, signal: AbortSignal) => custodyService.transfer(id, signal),
  float: (id: string, signal: AbortSignal) => custodyService.float(id, signal),
  handover: (id: string, signal: AbortSignal) => custodyService.handover(id, signal),
  variance: (id: string, signal: AbortSignal) => custodyService.variance(id, signal),
  retention: (id: string, signal: AbortSignal) => custodyService.retention(id, signal),
  adjustment: (id: string, signal: AbortSignal) => custodyService.adjustment(id, signal),
  remittanceOverdueFlag: (id: string, signal: AbortSignal) =>
    custodyService.remittanceOverdueFlag(id, signal),
};

const LIST_LABELS: Readonly<Partial<Record<RecordKind, string>>> = {
  CASH_TRANSFER: 'Cash transfers',
  CASH_FLOAT: 'Floats',
  CASH_VARIANCE: 'Variances',
  CASH_RETENTION: 'Retentions',
  CUSTODY_ADJUSTMENT: 'Custody adjustments',
  CASH_REMITTANCE: 'Remittances',
  REMITTANCE_OVERDUE: 'Overdue remittances',
};

/** Office readers go back to the cash list; field recorders to their own cash page. */
function useBack(kind: RecordKind) {
  const { hasPermission } = useSession();
  return hasPermission(PERMISSIONS.tenantFinanceRead)
    ? { label: LIST_LABELS[kind] ?? 'Cash custody', to: RECORD_LIST_ROUTES[kind] }
    : { label: 'My cash', to: ROUTES.fieldCash };
}

/** /tenant/finance/cash/transfers/:id */
export function CashTransferDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const res = useRecordById(load.transfer, id);
  const { actionsFor, dialog } = useTransferActions(res.reload);
  return (
    <>
      <RecordDetail<CashTransferDto>
        resource={res}
        what="cash transfer"
        back={useBack('CASH_TRANSFER')}
        timeZone={timeZone}
        title={(t) => `Cash transfer · ${transferFrom(t)} → ${transferTo(t)}`}
        status={transferChip}
        actions={actionsFor}
        primaryKey="answer"
        items={(t) => transferItems(t, timeZone, hasPermission(PERMISSIONS.tenantFinanceRead))}
        history={transferHistory}
      />
      {dialog}
    </>
  );
}

/** /tenant/finance/cash/floats/:id */
export function CashFloatDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.float, id);
  const { actionsFor, dialog } = useFloatActions(res.reload);
  const controlsOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  return (
    <>
      <RecordDetail<CashCustodyEntryDto>
        resource={res}
        what="cash float"
        back={useBack('CASH_FLOAT')}
        timeZone={timeZone}
        title={(e) => `${floatKind(e)} · ${floatCustodian(e)}`}
        {...(controlsOn ? { status: floatChip } : {})}
        actions={actionsFor}
        primaryKey="answer"
        items={(e) => floatItems(e, timeZone, controlsOn)}
        history={(e) => floatHistory(e, controlsOn)}
      />
      {dialog}
    </>
  );
}

/** /tenant/finance/cash/remittances/:id */
export function CashRemittanceDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.handover, id);
  const { actionsFor, dialog } = useRemittanceActions(res.reload);
  const controlsOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  return (
    <>
      <RecordDetail<CashHandoverDto>
        resource={res}
        what="remittance"
        back={useBack('CASH_REMITTANCE')}
        timeZone={timeZone}
        title={(h) => `Remittance · ${remittanceCustodian(h)}`}
        status={remittanceChip}
        actions={actionsFor}
        primaryKey="decide"
        items={(h) => remittanceItems(h, timeZone, controlsOn)}
        history={remittanceHistory}
      />
      {dialog}
    </>
  );
}

/** /tenant/finance/cash/variances/:id */
export function CashVarianceDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const res = useRecordById(load.variance, id);
  const { actionsFor, dialog } = useVarianceActions(res.reload);
  return (
    <>
      <RecordDetail<CashVarianceDto>
        resource={res}
        what="cash variance"
        back={useBack('CASH_VARIANCE')}
        timeZone={timeZone}
        title={(v) => `Cash variance · ${varianceCustodian(v)}`}
        subtitle={(v) => VARIANCE_KIND_LABELS[v.kind]}
        status={varianceChip}
        actions={actionsFor}
        primaryKey="resolve"
        items={(v) => varianceItems(v, timeZone, hasPermission(PERMISSIONS.tenantCaseRead))}
        history={varianceHistory}
      />
      {dialog}
    </>
  );
}

/** /tenant/finance/cash/retentions/:id */
export function CashRetentionDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.retention, id);
  const { actionsFor, dialog } = useRetentionActions(res.reload);
  return (
    <>
      <RecordDetail<CashRetentionDto>
        resource={res}
        what="cash retention"
        back={useBack('CASH_RETENTION')}
        timeZone={timeZone}
        title={(r) => `Request to keep cash · ${retentionCustodian(r)}`}
        status={retentionChip}
        actions={actionsFor}
        primaryKey="decide"
        items={(r) => retentionItems(r, timeZone)}
        history={retentionHistory}
      />
      {dialog}
    </>
  );
}

/** /tenant/finance/cash/adjustments/:id */
export function CustodyAdjustmentDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.adjustment, id);
  const { actionsFor, dialog } = useAdjustmentActions(res.reload);
  return (
    <>
      <RecordDetail<CustodyAdjustmentDto>
        resource={res}
        what="custody adjustment"
        back={useBack('CUSTODY_ADJUSTMENT')}
        timeZone={timeZone}
        title={(a) => `${ADJUSTMENT_KIND_LABELS[a.kind]} · ${adjustmentCustodian(a)}`}
        status={adjustmentChip}
        actions={actionsFor}
        primaryKey="decide"
        items={(a) => adjustmentItems(a, timeZone)}
        history={adjustmentHistory}
      />
      {dialog}
    </>
  );
}

/** /tenant/finance/cash/remittance-overdue/:id */
export function RemittanceOverdueDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.remittanceOverdueFlag, id);
  return (
    <RecordDetail<RemittanceOverdueDto>
      resource={res}
      what="overdue remittance"
      back={useBack('REMITTANCE_OVERDUE')}
      timeZone={timeZone}
      title={(o) => `Remittance overdue · ${overdueCustodian(o)} · ${formatDate(o.local_day)}`}
      links={(o) => (
        <div className="flex flex-wrap gap-2">
          <Button
            size="small"
            variant="outlined"
            component={RouterLink}
            to={cashTabPath('custody', { staff_member_id: o.staff_member_id })}
          >
            Open custody
          </Button>
          <Button
            size="small"
            variant="outlined"
            component={RouterLink}
            to={RECORD_LIST_ROUTES.CASH_REMITTANCE}
          >
            Remittances
          </Button>
        </div>
      )}
      items={(o) => overdueItems(o, timeZone)}
      history={(o) => overdueHistory(o, timeZone)}
    />
  );
}
