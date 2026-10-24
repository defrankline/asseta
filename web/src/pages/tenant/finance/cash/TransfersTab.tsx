import { Alert, Box, Button, Link } from '@mui/material';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashTransferDto, CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import { DetailsDrawer } from '../../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { cashTabPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { shortId } from '../../shared/financeDisplay';
import { PersonName } from '../../shared/PersonName';
import { useMyUserId } from '../../shared/useFinanceLabels';
import {
  ACK_METHOD_LABELS,
  TRANSFER_STATUS_LABELS,
  TRANSFER_STATUS_OPTIONS,
  TRANSFER_STATUS_TONES,
} from './custodyDisplay';
import { AcknowledgeDialog, TransferDialog } from './CustodyDialogs';
import { useCashPolicy, useCustodianLabels } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';

const statusChip = (t: CashTransferDto) => (
  <StatusChip
    status={t.status}
    tones={TRANSFER_STATUS_TONES}
    label={TRANSFER_STATUS_LABELS[t.status]}
  />
);

interface TransfersTabProps {
  timeZone: string;
  /** Field work: the caller records as sender unless the tenant lets recorders act for others. */
  field?: boolean;
  /** Opens this transfer's details (deep link from a reconciliation drill-down). */
  focusId?: string | null;
  /** Status filter on arrival (dashboard deep link). */
  initialStatus?: string | undefined;
}

