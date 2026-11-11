import { Link } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import type { CashVarianceDto, VarianceEventDto } from '../../../../api/custodyTypes';
import { custodyService } from '../../../../api/services/custodyService';
import { KeyValueGrid, type KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../../components/display/StatusChip';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { hoursPurchasePath } from '../../../../navigation/hoursRoutes';
import { recordPath, type RecordKind } from '../../../../navigation/recordRoutes';
import { caseDetailPath, jobDetailPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { machineText, nameOr } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import type { HistoryEvent } from '../../shared/RecordDetail';
import { useMyUserId } from '../../shared/useFinanceLabels';
import {
  OWN_REQUEST_TOOLTIP,
  VARIANCE_CHECK_LABELS,
  VARIANCE_EVENT_LABELS,
  VARIANCE_KIND_LABELS,
  VARIANCE_OUTCOME_LABELS,
  VARIANCE_SOURCE_LABELS,
  VARIANCE_STATUS_LABELS,
  VARIANCE_STATUS_TONES,
} from './custodyDisplay';
import { useCashPolicy } from './custodyHooks';
import {
  AssignVarianceDialog,
  ExplainVarianceDialog,
  ResolveVarianceDialog,
  WriteOffProposalDialog,
} from './VarianceDialogs';
import { varianceFigure } from './varianceFigures';

export const varianceChip = (v: CashVarianceDto) => (
  <StatusChip
    status={v.status}
    tones={VARIANCE_STATUS_TONES}
    label={VARIANCE_STATUS_LABELS[v.status]}
  />
);

/** Who answers for it: the custodian, or the customer for a customer-hour difference. */
export const varianceCustodian = (v: CashVarianceDto) =>
  v.source_type === 'CUSTOMER_HOUR'
    ? (v.customer_name ?? '—')
    : nameOr(v.staff_member_name, v.staff_member_id);

export const varianceAssignee = (v: CashVarianceDto) => (
  <PersonName userId={v.assignee_user_id ?? null} name={v.assignee_user_name} empty="Unassigned" />
);

const SOURCE_KIND: Readonly<
  Record<
    Exclude<CashVarianceDto['source_type'], 'CUSTOMER_HOUR' | `PETTY_CASH_${string}`>,
    RecordKind
  >
> = {
  TRANSFER: 'CASH_TRANSFER',
  REMITTANCE: 'CASH_REMITTANCE',
  FLOAT: 'CASH_FLOAT',
};

/** The record that opened the variance; customer-hour checks point at the purchase or the job. */
export function varianceSourcePath(v: CashVarianceDto): string | null {
  if (v.source_type !== 'CUSTOMER_HOUR') {
    // petty cash sources have no record kind here yet (DEC-033 web pass)
    const kind = (SOURCE_KIND as Partial<Record<string, RecordKind>>)[v.source_type];
    return kind ? recordPath(kind, v.source_id) : null;
  }
  if (v.purchase_id != null) return hoursPurchasePath(v.purchase_id);
  return v.job_id == null ? null : jobDetailPath(v.job_id);
}

type OpenKind = 'assign' | 'explain' | 'resolve' | 'propose' | 'decide' | 'closure';
type Open = { kind: OpenKind; v: CashVarianceDto } | null;

/**
 * Investigate a variance (assign, explain), close it (or propose its closure), propose or decide a
 * write-off. The person who proposed or opened it never decides: the rules are the tenant's policy
 * and the server applies them too.
 */
export function useVarianceActions(onChanged: (v: CashVarianceDto) => void) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const policy = useCashPolicy();
  const canInvestigate = can(PERMISSIONS.tenantFinanceVariance);
  const canWriteOff = can(PERMISSIONS.tenantFinanceWriteoff);
  const canClose = can(PERMISSIONS.tenantFinanceVarianceClose);
  const secondPerson = policy?.varianceClosureRequiresSecondPerson ?? true;
  const approvalNeeded = (policy?.writeoffRequiresApproval ?? true) || secondPerson;
  const [open, setOpen] = useState<Open>(null);
  const actionsFor = (v: CashVarianceDto): RowAction[] => {
    const go = (kind: OpenKind) => () => {
      setOpen({ kind, v });
    };
    const isOpen = v.status === 'OPEN';
    const unresolved = v.status !== 'RESOLVED';
    const proposedByMe = v.proposed_by !== null && v.proposed_by === me;
    const mine = proposedByMe || (v.opened_by !== null && v.opened_by === me);
    return [
      {
        key: 'assign',
        label: v.assignee_user_id == null ? 'Assign' : 'Reassign',
        hidden: !canInvestigate || !unresolved,
        onClick: go('assign'),
      },
      {
        key: 'explain',
        label: 'Explain',
        hidden: !canInvestigate || !unresolved,
        onClick: go('explain'),
      },
      {
        key: 'resolve',
        label: secondPerson ? 'Propose closure' : 'Resolve',
        hidden: !canInvestigate || !isOpen,
        onClick: go('resolve'),
      },
      {
        key: 'propose',
        label: 'Propose write-off',
        hidden: !canInvestigate || !isOpen || !approvalNeeded || v.unit === 'HOURS',
        onClick: go('propose'),
      },
      {
        key: 'closure',
        label: mine ? `Decide closure (${OWN_REQUEST_TOOLTIP})` : 'Decide closure',
        hidden: !canClose || v.status !== 'CLOSURE_PROPOSED',
        disabled: mine,
        disabledReason: OWN_REQUEST_TOOLTIP,
        onClick: go('closure'),
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
  if (open !== null) {
    const v = open.v;
    const custodian = varianceCustodian(v);
    const shared = { variance: v, custodian, onClose: close };
    const summary = (extra: KeyValueItem[]) => (
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Accountable', value: custodian },
          { label: 'Difference', value: varianceFigure(v, 'amount', true) },
          {
            label: 'Proposed by',
            value: <PersonName userId={v.proposed_by} name={v.proposed_by_name} />,
          },
          ...extra,
          { label: 'Explanation', value: v.proposal_note ?? '—' },
        ]}
      />
    );
    if (open.kind === 'assign') {
      dialog = (
        <AssignVarianceDialog
          {...shared}
          onDone={(r) => {
            done('Variance assigned.', r);
          }}
        />
      );
    } else if (open.kind === 'explain') {
      dialog = (
        <ExplainVarianceDialog
          {...shared}
          onDone={(r) => {
            done('Explanation saved.', r);
          }}
        />
      );
    } else if (open.kind === 'resolve') {
      dialog = (
        <ResolveVarianceDialog
          {...shared}
          allowWriteOff={!approvalNeeded && canWriteOff}
          secondPerson={secondPerson}
          evidenceRequired={policy?.varianceEvidenceRequired ?? false}
          onDone={(r) => {
            done(
              r.status === 'CLOSURE_PROPOSED'
                ? 'Closure proposed; someone else decides it.'
                : 'Variance resolved.',
              r,
            );
          }}
        />
      );
    } else if (open.kind === 'propose') {
      dialog = (
        <WriteOffProposalDialog
          {...shared}
          onDone={(r) => {
            done('Write-off proposed; someone else with the write-off permission decides.', r);
          }}
        />
      );
    } else if (open.kind === 'closure') {
      dialog = (
        <DecisionDialog<CashVarianceDto>
          title="Decide closure"
          kind="approve"
          summary={summary([
            {
              label: 'Proposed outcome',
              value: v.proposed_outcome == null ? '—' : VARIANCE_OUTCOME_LABELS[v.proposed_outcome],
            },
          ])}
          explanation="Approving closes the variance with the proposed outcome. Rejecting returns it to open for more work."
          onDecide={(approve, note, key) =>
            custodyService.decideClosure(v.id, { approve, note }, key)
          }
          onDone={(r) => {
            done(
              r.status === 'RESOLVED'
                ? 'Closure approved.'
                : 'Closure rejected; the variance is open again.',
              r,
            );
          }}
          onClose={close}
        />
      );
    } else {
      dialog = (
        <DecisionDialog<CashVarianceDto>
          title="Decide write-off"
          kind="approve"
          summary={summary([])}
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
  }
  return { actionsFor, dialog };
}

function sourceItem(v: CashVarianceDto): ReactNode {
  const label = VARIANCE_SOURCE_LABELS[v.source_type];
  const to = varianceSourcePath(v);
  return to === null ? (
    label
  ) : (
    <Link component={RouterLink} to={to}>
      {label}
    </Link>
  );
}

function customerHourItems(v: CashVarianceDto): KeyValueItem[] {
  if (v.source_type !== 'CUSTOMER_HOUR') return [];
  return [
    {
      label: 'What was found',
      value: v.check_code == null ? '—' : (VARIANCE_CHECK_LABELS[v.check_code] ?? v.check_code),
    },
    { label: 'Customer', value: v.customer_name ?? '—' },
    {
      label: 'Machine',
      value:
        v.machine_id == null
          ? '—'
          : machineText(v.machine_code ?? null, v.machine_name ?? null, v.machine_id),
    },
    {
      label: 'Purchase',
      value:
        v.purchase_id == null ? (
          '—'
        ) : (
          <Link component={RouterLink} to={hoursPurchasePath(v.purchase_id)}>
            {v.purchase_number ?? 'Open the purchase'}
          </Link>
        ),
    },
    {
      label: 'Job',
      value:
        v.job_id == null ? (
          '—'
        ) : (
          <Link component={RouterLink} to={jobDetailPath(v.job_id)}>
            {v.job_number ?? 'Open the job'}
          </Link>
        ),
    },
  ];
}

export function varianceItems(
  v: CashVarianceDto,
  timeZone: string,
  canOpenCase: boolean,
): KeyValueItem[] {
  const hours = v.source_type === 'CUSTOMER_HOUR';
  return [
    { label: 'From', value: sourceItem(v) },
    { label: 'Kind', value: VARIANCE_KIND_LABELS[v.kind] },
    ...customerHourItems(v),
    ...(hours
      ? []
      : [
          { label: 'Accountable custodian', value: varianceCustodian(v) },
          {
            label: 'Other custodian',
            value:
              v.counterparty_staff_id === null
                ? '—'
                : nameOr(v.counterparty_staff_name, v.counterparty_staff_id),
          },
        ]),
    { label: hours ? 'Expected' : 'Declared', value: varianceFigure(v, 'declared_amount') },
    { label: hours ? 'Found' : 'Received', value: varianceFigure(v, 'received_amount') },
    { label: 'Difference', value: varianceFigure(v, 'amount', true) },
    { label: 'Opened', value: formatInstantIn(v.opened_at, timeZone) },
    { label: 'Assigned to', value: varianceAssignee(v) },
    { label: 'Explanation', value: v.explanation ?? '—' },
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
      label: 'Proposed outcome',
      value: v.proposed_outcome == null ? '—' : VARIANCE_OUTCOME_LABELS[v.proposed_outcome],
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

/** The append-only investigation history, as the timeline shows it. */
export const varianceTimeline = (events: readonly VarianceEventDto[]): HistoryEvent[] =>
  events.map((e) => ({
    key: e.id,
    at: e.occurred_at,
    label: VARIANCE_EVENT_LABELS[e.action],
    by: <PersonName userId={e.actor_user_id} name={e.actor_user_name} empty="Automatically" />,
    note: e.note,
  }));

/** The history timeline of one variance; reload after every command. */
export function useVarianceTimeline(varianceId: string | undefined) {
  const load = useCallback(
    (signal: AbortSignal) => custodyService.varianceHistory(varianceId ?? '', signal),
    [varianceId],
  );
  return useAsyncResource(load, [varianceId], varianceId !== undefined);
}
