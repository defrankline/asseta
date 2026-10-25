import { Alert, Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashTransferDto, CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { recordPath } from '../../../../navigation/recordRoutes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { TRANSFER_STATUS_OPTIONS } from './custodyDisplay';
import { TransferDialog } from './CustodyDialogs';
import { useCashPolicy } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';
import { transferChip, transferFrom, transferTo, useTransferActions } from './transferRecord';

interface TransfersTabProps {
  timeZone: string;
  /** Field work: the caller records as sender unless the tenant lets recorders act for others. */
  field?: boolean;
  /** Status filter on arrival (dashboard deep link). */
  initialStatus?: string | undefined;
}

/** Field-to-field cash transfers: who handed what to whom, and the receiver's acknowledgement. */
export function TransfersTab({ timeZone, field = false, initialStatus }: TransfersTabProps) {
  const notify = useNotify();
  const navigate = useNavigate();
  const can = useMutationGuard();
  const policy = useCashPolicy();
  const canRecord = can(PERMISSIONS.tenantCollectionRecord);
  const forOthers =
    can(PERMISSIONS.tenantFinanceCash) || policy?.recordersMayRecordForOthers === true;
  const [status, setStatus] = useState(initialStatus ?? (field ? 'PENDING_ACKNOWLEDGEMENT' : ''));
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [recording, setRecording] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const { actionsFor, dialog } = useTransferActions(reload);
  const open = (t: CashTransferDto) => {
    void navigate(recordPath('CASH_TRANSFER', t.id));
  };
  const fetchPage = useCallback<FetchPage<CashTransferDto>>(
    (query, signal) => custodyService.transfers(query, signal),
    [],
  );
  const columns: DataColumn<CashTransferDto>[] = [
    { id: 'at', header: 'Handed over', render: (t) => formatInstantIn(t.transferred_at, timeZone) },
    { id: 'from', header: 'From', render: transferFrom },
    { id: 'to', header: 'To', render: transferTo },
    { id: 'status', header: 'Status', render: transferChip },
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
          label={`transfer ${transferFrom(t)} to ${transferTo(t)}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                open(t);
              },
            },
            ...actionsFor(t),
          ]}
        />
      ),
    },
  ];
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
        onRowClick={open}
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