/** Field-to-field cash transfers: who handed what to whom, and the receiver's acknowledgement. */
export function TransfersTab({
  timeZone,
  field = false,
  focusId = null,
  initialStatus,
}: TransfersTabProps) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const policy = useCashPolicy();
  const custodian = useCustodianLabels();
  const canRecord = can(PERMISSIONS.tenantCollectionRecord);
  const forOthers =
    can(PERMISSIONS.tenantFinanceCash) || policy?.recordersMayRecordForOthers === true;
  const [status, setStatus] = useState(initialStatus ?? (field ? 'PENDING_ACKNOWLEDGEMENT' : ''));
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [viewing, setViewing] = useState<CashTransferDto | null>(null);
  const [answering, setAnswering] = useState<CashTransferDto | null>(null);
  const [recording, setRecording] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  useEffect(() => {
    if (focusId === null) return undefined;
    const controller = new AbortController();
    custodyService.transfer(focusId, controller.signal).then(setViewing, () => {
      // The list stays usable when the linked transfer is not visible to this user.
    });
    return () => {
      controller.abort();
    };
  }, [focusId]);
  const fetchPage = useCallback<FetchPage<CashTransferDto>>(
    (query, signal) => custodyService.transfers(query, signal),
    [],
  );
  const recordedByMe = (t: CashTransferDto) => t.recorded_by !== null && t.recorded_by === me;
  const actionsFor = (t: CashTransferDto, inDrawer: boolean): RowAction[] => [
    ...(inDrawer
      ? []
      : [
          {
            key: 'view',
            label: 'View details',
            onClick: () => {
              setViewing(t);
            },
          },
        ]),
    {
      key: 'answer',
      label: 'Acknowledge / dispute',
      hidden: !canRecord || t.status !== 'PENDING_ACKNOWLEDGEMENT',
      disabled: recordedByMe(t),
      disabledReason: 'You recorded this transfer; the receiver must answer it.',
      onClick: () => {
        setViewing(null);
        setAnswering(t);
      },
    },
  ];
  const columns: DataColumn<CashTransferDto>[] = [
    { id: 'at', header: 'Handed over', render: (t) => formatInstantIn(t.transferred_at, timeZone) },
    { id: 'from', header: 'From', render: (t) => custodian(t.from_staff_id) },
    { id: 'to', header: 'To', render: (t) => custodian(t.to_staff_id) },
    { id: 'status', header: 'Status', render: statusChip },
    {
      id: 'declared',
      header: 'Declared',
      align: 'right',
      render: (t) => <MoneyText amount={t.amount_declared} currency={t.currency} />,
    },
    {
      id: 'received',
      header: 'Received',
      align: 'right',
      render: (t) =>
        t.amount_received === null ? (
          '—'
        ) : (
          <MoneyText amount={t.amount_received} currency={t.currency} />
        ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (t) => (
        <RowActionsMenu
          label={`transfer ${custodian(t.from_staff_id)} to ${custodian(t.to_staff_id)}`}
          actions={actionsFor(t, false)}
        />
      ),
    },
  ];
  let dialog: ReactNode = null;
  if (answering !== null) {
    const t = answering;
    dialog = (
      <AcknowledgeDialog<CashTransferDto>
        title="Acknowledge cash transfer"
        declared={t.amount_declared}
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'From', value: custodian(t.from_staff_id) },
              { label: 'To', value: custodian(t.to_staff_id) },
              {
                label: 'Declared',
                value: <MoneyText amount={t.amount_declared} currency={t.currency} strong />,
              },
              { label: 'Handed over', value: formatInstantIn(t.transferred_at, timeZone) },
            ]}
          />
        }
        onAnswer={(body, key) => custodyService.acknowledgeTransfer(t.id, body, key)}
        onDone={(r) => {
          notify.success(
            r.status === 'DISPUTED'
              ? 'Transfer disputed; it stays with the sender.'
              : r.variance_id === null || r.variance_id === undefined
                ? 'Transfer acknowledged.'
                : 'Transfer acknowledged; the difference was opened as a variance.',
          );
          reload();
        }}
        onClose={() => {
          setAnswering(null);
        }}
      />
    );
  }
  return (
    <Box className="flex flex-col gap-3">
      {policy?.transferAckRequired === false && (
        <Alert severity="info">
          Your organisation does not require receivers to acknowledge transfers: a transfer counts
          as received at the declared amount when recorded.
        </Alert>
      )}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(t) => t.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ status: status || undefined, staff_member_id: who?.staff_member_id }}
        emptyTitle="No cash transfers"
        isRowMuted={(t) => t.status === 'DISPUTED'}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={TRANSFER_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <CustodianFilter value={who} onChange={setWho} />
            </Box>
            {canRecord && (
              <Button
                variant="outlined"
                onClick={() => {
                  setRecording(true);
                }}
              >
                Record transfer
              </Button>
            )}
          </Box>
        }
      />
      {viewing !== null && (
        <DetailsDrawer
          title="Cash transfer"
          status={statusChip(viewing)}
          actions={<ActionButtons actions={actionsFor(viewing, true)} />}
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'From (sender)', value: custodian(viewing.from_staff_id) },
              { label: 'To (receiver)', value: custodian(viewing.to_staff_id) },
              {
                label: 'Declared',
                value: <MoneyText amount={viewing.amount_declared} currency={viewing.currency} />,
              },
              {
                label: 'Received',
                value:
                  viewing.amount_received === null ? (
                    '—'
                  ) : (
                    <MoneyText amount={viewing.amount_received} currency={viewing.currency} />
                  ),
              },
              { label: 'Handed over', value: formatInstantIn(viewing.transferred_at, timeZone) },
              { label: 'Note', value: viewing.note ?? '—' },
              { label: 'Recorded by', value: <PersonName userId={viewing.recorded_by} /> },
              { label: 'Recorded at', value: formatInstantIn(viewing.recorded_at, timeZone) },
              {
                label: 'Acknowledgement',
                value: viewing.ack_method === null ? '—' : ACK_METHOD_LABELS[viewing.ack_method],
              },
              {
                label: 'Answered by',
                value: <PersonName userId={viewing.acknowledged_by} />,
              },
              {
                label: 'Answered at',
                value:
                  viewing.acknowledged_at === null
                    ? '—'
                    : formatInstantIn(viewing.acknowledged_at, timeZone),
              },
              { label: 'Receiver’s note', value: viewing.ack_note ?? '—' },
              {
                label: 'Variance',
                value:
                  viewing.variance_id === null || viewing.variance_id === undefined ? (
                    '—'
                  ) : field ? (
                    shortId(viewing.variance_id)
                  ) : (
                    <Link
                      component={RouterLink}
                      to={cashTabPath('variances', { id: viewing.variance_id })}
                    >
                      Open variance
                    </Link>
                  ),
              },
            ]}
          />
        </DetailsDrawer>
      )}
      {recording && (
        <TransferDialog
          ownCustody={!forOthers}
          policy={policy}
          timeZone={timeZone}
          onClose={() => {
            setRecording(false);
          }}
          onRecorded={(t) => {
            notify.success(
              t.status === 'PENDING_ACKNOWLEDGEMENT'
                ? 'Transfer recorded; it stays with the sender until the receiver acknowledges it.'
                : 'Transfer recorded.',
            );
            reload();
          }}
        />
      )}
      {dialog}
    </Box>
  );
}
