import { Link } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import type { CustodyAdjustmentDto } from '../../../../api/custodyTypes';
import { custodyService } from '../../../../api/services/custodyService';
import { KeyValueGrid, type KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { RECORD_KIND_BY_ENTITY, recordPath } from '../../../../navigation/recordRoutes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { nameOr } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import type { HistoryEvent } from '../../shared/RecordDetail';
import { useMyUserId } from '../../shared/useFinanceLabels';
import {
  ADJUSTMENT_KIND_LABELS,
  DECISION_STATUS_LABELS,
  DECISION_STATUS_TONES,
  entityTypeLabel,
  OWN_REQUEST_TOOLTIP,
} from './custodyDisplay';

export const adjustmentChip = (a: CustodyAdjustmentDto) => (
  <StatusChip
    status={a.status}
    tones={DECISION_STATUS_TONES}
    label={DECISION_STATUS_LABELS[a.status]}
  />
);

export const adjustmentCustodian = (a: CustodyAdjustmentDto) =>
  nameOr(a.staff_member_name, a.staff_member_id);

/** The record an adjustment reverses: a link when it has its own page. */
function reversed(a: CustodyAdjustmentDto): ReactNode {
  if (a.reverses_entity_type === null) return '—';
  const label = entityTypeLabel(a.reverses_entity_type);
  const kind = RECORD_KIND_BY_ENTITY[a.reverses_entity_type];
  if (kind === undefined || a.reverses_entity_id === null) return label;
  return (
    <Link component={RouterLink} to={recordPath(kind, a.reverses_entity_id)}>
      {label}
    </Link>
  );
}

/** Approve / reject a custody adjustment (list row and detail page); never your own proposal. */
export function useAdjustmentActions(onChanged: (a: CustodyAdjustmentDto) => void) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const canDecide = can(PERMISSIONS.tenantFinanceAdjustmentApprove);
  const [deciding, setDeciding] = useState<CustodyAdjustmentDto | null>(null);
  const actionsFor = (a: CustodyAdjustmentDto): RowAction[] => {
    const mine = a.created_by !== null && a.created_by === me;
    return [
      {
        key: 'decide',
        label: mine ? `Approve / reject (${OWN_REQUEST_TOOLTIP})` : 'Approve / reject',
        hidden: !canDecide || a.status !== 'PENDING',
        disabled: mine,
        disabledReason: OWN_REQUEST_TOOLTIP,
        onClick: () => {
          setDeciding(a);
        },
      },
    ];
  };
  let dialog: ReactNode = null;
  if (deciding !== null) {
    const a = deciding;
    dialog = (
      <DecisionDialog<CustodyAdjustmentDto>
        title="Decide custody adjustment"
        kind="approve"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: adjustmentCustodian(a) },
              { label: 'Kind', value: ADJUSTMENT_KIND_LABELS[a.kind] },
              {
                label: 'Amount',
                value: <MoneyText amount={a.amount} currency={a.currency} strong />,
              },
              { label: 'Reason', value: a.reason },
              {
                label: 'Proposed by',
                value: <PersonName userId={a.created_by} name={a.created_by_name} />,
              },
              {
                label: 'Record reversed',
                value:
                  a.reverses_entity_type === null ? '—' : entityTypeLabel(a.reverses_entity_type),
              },
            ]}
          />
        }
        explanation="An approved adjustment changes the custodian's expected balance by the signed amount; a rejected one never counts."
        onDecide={(approve, note, key) =>
          custodyService.decideAdjustment(a.id, { approve, note }, key)
        }
        onDone={(res) => {
          notify.success(
            res.status === 'APPROVED' ? 'Adjustment approved.' : 'Adjustment rejected.',
          );
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

export function adjustmentItems(a: CustodyAdjustmentDto, timeZone: string): KeyValueItem[] {
  return [
    { label: 'Custodian', value: adjustmentCustodian(a) },
    { label: 'Kind', value: ADJUSTMENT_KIND_LABELS[a.kind] },
    { label: 'Amount', value: <MoneyText amount={a.amount} currency={a.currency} /> },
    { label: 'Effective', value: formatInstantIn(a.occurred_at, timeZone) },
    { label: 'Reason', value: a.reason },
    { label: 'Record reversed', value: reversed(a) },
    {
      label: 'Proposed by',
      value: <PersonName userId={a.created_by} name={a.created_by_name} />,
    },
    {
      label: 'Decided by',
      value: <PersonName userId={a.decided_by} name={a.decided_by_name} />,
    },
    { label: 'Decision note', value: a.decision_note ?? '—' },
  ];
}

export function adjustmentHistory(a: CustodyAdjustmentDto): HistoryEvent[] {
  return [
    {
      key: 'proposed',
      at: a.created_at,
      label: 'Proposed',
      by: <PersonName userId={a.created_by} name={a.created_by_name} />,
      note: a.reason,
    },
    {
      key: 'decided',
      at: a.decided_at,
      label: DECISION_STATUS_LABELS[a.status],
      by: <PersonName userId={a.decided_by} name={a.decided_by_name} />,
      note: a.decision_note,
    },
  ];
}
