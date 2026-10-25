import { Link } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import type { CashTransferDto } from '../../../../api/custodyTypes';
import { custodyService } from '../../../../api/services/custodyService';
import type { KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { recordPath } from '../../../../navigation/recordRoutes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { nameOr } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import type { HistoryEvent } from '../../shared/RecordDetail';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { ACK_METHOD_LABELS, TRANSFER_STATUS_LABELS, TRANSFER_STATUS_TONES } from './custodyDisplay';
import { AcknowledgeDialog } from './CustodyDialogs';

export const transferChip = (t: CashTransferDto) => (
  <StatusChip
    status={t.status}
    tones={TRANSFER_STATUS_TONES}
    label={TRANSFER_STATUS_LABELS[t.status]}
  />
);

export const transferFrom = (t: CashTransferDto) => nameOr(t.from_staff_name, t.from_staff_id);
export const transferTo = (t: CashTransferDto) => nameOr(t.to_staff_name, t.to_staff_id);

/**
 * The receiver's answer to a transfer, shared by the list row and the detail page: acknowledge with
 * the amount received or dispute; never the person who recorded it.
 */
export function useTransferActions(onChanged: (t: CashTransferDto) => void) {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const me = useMyUserId();
  const can = useMutationGuard();
  const canRecord = can(PERMISSIONS.tenantCollectionRecord);
  const [answering, setAnswering] = useState<CashTransferDto | null>(null);
  const actionsFor = (t: CashTransferDto): RowAction[] => [
    {
      key: 'answer',
      label: 'Acknowledge / dispute',
      hidden: !canRecord || t.status !== 'PENDING_ACKNOWLEDGEMENT',
      disabled: t.recorded_by !== null && t.recorded_by === me,
      disabledReason: 'You recorded this transfer; the receiver must answer it.',
      onClick: () => {
        setAnswering(t);
      },
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
              { label: 'From', value: transferFrom(t) },
              { label: 'To', value: transferTo(t) },
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
          onChanged(r);
        }}
        onClose={() => {
          setAnswering(null);
        }}
      />
    );
  }
  return { actionsFor, dialog };
}

/** Detail fields of a transfer; `linkVariance` when the viewer may open variances. */
export function transferItems(
  t: CashTransferDto,
  timeZone: string,
  linkVariance: boolean,
): KeyValueItem[] {
  const varianceId = t.variance_id ?? null;
  return [
    { label: 'From (sender)', value: transferFrom(t) },
    { label: 'To (receiver)', value: transferTo(t) },
    { label: 'Declared', value: <MoneyText amount={t.amount_declared} currency={t.currency} /> },
    {
      label: 'Received',
      value:
        t.amount_received === null ? (
          '—'
        ) : (
          <MoneyText amount={t.amount_received} currency={t.currency} />
        ),
    },
    { label: 'Handed over', value: formatInstantIn(t.transferred_at, timeZone) },
    { label: 'Note', value: t.note ?? '—' },
    {
      label: 'Recorded by',
      value: <PersonName userId={t.recorded_by} name={t.recorded_by_name} />,
    },
    {
      label: 'Acknowledgement',
      value: t.ack_method === null ? '—' : ACK_METHOD_LABELS[t.ack_method],
    },
    {
      label: 'Answered by',
      value: <PersonName userId={t.acknowledged_by} name={t.acknowledged_by_name} />,
    },
    { label: 'Receiver’s note', value: t.ack_note ?? '—' },
    {
      label: 'Variance',
      value:
        varianceId === null ? (
          '—'
        ) : linkVariance ? (
          <Link component={RouterLink} to={recordPath('CASH_VARIANCE', varianceId)}>
            Open variance
          </Link>
        ) : (
          'Opened'
        ),
    },
  ];
}

export function transferHistory(t: CashTransferDto): HistoryEvent[] {
  return [
    { key: 'handed', at: t.transferred_at, label: `Handed over by ${transferFrom(t)}` },
    {
      key: 'recorded',
      at: t.recorded_at,
      label: 'Recorded',
      by: <PersonName userId={t.recorded_by} name={t.recorded_by_name} />,
      note: t.note,
    },
    {
      key: 'answered',
      at: t.acknowledged_at,
      label: t.status === 'DISPUTED' ? 'Disputed' : 'Acknowledged',
      by: <PersonName userId={t.acknowledged_by} name={t.acknowledged_by_name} />,
      note: t.ack_note,
    },
  ];
}
