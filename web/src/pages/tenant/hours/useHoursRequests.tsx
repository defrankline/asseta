import { Box, Button } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { CancellationDto, TransferDto } from '../../../api/hoursTypes';
import { hoursRequestService } from '../../../api/services/hoursService';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { PersonName } from '../shared/PersonName';
import { useMyUserId } from '../shared/useFinanceLabels';
import { useMachineLabels } from '../shared/useMachineLabels';
import { DecideButton, DecideDialog, ReasonDialog } from './HoursDialogs';
import { hoursText, REQUEST_STATUS_LABELS, REQUEST_STATUS_TONES } from './hoursDisplay';

const statusChip = (s: TransferDto['status']) => (
  <StatusChip status={s} tones={REQUEST_STATUS_TONES} label={REQUEST_STATUS_LABELS[s]} />
);

interface RequestTable<T> {
  columns: DataColumn<T>[];
  dialogs: ReactNode;
}

/**
 * Columns and decide / withdraw dialogs for hours transfers. Deciding needs the approve permission
 * and is disabled on your own request; only the requester withdraws a pending request.
 */
export function useTransferRequests(
  onChanged: (t: TransferDto) => void,
  options: { showPurchase?: boolean } = {},
): RequestTable<TransferDto> {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const machineName = useMachineLabels();
  const me = useMyUserId();
  const canDecide = useCanMutate(PERMISSIONS.tenantHoursTransferApprove);
  const canRequest = useCanMutate(PERMISSIONS.tenantHoursTransfer);
  const [deciding, setDeciding] = useState<TransferDto | null>(null);
  const [withdrawing, setWithdrawing] = useState<TransferDto | null>(null);
  const done = (t: TransferDto, verb: string) => {
    notify.success(`Transfer of ${hoursText(t.hours)} ${verb}.`);
    onChanged(t);
  };
  const columns: DataColumn<TransferDto>[] = [
    {
      id: 'requested',
      header: 'Requested',
      render: (t) => formatInstantIn(t.requested_at, timeZone),
    },
    ...(options.showPurchase === true
      ? [
          {
            id: 'purchase',
            header: 'Purchase',
            render: (t: TransferDto) => (
              <Button component={RouterLink} to={hoursPurchasePath(t.purchase_id)} size="small">
                Open purchase
              </Button>
            ),
          },
        ]
      : []),
    {
      id: 'machines',
      header: 'From → to',
      render: (t) => `${machineName(t.from_machine_id)} → ${machineName(t.to_machine_id)}`,
    },
    { id: 'hours', header: 'Hours', align: 'right', render: (t) => hoursText(t.hours) },
    { id: 'reason', header: 'Reason', render: (t) => t.reason },
    { id: 'by', header: 'Requested by', render: (t) => <PersonName userId={t.requested_by} /> },
    { id: 'status', header: 'Status', render: (t) => statusChip(t.status) },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (t) =>
        t.status !== 'PENDING' ? null : (
          <Box className="flex justify-end gap-1">
            {canDecide && (
              <DecideButton
                own={me !== null && t.requested_by === me}
                onClick={() => {
                  setDeciding(t);
                }}
              />
            )}
            {canRequest && me !== null && t.requested_by === me && (
              <Button
                size="small"
                onClick={() => {
                  setWithdrawing(t);
                }}
              >
                Withdraw
              </Button>
            )}
          </Box>
        ),
    },
  ];
  const dialogs = (
    <>
      {deciding !== null && (
        <DecideDialog
          title="Decide hours transfer"
          summary={
            <KeyValueGrid
              columns={2}
              items={[
                { label: 'From', value: machineName(deciding.from_machine_id) },
                { label: 'To', value: machineName(deciding.to_machine_id) },
                { label: 'Hours', value: hoursText(deciding.hours) },
                { label: 'Requested by', value: <PersonName userId={deciding.requested_by} /> },
                { label: 'Reason', value: deciding.reason },
              ]}
            />
          }
          explanation="Approving moves these remaining hours to the other machine; the purchase keeps its history."
          onDecide={(body, key) => hoursRequestService.decideTransfer(deciding.id, body, key)}
          onDone={(t) => {
            done(t, t.status === 'APPROVED' ? 'approved' : 'rejected');
          }}
          onClose={() => {
            setDeciding(null);
          }}
        />
      )}
      {withdrawing !== null && (
        <ReasonDialog
          title="Withdraw transfer request"
          submitLabel="Withdraw request"
          onSubmit={(body, key) =>
            hoursRequestService.withdrawTransfer(withdrawing.id, { reason: body.reason }, key)
          }
          onDone={(t) => {
            done(t, 'withdrawn');
          }}
          onClose={() => {
            setWithdrawing(null);
          }}
        />
      )}
    </>
  );
  return { columns, dialogs };
}

