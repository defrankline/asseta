import { Box, Button, Paper, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { CAPABILITY, useCapabilityEnabled } from '../../../access/capabilities';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { CanMutate } from '../../../access/CanMutate';
import { useCanMutate } from '../../../access/useCanMutate';
import { cashService } from '../../../api/services/cashService';
import type { CashHandoverDto, CustomerPaymentDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { recordPath } from '../../../navigation/recordRoutes';
import { formatInstantIn } from '../../../utils/time';
import { HandoverDialog } from '../finance/cash/CashDialogs';
import { remittanceAccountText, remittanceMethodText } from '../finance/cash/remittanceDetails';
import { useCashPolicy } from '../finance/cash/custodyHooks';
import { FloatsTab } from '../finance/cash/FloatsTab';
import { RetentionsTab } from '../finance/cash/RetentionsTab';
import { TransactionsDrawer, type DrillDown } from '../finance/cash/TransactionsDrawer';
import { TransfersTab } from '../finance/cash/TransfersTab';
import { BalanceCard } from '../finance/cash/CustodyTab';
import { FormulaCard, ReconciliationFormula } from '../finance/cash/ReconciliationTab';
import {
  SETTLEMENT_LABELS,
  SETTLEMENT_STATUS_OPTIONS,
  SETTLEMENT_TONES,
} from '../shared/financeDisplay';
import { useCustomerLabels } from '../shared/useFinanceLabels';
import { FieldCollectionDialog } from './FieldCollectionDialog';

type TabKey = 'collections' | 'handovers' | 'transfers' | 'floats' | 'retentions';
type Open = 'collection' | 'handover' | null;

/** Tabs of the cash custody controls (DEC-030). */
const CONTROL_TABS: ReadonlySet<TabKey> = new Set(['transfers', 'retentions']);

const settlement = (s: CustomerPaymentDto['status']) => (
  <StatusChip status={s} tones={SETTLEMENT_TONES} label={SETTLEMENT_LABELS[s]} />
);

/** Today's custody and reconciliation for the caller (one entry per currency). */
function MyCustody({ timeZone, reloadKey }: { timeZone: string; reloadKey: number }) {
  const [drill, setDrill] = useState<DrillDown | null>(null);
  const load = useCallback(async (signal: AbortSignal) => {
    const [balances, reconciliation] = await Promise.all([
      cashService.myCustody(signal),
      cashService.myReconciliation(undefined, signal),
    ]);
    return { balances, reconciliation };
  }, []);
  const res = useAsyncResource(load, [reloadKey]);
  return (
    <AsyncContent
      resource={res}
      isEmpty={(d) => d.balances.length === 0 && d.reconciliation.length === 0}
      emptyTitle="No cash in your custody"
      emptyDescription="Floats the office issues to you and cash you collect appear here."
      errorTitle="Could not load your cash custody"
    >
      {(d) => (
        <Stack spacing={2}>
          {d.balances.map((b) => (
            <BalanceCard key={b.currency} b={b} timeZone={timeZone} />
          ))}
          <Typography variant="h6" component="h2">
            Today’s reconciliation
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <ReconciliationFormula />
          </Typography>
          {d.reconciliation.flatMap((r) =>
            r.days.map((day) => (
              <FormulaCard
                key={`${r.currency}-${day.day}`}
                day={day}
                currency={r.currency}
                onFigure={(dayIso, figure) => {
                  setDrill({ from: dayIso, to: dayIso, currency: r.currency, figure });
                }}
              />
            )),
          )}
          {drill !== null && (
            <TransactionsDrawer
              drill={drill}
              timeZone={timeZone}
              onClose={() => {
                setDrill(null);
              }}
            />
          )}
        </Stack>
      )}
    </AsyncContent>
  );
}

/**
 * Field cash (Field work): own custody and today's reconciliation (every figure drills down), the
 * collections and remittances recorded, transfers between custodians, floats to acknowledge and
 * requests to keep cash. Recording for another custodian follows the tenant's CASH_CUSTODY policy.
 */
export function FieldCashPage() {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const customerLabel = useCustomerLabels();
  /** Off: transfers, keep-cash requests and recording for another custodian are hidden. */
  const controlsOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  const [chosenTab, setTab] = useState<TabKey>('collections');
  const tab: TabKey = !controlsOn && CONTROL_TABS.has(chosenTab) ? 'collections' : chosenTab;
  const [status, setStatus] = useState('');
  const [open, setOpen] = useState<Open>(null);
  const policy = useCashPolicy();
  const canOffice = useCanMutate(PERMISSIONS.tenantFinanceCash);
  const forOthers = canOffice || (controlsOn && policy?.recordersMayRecordForOthers === true);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.customerPayment, ENTITY.cashHandover, ENTITY.expense], reload);
  const fetchCollections = useCallback<FetchPage<CustomerPaymentDto>>(
    (query, signal) => cashService.myCollections(query, signal),
    [],
  );
  const navigate = useNavigate();
  const openRemittance = (h: CashHandoverDto) => {
    void navigate(recordPath('CASH_REMITTANCE', h.id));
  };
  const fetchHandovers = useCallback<FetchPage<CashHandoverDto>>(
    (query, signal) => cashService.myHandovers(query, signal),
    [],
  );
  const collectionColumns: DataColumn<CustomerPaymentDto>[] = [
    { id: 'at', header: 'Received', render: (p) => formatInstantIn(p.received_at, timeZone) },
    {
      id: 'customer',
      header: 'Customer',
      render: (p) => p.customer_name ?? customerLabel(p.customer_id),
    },
    { id: 'ref', header: 'Reference', render: (p) => p.reference ?? '—' },
    { id: 'status', header: 'Status', render: (p) => settlement(p.status) },
    { id: 'note', header: 'Office note', render: (p) => p.decision_note ?? '—' },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (p) => <MoneyText amount={p.amount} currency={p.currency} />,
    },
  ];
  const handoverColumns: DataColumn<CashHandoverDto>[] = [
    { id: 'at', header: 'Handed over', render: (h) => formatInstantIn(h.handed_at, timeZone) },
    { id: 'method', header: 'Paid by', render: remittanceMethodText },
    { id: 'account', header: 'Company account', render: remittanceAccountText },
    { id: 'ref', header: 'Reference', render: (h) => h.reference ?? '—' },
    { id: 'status', header: 'Status', render: (h) => settlement(h.status) },
    { id: 'note', header: 'Office note', render: (h) => h.decision_note ?? '—' },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (h) => <MoneyText amount={h.amount} currency={h.currency} />,
    },
  ];
  const done = (message: string) => {
    notify.success(message);
    reload();
  };
  const close = () => {
    setOpen(null);
  };
  return (
    <>
      <PageHeader
        title="Cash"
        subtitle="Cash in your custody, today’s reconciliation, transfers, floats and the collections and remittances you recorded"
        actions={
          <CanMutate permission={PERMISSIONS.tenantCollectionRecord}>
            <Button
              variant="contained"
              onClick={() => {
                setOpen('collection');
              }}
            >
              Record cash collection
            </Button>
            <Button
              variant="outlined"
              onClick={() => {
                setOpen('handover');
              }}
            >
              Remit cash
            </Button>
          </CanMutate>
        }
      />
      <Stack spacing={3}>
        <MyCustody timeZone={timeZone} reloadKey={reloadKey} />
        <Paper variant="outlined">
          <Tabs
            value={tab}
            aria-label="Cash records"
            onChange={(_e, v: TabKey) => {
              setTab(v);
              setStatus('');
            }}
          >
            <Tab value="collections" label="My collections" />
            <Tab value="handovers" label="My remittances" />
            {controlsOn && <Tab value="transfers" label="Transfers" />}
            <Tab value="floats" label="Floats" />
            {controlsOn && <Tab value="retentions" label="Keep cash requests" />}
          </Tabs>
          <Box className="p-3">
            {tab === 'transfers' && <TransfersTab timeZone={timeZone} field />}
            {tab === 'floats' && <FloatsTab timeZone={timeZone} />}
            {tab === 'retentions' && <RetentionsTab timeZone={timeZone} field />}
            {tab === 'collections' && (
              <ServerDataTable
                columns={collectionColumns}
                fetchPage={fetchCollections}
                getRowId={(p) => p.id}
                searchable={false}
                reloadKey={reloadKey}
                filters={{ status: status || undefined }}
                emptyTitle="No cash collections"
                isRowMuted={(p) => p.status === 'REJECTED'}
                toolbar={
                  <StaticSelectFilter
                    label="Status"
                    value={status}
                    options={SETTLEMENT_STATUS_OPTIONS}
                    onChange={setStatus}
                  />
                }
              />
            )}
            {tab === 'handovers' && (
              <ServerDataTable
                columns={handoverColumns}
                fetchPage={fetchHandovers}
                getRowId={(h) => h.id}
                searchable={false}
                reloadKey={reloadKey}
                filters={{ status: status || undefined }}
                emptyTitle="No remittances"
                isRowMuted={(h) => h.status === 'REJECTED'}
                onRowClick={openRemittance}
                toolbar={
                  <StaticSelectFilter
                    label="Status"
                    value={status}
                    options={SETTLEMENT_STATUS_OPTIONS}
                    onChange={setStatus}
                  />
                }
              />
            )}
          </Box>
        </Paper>
      </Stack>
      {open === 'collection' && (
        <FieldCollectionDialog
          timeZone={timeZone}
          forOthers={forOthers}
          onClose={close}
          onRecorded={() => {
            done('Cash collection recorded; it is claimed until the office verifies it.');
          }}
        />
      )}
      {open === 'handover' && (
        <HandoverDialog
          ownCustody={!forOthers}
          timeZone={timeZone}
          onClose={close}
          onRecorded={() => {
            done('Remittance recorded; it is awaiting confirmation until the office counts it.');
          }}
        />
      )}
    </>
  );
}
