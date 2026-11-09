import Add from '@mui/icons-material/Add';
import { Alert, Box, Button, Link, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router';
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
import type { FetchPage } from '../../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import { DetailsDrawer } from '../../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { adjustmentRequestPath } from '../../../../navigation/adjustmentRoutes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import {
  PAYMENT_METHOD_LABELS,
  SETTLEMENT_LABELS,
  SETTLEMENT_TONES,
  shortId,
} from '../../shared/financeDisplay';
import { CustomerFilter, StaffFilter } from '../../shared/financePickers';
import { useCustomerLabels, useStaffLabels } from '../../shared/useFinanceLabels';
import { PaymentAllocations, ReversedChip } from './PaymentParts';
import { paymentItems } from './paymentRecord';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { initialFilter } from '../../../../navigation/urlFilters';
import { urlPeriod } from '../../shared/urlPeriod';
import { UrlPeriodChip } from '../../shared/UrlPeriodChip';
import { PAYMENT_METHOD_OPTIONS } from '../../shared/financeDisplay';
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
      title={`Payment ${p.collection_number ?? p.reference ?? shortId(p.id)}`}
      status={
        <Box component="span" className="inline-flex flex-wrap gap-1">
          <StatusChip
            status={p.status}
            tones={SETTLEMENT_TONES}
            label={SETTLEMENT_LABELS[p.status]}
          />
          <ReversedChip payment={p} />
        </Box>
      }
      actions={
        <ActionButtons actions={actions(p).filter((a) => a.key !== 'view')} primaryKey="decide" />
      }
      onClose={onClose}
    >
      {mine && p.status === 'CLAIMED' && <Alert severity="info">{SOD_RECORDER_NOTE}</Alert>}
      {p.reversed_at != null && (
        <Alert severity="warning">
          Reversed {formatInstantIn(p.reversed_at, timeZone)}. This money no longer counts for the
          customer.{' '}
          {p.reversal_id != null && (
            <Link component={RouterLink} to={adjustmentRequestPath(p.reversal_id)}>
              Open the reversal
            </Link>
          )}
        </Alert>
      )}
      <KeyValueGrid columns={2} items={paymentItems(p, timeZone, customerLabel, staffLabel)} />
      <PaymentAllocations payment={p} />
    </DetailsDrawer>
  );
}

/** Customer payments: claimed vs verified views, record, allocate, verify / reject (SoD). */
export function PaymentsTab({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const customerLabel = useCustomerLabels();
  const [params, setParams] = useSearchParams();
  const linkedPaymentId = params.get('payment_id');
  const { dateFrom, dateTo } = urlPeriod(params);
  const [view, setView] = useState<View>(() => {
    const s = params.get('status');
    if (s === 'CLAIMED' || s === 'VERIFIED' || s === 'REJECTED' || s === 'ALL') return s;
    const filtered = linkedPaymentId !== null || params.has('method') || dateFrom !== undefined;
    return filtered || dateTo !== undefined ? 'ALL' : 'CLAIMED';
  });
  const [method, setMethod] = useState(() =>
    initialFilter(params, 'method', PAYMENT_METHOD_OPTIONS, ''),
  );
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [recording, setRecording] = useState(false);
  const [viewing, setViewing] = useState<CustomerPaymentDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    if (linkedPaymentId === null) return undefined;
    const controller = new AbortController();
    customerPaymentService
      .get(linkedPaymentId, controller.signal)
      .then(setViewing)
      .catch((err: unknown) => {
        if (!controller.signal.aborted) notify.error(err, 'Could not open that payment.');
      });
    return () => {
      controller.abort();
    };
    // `notify` is only used for the failure message; the link alone decides what to open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkedPaymentId]);
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
    {
      id: 'number',
      header: 'Number',
      render: (p) => <strong>{p.collection_number ?? '—'}</strong>,
    },
    { id: 'received', header: 'Received', render: (p) => formatInstantIn(p.received_at, timeZone) },
    {
      id: 'customer',
      header: 'Customer',
      render: (p) => p.customer_name ?? customerLabel(p.customer_id),
    },
    { id: 'method', header: 'Method', render: (p) => PAYMENT_METHOD_LABELS[p.method] },
    { id: 'ref', header: 'Reference', render: (p) => p.reference ?? '—' },
    {
      id: 'status',
      header: 'Status',
      render: (p) => (
        <Box component="span" className="inline-flex flex-wrap gap-1">
          <StatusChip
            status={p.status}
            tones={SETTLEMENT_TONES}
            label={SETTLEMENT_LABELS[p.status]}
          />
          <ReversedChip payment={p} />
        </Box>
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
        <RowActionsMenu
          label={`payment ${p.collection_number ?? p.reference ?? shortId(p.id)}`}
          actions={actionsFor(p)}
        />
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
        searchPlaceholder="Search collection number or reference"
        reloadKey={reloadKey}
        filters={{
          status: view === 'ALL' ? undefined : view,
          customer_id: customer?.id,
          staff_member_id: staff?.id,
          method: method === '' ? undefined : method,
          date_from: dateFrom,
          date_to: dateTo,
        }}
        emptyTitle="No payments"
        isRowMuted={(p) => p.status === 'REJECTED' || p.reversed_at != null}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-wrap gap-3">
            <Box sx={{ minWidth: 240 }}>
              <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
            </Box>
            <Box sx={{ minWidth: 220 }}>
              <StaffFilter label="Received by" value={staff} onChange={setStaff} />
            </Box>
            <StaticSelectFilter
              label="Method"
              value={method}
              options={PAYMENT_METHOD_OPTIONS}
              allLabel="All methods"
              onChange={setMethod}
            />
            <UrlPeriodChip params={params} setParams={setParams} />
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
