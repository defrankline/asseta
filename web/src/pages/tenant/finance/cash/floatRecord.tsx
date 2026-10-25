import { useState, type ReactNode } from 'react';
import { CAPABILITY, useCapabilityEnabled } from '../../../../access/capabilities';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashCustodyEntryDto } from '../../../../api/types';
import { KeyValueGrid, type KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { nameOr } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import type { HistoryEvent } from '../../shared/RecordDetail';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { FLOAT_ACK_LABELS, FLOAT_ACK_TONES } from './custodyDisplay';
import { AcknowledgeDialog } from './CustodyDialogs';

export const floatChip = (e: CashCustodyEntryDto) => (
  <StatusChip
    status={e.ack_status}
    tones={FLOAT_ACK_TONES}
    label={FLOAT_ACK_LABELS[e.ack_status]}
  />
);

export const floatCustodian = (e: CashCustodyEntryDto) =>
  nameOr(e.staff_member_name, e.staff_member_id);

export const floatKind = (e: CashCustodyEntryDto) =>
  e.entry_type === 'FLOAT_ISSUED' ? 'Float issued' : 'Opening balance';

/** The receiver's answer to a float (list row and detail page); never the person who issued it. */
export function useFloatActions(onChanged: (e: CashCustodyEntryDto) => void) {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const me = useMyUserId();
  const can = useMutationGuard();
  // Float acknowledgement is a cash custody control: none while the tenant switches it off.
  const ackOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  const canAnswer = ackOn && can(PERMISSIONS.tenantCollectionRecord);
  const [answering, setAnswering] = useState<CashCustodyEntryDto | null>(null);
  const actionsFor = (e: CashCustodyEntryDto): RowAction[] => [
    {
      key: 'answer',
      label: 'Acknowledge / dispute',
      hidden: !canAnswer || e.ack_status !== 'PENDING',
      disabled: e.created_by != null && e.created_by === me,
      disabledReason: 'You issued this float; the receiver must answer it.',
      onClick: () => {
        setAnswering(e);
      },
    },
  ];
  let dialog: ReactNode = null;
  if (answering !== null) {
    const e = answering;
    dialog = (
      <AcknowledgeDialog<CashCustodyEntryDto>
        title="Acknowledge cash float"
        declared={e.amount}
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: floatCustodian(e) },
              {
                label: 'Amount issued',
                value: <MoneyText amount={e.amount} currency={e.currency} strong />,
              },
              { label: 'Issued', value: formatInstantIn(e.occurred_at, timeZone) },
              { label: 'Reference', value: e.reference ?? '—' },
            ]}
          />
        }
        onAnswer={(body, key) => custodyService.acknowledgeFloat(e.id, body, key)}
        onDone={(r) => {
          notify.success(r.ack_status === 'DISPUTED' ? 'Float disputed.' : 'Float acknowledged.');
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

export function floatItems(e: CashCustodyEntryDto, timeZone: string): KeyValueItem[] {
  return [
    { label: 'Custodian', value: floatCustodian(e) },
    { label: 'Entry', value: floatKind(e) },
    { label: 'Amount', value: <MoneyText amount={e.amount} currency={e.currency} /> },
    {
      label: 'Received',
      value:
        e.amount_received == null ? (
          '—'
        ) : (
          <MoneyText amount={e.amount_received} currency={e.currency} />
        ),
    },
    { label: 'Issued', value: formatInstantIn(e.occurred_at, timeZone) },
    { label: 'Reference', value: e.reference ?? '—' },
    { label: 'Note', value: e.note ?? '—' },
    {
      label: 'Issued by',
      value: <PersonName userId={e.created_by ?? null} name={e.created_by_name} />,
    },
    {
      label: 'Answered by',
      value: <PersonName userId={e.acknowledged_by ?? null} name={e.acknowledged_by_name} />,
    },
  ];
}

export function floatHistory(e: CashCustodyEntryDto): HistoryEvent[] {
  return [
    {
      key: 'issued',
      at: e.occurred_at,
      label: `${floatKind(e)} to ${floatCustodian(e)}`,
      by: <PersonName userId={e.created_by ?? null} name={e.created_by_name} />,
      note: e.note,
    },
    {
      key: 'answered',
      at: e.acknowledged_at,
      label: e.ack_status === 'DISPUTED' ? 'Disputed' : 'Acknowledged',
      by: <PersonName userId={e.acknowledged_by ?? null} name={e.acknowledged_by_name} />,
    },
  ];
}
