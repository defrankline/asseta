import Add from '@mui/icons-material/Add';
import { Alert, Box, Button, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { CanMutate } from '../../../../access/CanMutate';
import { customerPaymentService } from '../../../../api/services/financeService';
import type {
  CustomerDto,
  CustomerPaymentDto,
  SettlementStatus,
  StaffDto,
} from '../../../../api/types';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { ServerDataTable } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import { DetailsDrawer } from '../../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import {
  PAYMENT_METHOD_LABELS,
  SETTLEMENT_LABELS,
  SETTLEMENT_TONES,
  shortId,
} from '../../shared/financeDisplay';
import { PersonName } from '../../shared/PersonName';
import { CustomerFilter, StaffFilter } from '../../shared/financePickers';
import { useCustomerLabels, useStaffLabels } from '../../shared/useFinanceLabels';
import { unallocatedOf } from './paymentForm';
import { RecordPaymentDialog } from './RecordPaymentDialog';
import { SOD_RECORDER_NOTE, usePaymentActions } from './usePaymentActions';
import { ENTITY } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';

type View = SettlementStatus | 'ALL';

/** Status views: claimed (reported, not settled) and verified (settled) are never mixed by default. */
const VIEW_HELP: Readonly<Record<View, string>> = {
  CLAIMED:
    'Claimed: recorded but not yet verified. These do NOT reduce customer balances or supervisor accountability yet.',
  VERIFIED:
    'Verified: confirmed received by someone other than the recorder. These settle balances.',
  REJECTED: 'Rejected: not received; any allocations were released.',
  ALL: 'All payments. Check each status: only VERIFIED money settles balances.',
};

function PaymentDrawer({
  payment: p,
  timeZone,
  actions,
  mine,
  onClose,
}: {
  payment: CustomerPaymentDto;
  timeZone: string;
  actions: ReturnType<typeof usePaymentActions>['actionsFor'];
  mine: boolean;
  onClose: () => void;
}) {
  const customerLabel = useCustomerLabels();
  const staffLabel = useStaffLabels();
  return (
    <DetailsDrawer
      title={`Payment ${p.reference ?? shortId(p.id)}`}
      status={
        <StatusChip
          status={p.status}
          tones={SETTLEMENT_TONES}
          label={SETTLEMENT_LABELS[p.status]}
        />
      }
      actions={
        <ActionButtons actions={actions(p).filter((a) => a.key !== 'view')} primaryKey="decide" />
      }
      onClose={onClose}
    >
      {mine && p.status === 'CLAIMED' && <Alert severity="info">{SOD_RECORDER_NOTE}</Alert>}
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Customer', value: customerLabel(p.customer_id) },
          { label: 'Amount', value: <MoneyText amount={p.amount} currency={p.currency} strong /> },
          {
            label: 'Unallocated',
            value: <MoneyText amount={unallocatedOf(p)} currency={p.currency} />,
          },
          { label: 'Method', value: PAYMENT_METHOD_LABELS[p.method] },
          { label: 'Reference', value: p.reference ?? '—' },
          { label: 'Received at', value: formatInstantIn(p.received_at, timeZone) },
          { label: 'Received by', value: staffLabel(p.received_by_staff_id) },
          { label: 'Source', value: p.source },
          { label: 'Recorded by', value: <PersonName userId={p.recorded_by} /> },
          { label: 'Recorded at', value: formatInstantIn(p.recorded_at, timeZone) },
          { label: 'Decided by', value: <PersonName userId={p.verified_by} /> },
          {
            label: 'Decided at',
            value: p.verified_at === null ? '—' : formatInstantIn(p.verified_at, timeZone),
          },
          { label: 'Decision note', value: p.decision_note ?? '—' },
          { label: 'Note', value: p.note ?? '—' },
        ]}
      />
      <Typography variant="subtitle2">Allocations</Typography>
      <StaticTable
        ariaLabel="Allocations"
        rows={p.allocations}
        getRowId={(a) => a.id}
        isRowMuted={(a) => a.released_at !== null}
        columns={[
          { id: 'inv', header: 'Invoice', render: (a) => shortId(a.invoice_id) },
          {
            id: 'amt',
            header: 'Amount',
            align: 'right',
            render: (a) => <MoneyText amount={a.amount} currency={p.currency} />,
          },
          {
            id: 'rel',
            header: 'Released',
            render: (a) => (a.released_at === null ? 'Active' : (a.release_reason ?? 'Released')),
          },
        ]}
      />
    </DetailsDrawer>
  );
}

