import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import type { CashHandoverDto } from '../../../../api/types';
import type { KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { SETTLEMENT_LABELS, SETTLEMENT_TONES } from '../../shared/financeDisplay';
import { nameOr } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import type { HistoryEvent } from '../../shared/RecordDetail';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { OWN_REQUEST_TOOLTIP } from './custodyDisplay';
import { RemittanceDecisionDialog } from './CustodyDialogs';

export const remittanceChip = (h: CashHandoverDto) => (
  <StatusChip status={h.status} tones={SETTLEMENT_TONES} label={SETTLEMENT_LABELS[h.status]} />
);

export const remittanceCustodian = (h: CashHandoverDto) =>
  nameOr(h.staff_member_name, h.staff_member_id);

const money = (amount: string | null | undefined, currency: string) =>
  amount == null ? '—' : <MoneyText amount={amount} currency={currency} />;

/**
 * Confirm (with the amount actually received) or reject a remittance — list row and detail page.
 * Never the person who recorded it.
 */
export function useRemittanceActions(onChanged: (h: CashHandoverDto) => void) {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const me = useMyUserId();
  const canVerify = useCanMutate(PERMISSIONS.tenantFinanceVerify);
  const [deciding, setDeciding] = useState<CashHandoverDto | null>(null);
  const actionsFor = (h: CashHandoverDto): RowAction[] => {
    const mine = h.recorded_by !== null && h.recorded_by === me;
    return [
      {
        key: 'decide',
        label: mine ? `Confirm / reject (${OWN_REQUEST_TOOLTIP})` : 'Confirm / reject',
        hidden: !canVerify || h.status !== 'CLAIMED',
        disabled: mine,
        disabledReason: OWN_REQUEST_TOOLTIP,
        onClick: () => {
          setDeciding(h);
        },
      },
    ];
  };
  let dialog: ReactNode = null;
  if (deciding !== null) {
    const h = deciding;
    dialog = (
      <RemittanceDecisionDialog
        handover={h}
        custodianName={remittanceCustodian(h)}
        timeZone={timeZone}
        onDone={(r) => {
          notify.success(
            r.status === 'VERIFIED' ? 'Remittance confirmed.' : 'Remittance rejected.',
          );
          onChanged(r);
        }}
        onClose={() => {
          setDeciding(null);
        }}
      />
    );
  }
  return { actionsFor, dialog };
}

/** Amount received, expected balance and shortfall belong to the cash custody controls. */
const REMITTANCE_CONTROL_ITEMS: ReadonlySet<string> = new Set([
  'Received',
  'Expected balance',
  'Short of full balance',
]);

/** `controlsOn` false (cash custody controls off): the remittance as before those controls. */
export function remittanceItems(
  h: CashHandoverDto,
  timeZone: string,
  controlsOn = true,
): KeyValueItem[] {
  const items: KeyValueItem[] = [
    { label: 'Custodian', value: remittanceCustodian(h) },
    { label: 'Reference', value: h.reference ?? '—' },
    { label: 'Declared', value: <MoneyText amount={h.amount} currency={h.currency} /> },
    { label: 'Received', value: money(h.amount_received, h.currency) },
    { label: 'Expected balance', value: money(h.expected_balance, h.currency) },
    { label: 'Short of full balance', value: money(h.partial_shortfall, h.currency) },
    { label: 'Handed over', value: formatInstantIn(h.handed_at, timeZone) },
    { label: 'Note', value: h.note ?? '—' },
    {
      label: 'Recorded by',
      value: <PersonName userId={h.recorded_by} name={h.recorded_by_name} />,
    },
    {
      label: 'Decided by',
      value: <PersonName userId={h.verified_by} name={h.verified_by_name} />,
    },
    { label: 'Decision note', value: h.decision_note ?? '—' },
  ];
  return controlsOn ? items : items.filter((i) => !REMITTANCE_CONTROL_ITEMS.has(i.label));
}

export function remittanceHistory(h: CashHandoverDto): HistoryEvent[] {
  return [
    { key: 'handed', at: h.handed_at, label: `Handed over by ${remittanceCustodian(h)}` },
    {
      key: 'recorded',
      at: h.recorded_at,
      label: 'Recorded',
      by: <PersonName userId={h.recorded_by} name={h.recorded_by_name} />,
      note: h.note,
    },
    {
      key: 'decided',
      at: h.verified_at,
      label: SETTLEMENT_LABELS[h.status],
      by: <PersonName userId={h.verified_by} name={h.verified_by_name} />,
      note: h.decision_note,
    },
  ];
}