/** Columns and decide / withdraw dialogs for hours purchase cancellations (same rules as transfers). */
export function useCancellationRequests(
  onChanged: (c: CancellationDto) => void,
  options: { showPurchase?: boolean } = {},
): RequestTable<CancellationDto> {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const me = useMyUserId();
  const canDecide = useCanMutate(PERMISSIONS.tenantHoursCancelApprove);
  const canRequest = useCanMutate(PERMISSIONS.tenantHoursCancel);
  const [deciding, setDeciding] = useState<CancellationDto | null>(null);
  const [withdrawing, setWithdrawing] = useState<CancellationDto | null>(null);
  const done = (c: CancellationDto, verb: string) => {
    notify.success(`Cancellation request ${verb}.`);
    onChanged(c);
  };
  const columns: DataColumn<CancellationDto>[] = [
    {
      id: 'requested',
      header: 'Requested',
      render: (c) => formatInstantIn(c.requested_at, timeZone),
    },
    ...(options.showPurchase === true
      ? [
          {
            id: 'purchase',
            header: 'Purchase',
            render: (c: CancellationDto) => (
              <Button component={RouterLink} to={hoursPurchasePath(c.purchase_id)} size="small">
                Open purchase
              </Button>
            ),
          },
        ]
      : []),
    { id: 'reason', header: 'Reason', render: (c) => c.reason },
    { id: 'by', header: 'Requested by', render: (c) => <PersonName userId={c.requested_by} /> },
    { id: 'status', header: 'Status', render: (c) => statusChip(c.status) },
    { id: 'note', header: 'Decision note', render: (c) => c.decision_note ?? '—' },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) =>
        c.status !== 'PENDING' ? null : (
          <Box className="flex justify-end gap-1">
            {canDecide && (
              <DecideButton
                own={me !== null && c.requested_by === me}
                onClick={() => {
                  setDeciding(c);
                }}
              />
            )}
            {canRequest && me !== null && c.requested_by === me && (
              <Button
                size="small"
                onClick={() => {
                  setWithdrawing(c);
                }}
              >
                Withdraw
              </Button>
            )}
          </Box>
        ),
    },
  ];
  const dialogs = (
    <>
      {deciding !== null && (
        <DecideDialog
          title="Decide cancellation"
          summary={
            <KeyValueGrid
              columns={2}
              items={[
                { label: 'Requested by', value: <PersonName userId={deciding.requested_by} /> },
                { label: 'Reason', value: deciding.reason },
              ]}
            />
          }
          explanation="Approving cancels the purchase: hours not yet used can no longer be used, and the payment link is released."
          onDecide={(body, key) => hoursRequestService.decideCancellation(deciding.id, body, key)}
          onDone={(c) => {
            done(c, c.status === 'APPROVED' ? 'approved' : 'rejected');
          }}
          onClose={() => {
            setDeciding(null);
          }}
        />
      )}
      {withdrawing !== null && (
        <ReasonDialog
          title="Withdraw cancellation request"
          submitLabel="Withdraw request"
          onSubmit={(body, key) =>
            hoursRequestService.withdrawCancellation(withdrawing.id, { reason: body.reason }, key)
          }
          onDone={(c) => {
            done(c, 'withdrawn');
          }}
          onClose={() => {
            setWithdrawing(null);
          }}
        />
      )}
    </>
  );
  return { columns, dialogs };
}
