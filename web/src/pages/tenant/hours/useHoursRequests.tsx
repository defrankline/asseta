import { Box, Button } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { CancellationDto, DecisionIn, ReasonIn, TransferDto } from '../../../api/hoursTypes';
import { hoursRequestService } from '../../../api/services/hoursService';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { KeyValueGrid, type KeyValueItem } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import { recordPath, type RecordKind } from '../../../navigation/recordRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { machineText, nameOr } from '../shared/names';
import { PersonName } from '../shared/PersonName';
import type { HistoryEvent } from '../shared/RecordDetail';
import { useMyUserId } from '../shared/useFinanceLabels';
import { DecideButton, DecideDialog, ReasonDialog } from './HoursDialogs';
import {
  hoursText,
  OWN_REQUEST_TEXT,
  REQUEST_STATUS_LABELS,
  REQUEST_STATUS_TONES,
} from './hoursDisplay';

type RequestRow = TransferDto | CancellationDto;

export const requestStatusChip = (s: RequestRow['status']) => (
  <StatusChip status={s} tones={REQUEST_STATUS_TONES} label={REQUEST_STATUS_LABELS[s]} />
);

/** Columns, row commands, dialogs and detail view of one kind of hours request. */
export interface RequestKit<T> {
  columns: DataColumn<T>[];
  /** The row's commands (decide / withdraw), the same on the list and the detail page. */
  actionsFor: (row: T) => RowAction[];
  dialogs: ReactNode;
  items: (row: T) => KeyValueItem[];
  history: (row: T) => HistoryEvent[];
}

interface KitConfig<T extends RequestRow> {
  kind: RecordKind;
  decidePermission: string;
  requestPermission: string;
  /** Row-specific columns between "Purchase" and "Reason". */
  middleColumns: DataColumn<T>[];
  /** Row-specific details (decide summary and detail page). */
  detailItems: (row: T) => KeyValueItem[];
  decideTitle: string;
  withdrawTitle: string;
  explanation: string;
  decide: (id: string, body: DecisionIn, key: string) => Promise<T>;
  withdraw: (id: string, body: ReasonIn, key: string) => Promise<T>;
  doneText: (row: T, verb: string) => string;
}

function useRequestKit<T extends RequestRow>(
  config: KitConfig<T>,
  onChanged: (row: T) => void,
  showPurchase: boolean,
): RequestKit<T> {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const me = useMyUserId();
  const canDecide = useCanMutate(config.decidePermission);
  const canRequest = useCanMutate(config.requestPermission);
  const [deciding, setDeciding] = useState<T | null>(null);
  const [withdrawing, setWithdrawing] = useState<T | null>(null);
  const own = (r: T) => me !== null && r.requested_by === me;
  const done = (r: T, verb: string) => {
    notify.success(config.doneText(r, verb));
    onChanged(r);
  };
  const actionsFor = (r: T): RowAction[] => [
    {
      key: 'decide',
      label: 'Decide',
      hidden: !canDecide || r.status !== 'PENDING',
      disabled: own(r),
      disabledReason: OWN_REQUEST_TEXT,
      onClick: () => {
        setDeciding(r);
      },
    },
    {
      key: 'withdraw',
      label: 'Withdraw',
      hidden: !canRequest || r.status !== 'PENDING' || !own(r),
      onClick: () => {
        setWithdrawing(r);
      },
    },
  ];
  const purchaseLink = (r: T) => (
    <Button component={RouterLink} to={hoursPurchasePath(r.purchase_id)} size="small">
      {r.purchase_number ?? 'Open purchase'}
    </Button>
  );
  const columns: DataColumn<T>[] = [
    {
      id: 'requested',
      header: 'Requested',
      render: (r) => formatInstantIn(r.requested_at, timeZone),
    },
    ...(showPurchase
      ? [
          { id: 'purchase', header: 'Purchase', render: purchaseLink },
          {
            id: 'customer',
            header: 'Customer',
            render: (r: T) => nameOr(r.customer_name, null),
          },
        ]
      : []),
    ...config.middleColumns,
    { id: 'reason', header: 'Reason', render: (r) => r.reason },
    {
      id: 'by',
      header: 'Requested by',
      render: (r) => <PersonName userId={r.requested_by} name={r.requested_by_name} />,
    },
    { id: 'status', header: 'Status', render: (r) => requestStatusChip(r.status) },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => (
        <Box
          className="flex justify-end gap-1"
          onClick={(e) => {
            e.stopPropagation();
          }}
        >
          {canDecide && r.status === 'PENDING' && (
            <DecideButton
              own={own(r)}
              onClick={() => {
                setDeciding(r);
              }}
            />
          )}
          {canRequest && r.status === 'PENDING' && own(r) && (
            <Button
              size="small"
              onClick={() => {
                setWithdrawing(r);
              }}
            >
              Withdraw
            </Button>
          )}
          <Button size="small" component={RouterLink} to={recordPath(config.kind, r.id)}>
            Details
          </Button>
        </Box>
      ),
    },
  ];
  const items = (r: T): KeyValueItem[] => [
    { label: 'Purchase', value: purchaseLink(r) },
    { label: 'Customer', value: nameOr(r.customer_name, null) },
    ...config.detailItems(r),
    { label: 'Reason', value: r.reason },
    {
      label: 'Requested by',
      value: <PersonName userId={r.requested_by} name={r.requested_by_name} />,
    },
    { label: 'Requested at', value: formatInstantIn(r.requested_at, timeZone) },
    {
      label: r.status === 'WITHDRAWN' ? 'Withdrawn by' : 'Decided by',
      value: <PersonName userId={r.decided_by} name={r.decided_by_name} />,
    },
    {
      label: r.status === 'WITHDRAWN' ? 'Withdrawn at' : 'Decided at',
      value: r.decided_at === null ? '—' : formatInstantIn(r.decided_at, timeZone),
    },
    { label: 'Decision note', value: r.decision_note ?? '—' },
  ];
  const history = (r: T): HistoryEvent[] => [
    {
      key: 'requested',
      at: r.requested_at,
      label: 'Requested',
      by: <PersonName userId={r.requested_by} name={r.requested_by_name} />,
      note: r.reason,
    },
    {
      key: 'decided',
      at: r.status === 'PENDING' ? null : r.decided_at,
      label: REQUEST_STATUS_LABELS[r.status],
      by: <PersonName userId={r.decided_by} name={r.decided_by_name} />,
      note: r.decision_note,
    },
  ];
  const dialogs = (
    <>
      {deciding !== null && (
        <DecideDialog
          title={config.decideTitle}
          summary={
            <KeyValueGrid
              columns={2}
              items={[
                ...config.detailItems(deciding),
                {
                  label: 'Requested by',
                  value: (
                    <PersonName userId={deciding.requested_by} name={deciding.requested_by_name} />
                  ),
                },
                { label: 'Reason', value: deciding.reason },
              ]}
            />
          }
          explanation={config.explanation}
          onDecide={(body, key) => config.decide(deciding.id, body, key)}
          onDone={(r) => {
            done(r, r.status === 'APPROVED' ? 'approved' : 'rejected');
          }}
          onClose={() => {
            setDeciding(null);
          }}
        />
      )}
      {withdrawing !== null && (
        <ReasonDialog
          title={config.withdrawTitle}
          submitLabel="Withdraw request"
          onSubmit={(body, key) => config.withdraw(withdrawing.id, { reason: body.reason }, key)}
          onDone={(r) => {
            done(r, 'withdrawn');
          }}
          onClose={() => {
            setWithdrawing(null);
          }}
        />
      )}
    </>
  );
  return { columns, actionsFor, dialogs, items, history };
}

