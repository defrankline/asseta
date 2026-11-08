import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashHandoverDto } from '../../../../api/types';
import { KeyValueGrid, type KeyValueItem } from '../../../../components/display/KeyValueGrid';
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
import { DecisionDialog } from '../../shared/DecisionDialog';
import { useMyUserId } from '../../shared/useFinanceLabels';
import {
  DECISION_STATUS_LABELS,
  EVIDENCE_STATUS_LABELS,
  EVIDENCE_STATUS_TONES,
  OWN_REQUEST_TOOLTIP,
} from './custodyDisplay';
import { RemittanceEvidence } from './remittanceDeposit';
import { remittanceAccountText, remittanceMethodText } from './remittanceDetails';
import { RemittanceDecisionDialog } from './CustodyDialogs';

export const remittanceChip = (h: CashHandoverDto) => (
  <StatusChip status={h.status} tones={SETTLEMENT_TONES} label={SETTLEMENT_LABELS[h.status]} />
);

/** Declared / Supported / Confirmed: what backs the remittance (derived by the server). */
export const remittanceEvidenceChip = (h: CashHandoverDto) =>
  h.evidence_status == null ? (
    '—'
  ) : (
    <StatusChip
      status={h.evidence_status}
      tones={EVIDENCE_STATUS_TONES}
      label={EVIDENCE_STATUS_LABELS[h.evidence_status]}
    />
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
  const canDecideReason = useCanMutate(PERMISSIONS.tenantFinanceRetentionApprove);
  const [deciding, setDeciding] = useState<CashHandoverDto | null>(null);
  const [partial, setPartial] = useState<CashHandoverDto | null>(null);
  const actionsFor = (h: CashHandoverDto): RowAction[] => {
    const mine = h.recorded_by !== null && h.recorded_by === me;
    const reasonMine = h.partial_approval?.created_by === me && me !== null;
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
      {
        key: 'partial-reason',
        label: reasonMine
          ? `Decide partial reason (${OWN_REQUEST_TOOLTIP})`
          : 'Decide partial reason',
        hidden: !canDecideReason || h.partial_approval?.status !== 'PENDING',
        disabled: reasonMine,
        disabledReason: OWN_REQUEST_TOOLTIP,
        onClick: () => {
          setPartial(h);
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
  if (partial?.partial_approval != null) {
    const h = partial;
    const approval = partial.partial_approval;
    dialog = (
      <DecisionDialog<CashHandoverDto>
        title="Decide partial remittance reason"
        kind="approve"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: remittanceCustodian(h) },
              { label: 'Short of full balance', value: money(h.partial_shortfall, h.currency) },
              { label: 'Why part stays', value: approval.reason },
              {
                label: 'Requested by',
                value: <PersonName userId={approval.created_by} name={approval.created_by_name} />,
              },
            ]}
          />
        }
        explanation="This decides the reason only. Confirming the money is a separate decision; a rejected reason does not reject the money."
        onDecide={(approve, note, key) =>
          custodyService.decidePartialReason(h.id, { approve, note }, key)
        }
        onDone={(r) => {
          notify.success(
            r.partial_approval?.status === 'APPROVED'
              ? 'Partial reason approved.'
              : 'Partial reason rejected.',
          );
          onChanged(r);
        }}
        onClose={() => {
          setPartial(null);
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
  'Outstanding difference',
  'Evidence status',
]);

function partialItems(h: CashHandoverDto): KeyValueItem[] {
  const a = h.partial_approval;
  if (a == null) return [];
  return [
    { label: 'Why part stays', value: a.reason },
    { label: 'Reason decision', value: DECISION_STATUS_LABELS[a.status] },
    {
      label: 'Reason decided by',
      value: <PersonName userId={a.decided_by} name={a.decided_by_name} />,
    },
    { label: 'Reason decision note', value: a.decision_note ?? '—' },
  ];
}

/** `controlsOn` false (cash custody controls off): the remittance as before those controls. */
export function remittanceItems(
  h: CashHandoverDto,
  timeZone: string,
  controlsOn = true,
): KeyValueItem[] {
  const items: KeyValueItem[] = [
    { label: 'Number', value: h.remittance_number ?? '—' },
    { label: 'Custodian', value: remittanceCustodian(h) },
    { label: 'Paid by', value: remittanceMethodText(h) },
    { label: 'Company account', value: remittanceAccountText(h) },
    { label: 'Bank / mobile reference', value: h.reference ?? '—' },
    { label: 'Evidence status', value: remittanceEvidenceChip(h) },
    { label: 'Photos', value: <RemittanceEvidence handover={h} /> },
    { label: 'Declared', value: <MoneyText amount={h.amount} currency={h.currency} /> },
    { label: 'Received', value: money(h.amount_received, h.currency) },
    { label: 'Expected balance', value: money(h.expected_balance, h.currency) },
    { label: 'Short of full balance', value: money(h.partial_shortfall, h.currency) },
    { label: 'Outstanding difference', value: money(h.outstanding_difference, h.currency) },
    ...partialItems(h),
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
    {
      key: 'partial-requested',
      at: h.partial_approval?.created_at,
      label: 'Partial reason given',
      by: (
        <PersonName
          userId={h.partial_approval?.created_by ?? null}
          name={h.partial_approval?.created_by_name}
        />
      ),
      note: h.partial_approval?.reason,
    },
    {
      key: 'partial-decided',
      at: h.partial_approval?.decided_at,
      label:
        h.partial_approval?.status === 'REJECTED'
          ? 'Partial reason rejected'
          : 'Partial reason approved',
      by: (
        <PersonName
          userId={h.partial_approval?.decided_by ?? null}
          name={h.partial_approval?.decided_by_name}
        />
      ),
      note: h.partial_approval?.decision_note,
    },
  ];
}
