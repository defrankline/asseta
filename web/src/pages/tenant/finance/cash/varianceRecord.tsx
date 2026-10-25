import { Link } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import type { CashVarianceDto } from '../../../../api/custodyTypes';
import { custodyService } from '../../../../api/services/custodyService';
import { KeyValueGrid, type KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { recordPath, type RecordKind } from '../../../../navigation/recordRoutes';
import { caseDetailPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { nameOr } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import type { HistoryEvent } from '../../shared/RecordDetail';
import { useMyUserId } from '../../shared/useFinanceLabels';
import {
  OWN_REQUEST_TOOLTIP,
  VARIANCE_OUTCOME_LABELS,
  VARIANCE_SOURCE_LABELS,
  VARIANCE_STATUS_LABELS,
  VARIANCE_STATUS_TONES,
} from './custodyDisplay';
import { useCashPolicy } from './custodyHooks';
import { ResolveVarianceDialog, WriteOffProposalDialog } from './VarianceDialogs';

export const varianceChip = (v: CashVarianceDto) => (
  <StatusChip
    status={v.status}
    tones={VARIANCE_STATUS_TONES}
    label={VARIANCE_STATUS_LABELS[v.status]}
  />
);

export const varianceCustodian = (v: CashVarianceDto) =>
  nameOr(v.staff_member_name, v.staff_member_id);

const SOURCE_KIND: Readonly<Record<CashVarianceDto['source_type'], RecordKind>> = {
  TRANSFER: 'CASH_TRANSFER',
  REMITTANCE: 'CASH_REMITTANCE',
  FLOAT: 'CASH_FLOAT',
};

/** The record whose declared ≠ received amount opened the variance. */
export const varianceSourcePath = (v: CashVarianceDto) =>
  recordPath(SOURCE_KIND[v.source_type], v.source_id);

type Open = { kind: 'resolve' | 'propose' | 'decide'; v: CashVarianceDto } | null;

/**
 * Resolve, propose a write-off, or decide a proposed write-off (list row and detail page). The
 * proposer never decides; whether a write-off needs approval is the tenant's CASH_CUSTODY policy.
 */
export function useVarianceActions(onChanged: (v: CashVarianceDto) => void) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const policy = useCashPolicy();
  const canResolve = can(PERMISSIONS.tenantFinanceVariance);
  const canWriteOff = can(PERMISSIONS.tenantFinanceWriteoff);
  const approvalNeeded = policy?.writeoffRequiresApproval ?? true;
  const [open, setOpen] = useState<Open>(null);
  const actionsFor = (v: CashVarianceDto): RowAction[] => {
    const go = (kind: 'resolve' | 'propose' | 'decide') => () => {
      setOpen({ kind, v });
    };
    const proposedByMe = v.proposed_by !== null && v.proposed_by === me;
    return [
      {
        key: 'resolve',
        label: 'Resolve',
        hidden: !canResolve || v.status !== 'OPEN',
        onClick: go('resolve'),
      },
      {
        key: 'propose',
        label: 'Propose write-off',
        hidden: !canResolve || v.status !== 'OPEN' || !approvalNeeded,
        onClick: go('propose'),
      },
      {
        key: 'decide',
        label: proposedByMe
          ? `Approve / reject write-off (${OWN_REQUEST_TOOLTIP})`
          : 'Approve / reject write-off',
        hidden: !canWriteOff || v.status !== 'WRITE_OFF_PROPOSED',
        disabled: proposedByMe,
        disabledReason: OWN_REQUEST_TOOLTIP,
        onClick: go('decide'),
      },
    ];
  };
  const done = (message: string, v: CashVarianceDto) => {
    notify.success(message);
    onChanged(v);
  };
  const close = () => {
    setOpen(null);
  };
  let dialog: ReactNode = null;
  if (open?.kind === 'resolve') {
    dialog = (
      <ResolveVarianceDialog
        variance={open.v}
        custodian={varianceCustodian(open.v)}
        allowWriteOff={!approvalNeeded && canWriteOff}
        onDone={(v) => {
          done('Variance resolved.', v);
        }}
        onClose={close}
      />
    );
  } else if (open?.kind === 'propose') {
    dialog = (
      <WriteOffProposalDialog
        variance={open.v}
        custodian={varianceCustodian(open.v)}
        onDone={(v) => {
          done('Write-off proposed; someone else with the write-off permission decides.', v);
        }}
        onClose={close}
      />
    );
  } else if (open?.kind === 'decide') {
    const v = open.v;
    dialog = (
      <DecisionDialog<CashVarianceDto>
        title="Decide write-off"
        kind="approve"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Accountable custodian', value: varianceCustodian(v) },
              {
                label: 'Difference',
                value: <MoneyText amount={v.amount} currency={v.currency} strong />,
              },
              {
                label: 'Proposed by',
                value: <PersonName userId={v.proposed_by} name={v.proposed_by_name} />,
              },
              { label: 'Explanation', value: v.proposal_note ?? '—' },
            ]}
          />
        }
        explanation="Approving resolves the variance as written off and lowers the custodian's expected balance by the difference. Rejecting returns it to open."
        onDecide={(approve, note, key) =>
          custodyService.decideWriteOff(v.id, { approve, note }, key)
        }
        onDone={(r) => {
          done(
            r.status === 'RESOLVED'
              ? 'Write-off approved.'
              : 'Write-off rejected; the variance is open again.',
            r,
          );
        }}
        onClose={close}
      />
    );
  }
  return { actionsFor, dialog };
}

