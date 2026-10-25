import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import type { CashRetentionDto } from '../../../../api/custodyTypes';
import { custodyService } from '../../../../api/services/custodyService';
import { KeyValueGrid, type KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { nameOr } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import type { HistoryEvent } from '../../shared/RecordDetail';
import { useMyUserId } from '../../shared/useFinanceLabels';
import {
  DECISION_STATUS_LABELS,
  DECISION_STATUS_TONES,
  OWN_REQUEST_TOOLTIP,
} from './custodyDisplay';

export const retentionChip = (r: CashRetentionDto) => (
  <StatusChip
    status={r.status}
    tones={DECISION_STATUS_TONES}
    label={DECISION_STATUS_LABELS[r.status]}
  />
);

export const retentionCustodian = (r: CashRetentionDto) =>
  nameOr(r.staff_member_name, r.staff_member_id);

/** Approve / reject a request to keep cash (list row and detail page); never your own request. */
export function useRetentionActions(onChanged: (r: CashRetentionDto) => void) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const canDecide = can(PERMISSIONS.tenantFinanceRetentionApprove);
  const [deciding, setDeciding] = useState<CashRetentionDto | null>(null);
  const actionsFor = (r: CashRetentionDto): RowAction[] => {
    const mine = r.created_by !== null && r.created_by === me;
    return [
      {
        key: 'decide',
        label: mine ? `Approve / reject (${OWN_REQUEST_TOOLTIP})` : 'Approve / reject',
        hidden: !canDecide || r.status !== 'PENDING',
        disabled: mine,
        disabledReason: OWN_REQUEST_TOOLTIP,
        onClick: () => {
          setDeciding(r);
        },
      },
    ];
  };
  let dialog: ReactNode = null;
  if (deciding !== null) {
    const r = deciding;
    dialog = (
      <DecisionDialog<CashRetentionDto>
        title="Decide cash retention"
        kind="approve"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: retentionCustodian(r) },
              {
                label: 'Amount to keep',
                value: <MoneyText amount={r.amount} currency={r.currency} strong />,
              },
              { label: 'Reason', value: r.reason },
              {
                label: 'Requested by',
                value: <PersonName userId={r.created_by} name={r.created_by_name} />,
              },
            ]}
          />
        }
        explanation="An approved retention lets the custodian keep this amount instead of remitting it; the full-remittance check allows for it."
        onDecide={(approve, note, key) =>
          custodyService.decideRetention(r.id, { approve, note }, key)
        }
        onDone={(res) => {
          notify.success(res.status === 'APPROVED' ? 'Retention approved.' : 'Retention rejected.');
          onChanged(res);
        }}
        onClose={() => {
          setDeciding(null);
        }}
      />
    );
  }
  return { actionsFor, dialog };
}

export function retentionItems(r: CashRetentionDto, timeZone: string): KeyValueItem[] {
  return [
    { label: 'Custodian', value: retentionCustodian(r) },
    { label: 'Amount to keep', value: <MoneyText amount={r.amount} currency={r.currency} /> },
    { label: 'Reason', value: r.reason },
    {
      label: 'Valid until',
      value: r.valid_until === null ? '—' : formatInstantIn(r.valid_until, timeZone),
    },
    {
      label: 'Requested by',
      value: <PersonName userId={r.created_by} name={r.created_by_name} />,
    },
    { label: 'Requested', value: formatInstantIn(r.created_at, timeZone) },
    {
      label: 'Decided by',
      value: <PersonName userId={r.decided_by} name={r.decided_by_name} />,
    },
    { label: 'Decision note', value: r.decision_note ?? '—' },
  ];
}

export function retentionHistory(r: CashRetentionDto): HistoryEvent[] {
  return [
    {
      key: 'requested',
      at: r.created_at,
      label: 'Requested',
      by: <PersonName userId={r.created_by} name={r.created_by_name} />,
      note: r.reason,
    },
    {
      key: 'decided',
      at: r.decided_at,
      label: DECISION_STATUS_LABELS[r.status],
      by: <PersonName userId={r.decided_by} name={r.decided_by_name} />,
      note: r.decision_note,
    },
  ];
}