const transferMachines = (t: TransferDto) =>
  `${machineText(t.from_machine_code, t.from_machine_name, t.from_machine_id)} → ${machineText(
    t.to_machine_code,
    t.to_machine_name,
    t.to_machine_id,
  )}`;

/** Title of a transfer (detail page, labels). */
export const transferTitle = (t: TransferDto) =>
  `Hours transfer · ${hoursText(t.hours)} · ${transferMachines(t)}`;

/**
 * Columns, commands and decide / withdraw dialogs for hours transfers. Deciding needs the approve
 * permission and is disabled on your own request; only the requester withdraws a pending request.
 */
export function useTransferRequests(
  onChanged: (t: TransferDto) => void,
  options: { showPurchase?: boolean } = {},
): RequestKit<TransferDto> {
  return useRequestKit<TransferDto>(
    {
      kind: 'HOURS_TRANSFER',
      decidePermission: PERMISSIONS.tenantHoursTransferApprove,
      requestPermission: PERMISSIONS.tenantHoursTransfer,
      middleColumns: [
        { id: 'machines', header: 'From → to', render: transferMachines },
        { id: 'hours', header: 'Hours', align: 'right', render: (t) => hoursText(t.hours) },
      ],
      detailItems: (t) => [
        {
          label: 'From',
          value: machineText(t.from_machine_code, t.from_machine_name, t.from_machine_id),
        },
        { label: 'To', value: machineText(t.to_machine_code, t.to_machine_name, t.to_machine_id) },
        { label: 'Hours', value: hoursText(t.hours) },
      ],
      decideTitle: 'Decide hours transfer',
      withdrawTitle: 'Withdraw transfer request',
      explanation:
        'Approving moves these remaining hours to the other machine; the purchase keeps its history.',
      decide: (id, body, key) => hoursRequestService.decideTransfer(id, body, key),
      withdraw: (id, body, key) => hoursRequestService.withdrawTransfer(id, body, key),
      doneText: (t, verb) => `Transfer of ${hoursText(t.hours)} ${verb}.`,
    },
    onChanged,
    options.showPurchase === true,
  );
}

/** Columns, commands and decide / withdraw dialogs for hours purchase cancellations (same rules). */
export function useCancellationRequests(
  onChanged: (c: CancellationDto) => void,
  options: { showPurchase?: boolean } = {},
): RequestKit<CancellationDto> {
  return useRequestKit<CancellationDto>(
    {
      kind: 'HOURS_CANCELLATION',
      decidePermission: PERMISSIONS.tenantHoursCancelApprove,
      requestPermission: PERMISSIONS.tenantHoursCancel,
      middleColumns: [],
      detailItems: () => [],
      decideTitle: 'Decide cancellation',
      withdrawTitle: 'Withdraw cancellation request',
      explanation:
        'Approving cancels the purchase: hours not yet used can no longer be used, and the payment link is released.',
      decide: (id, body, key) => hoursRequestService.decideCancellation(id, body, key),
      withdraw: (id, body, key) => hoursRequestService.withdrawCancellation(id, body, key),
      doneText: (_c, verb) => `Cancellation request ${verb}.`,
    },
    onChanged,
    options.showPurchase === true,
  );
}