/** Customer payments: claimed vs verified views, record, allocate, verify / reject (SoD). */
export function PaymentsTab({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const customerLabel = useCustomerLabels();
  const [view, setView] = useState<View>('CLAIMED');
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [recording, setRecording] = useState(false);
  const [viewing, setViewing] = useState<CustomerPaymentDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.customerPayment], liveReload);
  const changed = (p: CustomerPaymentDto) => {
    setReloadKey((k) => k + 1);
    setViewing((v) => (v?.id === p.id ? p : v));
  };
  const { actionsFor, dialogs, isMine } = usePaymentActions({
    onChanged: changed,
    onView: setViewing,
  });
  const fetchPage = useCallback<FetchPage<CustomerPaymentDto>>(
    (query, signal) => customerPaymentService.list(query, signal),
    [],
  );
  const columns: DataColumn<CustomerPaymentDto>[] = [
    { id: 'received', header: 'Received', render: (p) => formatInstantIn(p.received_at, timeZone) },
    { id: 'customer', header: 'Customer', render: (p) => customerLabel(p.customer_id) },
    { id: 'method', header: 'Method', render: (p) => PAYMENT_METHOD_LABELS[p.method] },
    { id: 'ref', header: 'Reference', render: (p) => p.reference ?? '—' },
    {
      id: 'status',
      header: 'Status',
      render: (p) => (
        <StatusChip
          status={p.status}
          tones={SETTLEMENT_TONES}
          label={SETTLEMENT_LABELS[p.status]}
        />
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (p) => <MoneyText amount={p.amount} currency={p.currency} />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (p) => (
        <RowActionsMenu label={`payment ${p.reference ?? shortId(p.id)}`} actions={actionsFor(p)} />
      ),
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      <Box className="flex flex-wrap items-center gap-3">
        <ToggleButtonGroup
          exclusive
          size="small"
          value={view}
          aria-label="Payment status"
          onChange={(_e, v: View | null) => {
            if (v !== null) setView(v);
          }}
        >
          <ToggleButton value="CLAIMED">Claimed (unverified)</ToggleButton>
          <ToggleButton value="VERIFIED">Verified</ToggleButton>
          <ToggleButton value="REJECTED">Rejected</ToggleButton>
          <ToggleButton value="ALL">All</ToggleButton>
        </ToggleButtonGroup>
        <Box className="flex-1" />
        <CanMutate permission={PERMISSIONS.tenantFinancePayment}>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              setRecording(true);
            }}
          >
            Record payment
          </Button>
        </CanMutate>
      </Box>
      <Alert severity={view === 'CLAIMED' ? 'warning' : 'info'}>{VIEW_HELP[view]}</Alert>
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(p) => p.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{
          status: view === 'ALL' ? undefined : view,
          customer_id: customer?.id,
          staff_member_id: staff?.id,
        }}
        emptyTitle="No payments"
        isRowMuted={(p) => p.status === 'REJECTED'}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-wrap gap-3">
            <Box sx={{ minWidth: 240 }}>
              <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
            </Box>
            <Box sx={{ minWidth: 220 }}>
              <StaffFilter label="Received by" value={staff} onChange={setStaff} />
            </Box>
          </Box>
        }
      />
      {viewing !== null && (
        <PaymentDrawer
          payment={viewing}
          timeZone={timeZone}
          actions={actionsFor}
          mine={isMine(viewing)}
          onClose={() => {
            setViewing(null);
          }}
        />
      )}
      {recording && (
        <RecordPaymentDialog
          timeZone={timeZone}
          onClose={() => {
            setRecording(false);
          }}
          onRecorded={(p) => {
            notify.success('Payment recorded as CLAIMED; it counts once verified.');
            setView('CLAIMED');
            changed(p);
          }}
        />
      )}
      {dialogs}
    </Box>
  );
}