export function varianceItems(
  v: CashVarianceDto,
  timeZone: string,
  canOpenCase: boolean,
): KeyValueItem[] {
  return [
    {
      label: 'From',
      value: (
        <Link component={RouterLink} to={varianceSourcePath(v)}>
          {VARIANCE_SOURCE_LABELS[v.source_type]}
        </Link>
      ),
    },
    { label: 'Accountable custodian', value: varianceCustodian(v) },
    {
      label: 'Other custodian',
      value:
        v.counterparty_staff_id === null
          ? '—'
          : nameOr(v.counterparty_staff_name, v.counterparty_staff_id),
    },
    { label: 'Declared', value: <MoneyText amount={v.declared_amount} currency={v.currency} /> },
    { label: 'Received', value: <MoneyText amount={v.received_amount} currency={v.currency} /> },
    { label: 'Difference', value: <MoneyText amount={v.amount} currency={v.currency} strong /> },
    { label: 'Opened', value: formatInstantIn(v.opened_at, timeZone) },
    {
      label: 'Investigation',
      value:
        v.case_id === null ? (
          '—'
        ) : canOpenCase ? (
          <Link component={RouterLink} to={caseDetailPath(v.case_id)}>
            Open investigation
          </Link>
        ) : (
          'Opened'
        ),
    },
    {
      label: 'Outcome',
      value: v.outcome === null ? '—' : VARIANCE_OUTCOME_LABELS[v.outcome],
    },
    {
      label: 'Resolved by',
      value: <PersonName userId={v.resolved_by} name={v.resolved_by_name} />,
    },
  ];
}

export function varianceHistory(v: CashVarianceDto): HistoryEvent[] {
  return [
    {
      key: 'opened',
      at: v.opened_at,
      label: `Opened from a ${VARIANCE_SOURCE_LABELS[v.source_type].toLowerCase()}`,
      by: <PersonName userId={v.opened_by} name={v.opened_by_name} empty="Automatically" />,
    },
    {
      key: 'proposed',
      at: v.proposed_at,
      label: 'Write-off proposed',
      by: <PersonName userId={v.proposed_by} name={v.proposed_by_name} />,
      note: v.proposal_note,
    },
    {
      key: 'resolved',
      at: v.resolved_at,
      label: v.outcome === null ? 'Resolved' : `Resolved: ${VARIANCE_OUTCOME_LABELS[v.outcome]}`,
      by: <PersonName userId={v.resolved_by} name={v.resolved_by_name} />,
      note: v.resolution_note,
    },
  ];
}
