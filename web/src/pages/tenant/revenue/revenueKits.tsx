import { Button, Link } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type {
  NonRevenueActivityDto,
  NonRevenueApprovalDto,
  RevenueDifferenceDto,
} from '../../../api/types';
import type { KeyValueItem } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import {
  caseDetailPath,
  dailySheetDayPath,
  engineHoursMachinePath,
  jobDetailPath,
} from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { DecideButton } from '../engineHours/MeterDecisionDialog';
import { PersonName } from '../shared/PersonName';
import type { HistoryEvent } from '../shared/RecordDetail';
import {
  ADJUSTMENT_CAUSE_LABELS,
  activityTypeLabel,
  APPROVAL_STATUS_LABELS,
  APPROVAL_STATUS_TONES,
  DIFFERENCE_STATUS_LABELS,
  DIFFERENCE_STATUS_TONES,
  OWN_REQUEST_TEXT,
} from './revenueDisplay';
import { differenceMachine, differencePeriod } from './revenueDisplay';
import {
  DecideDifferenceDialog,
  DecideNonRevenueDialog,
  ExplainDifferenceDialog,
  ExplainNonRevenueDialog,
} from './RevenueDialogs';

export const differenceChip = (d: RevenueDifferenceDto) => (
  <StatusChip
    status={d.status}
    tones={DIFFERENCE_STATUS_TONES}
    label={DIFFERENCE_STATUS_LABELS[d.status]}
  />
);

export const approvalChip = (a: { status: string }) => (
  <StatusChip
    status={a.status}
    tones={APPROVAL_STATUS_TONES}
    label={APPROVAL_STATUS_LABELS[a.status] ?? a.status}
  />
);

const jobLink = (jobId: string | null, jobNumber: string | null | undefined): ReactNode =>
  jobId === null ? (
    '—'
  ) : (
    <Link component={RouterLink} to={jobDetailPath(jobId)}>
      {jobNumber ?? 'Open job'}
    </Link>
  );

/** Explain / decide commands, dialogs, details and history of revenue differences. */
export interface DifferenceKit {
  /** List cell: Decide / Confirm, disabled with the reason on your own explanation. */
  decideCell: (d: RevenueDifferenceDto) => ReactNode;
  actionsFor: (d: RevenueDifferenceDto) => RowAction[];
  dialog: ReactNode;
  items: (d: RevenueDifferenceDto) => KeyValueItem[];
  history: (d: RevenueDifferenceDto) => HistoryEvent[];
  links: (d: RevenueDifferenceDto) => ReactNode;
}

type DifferenceDialog =
  { kind: 'explain'; d: RevenueDifferenceDto } | { kind: 'decide'; d: RevenueDifferenceDto } | null;

/** Explain (tenant.revenue.explain) and decide (tenant.revenue.decide; never by the explainer). */
export function useDifferenceKit(onChanged: (d: RevenueDifferenceDto) => void): DifferenceKit {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const { me } = useSession();
  const canExplain = useCanMutate(PERMISSIONS.tenantRevenueExplain);
  const canDecide = useCanMutate(PERMISSIONS.tenantRevenueDecide);
  const [dialog, setDialog] = useState<DifferenceDialog>(null);
  const own = (d: RevenueDifferenceDto) =>
    me !== null && d.explained_by !== null && d.explained_by === me.user_id;
  const actionsFor = (d: RevenueDifferenceDto): RowAction[] => [
    {
      key: 'explain',
      label: 'Explain',
      hidden: !canExplain || d.status !== 'OPEN',
      onClick: () => {
        setDialog({ kind: 'explain', d });
      },
    },
    {
      key: 'decide',
      label: d.status === 'OPEN' ? 'Confirm difference' : 'Decide',
      hidden: !canDecide || (d.status !== 'OPEN' && d.status !== 'EXPLANATION_PROPOSED'),
      disabled: own(d),
      disabledReason: OWN_REQUEST_TEXT,
      onClick: () => {
        setDialog({ kind: 'decide', d });
      },
    },
  ];
  const decideCell = (d: RevenueDifferenceDto) =>
    canDecide && (d.status === 'OPEN' || d.status === 'EXPLANATION_PROPOSED') ? (
      <DecideButton
        proposedBy={d.status === 'OPEN' ? null : d.explained_by}
        label={d.status === 'OPEN' ? 'Confirm' : 'Decide'}
        onClick={() => {
          setDialog({ kind: 'decide', d });
        }}
      />
    ) : null;
  const items = (d: RevenueDifferenceDto): KeyValueItem[] => [
    { label: 'Machine', value: differenceMachine(d) },
    { label: 'Period', value: differencePeriod(d) },
    { label: 'Job', value: jobLink(d.job_id, d.job_number) },
    {
      label: 'Expected revenue',
      value: <MoneyText amount={d.expected_amount} currency={d.currency} />,
    },
    {
      label: 'Of which unexplained hours expected as revenue',
      value: (
        <>
          <MoneyText amount={d.unexplained_expected_amount} currency={d.currency} /> (
          {d.unexplained_hours} h)
        </>
      ),
    },
    {
      label: 'Work still in progress',
      value: <MoneyText amount={d.in_progress_amount} currency={d.currency} />,
    },
    {
      label: 'Money attributed',
      value: <MoneyText amount={d.attributed_amount} currency={d.currency} />,
    },
    {
      label: 'Difference to explain',
      value: <MoneyText amount={d.difference} currency={d.currency} strong />,
    },
    ...(d.adjusted_difference == null
      ? []
      : [
          {
            label: 'Difference after later changes',
            value: <MoneyText amount={d.adjusted_difference} currency={d.currency} strong />,
          },
        ]),
    { label: 'Customer-work hours', value: `${d.customer_work_hours} h` },
    { label: 'Non-revenue hours (approved)', value: `${d.non_revenue_hours} h` },
    { label: 'Reason', value: d.reason_name ?? '—' },
    { label: 'Explanation', value: d.explanation_note ?? '—' },
    {
      label: 'Explained by',
      value: <PersonName userId={d.explained_by} name={d.explained_by_name} />,
    },
    { label: 'Decided by', value: <PersonName userId={d.decided_by} name={d.decided_by_name} /> },
    { label: 'Decision note', value: d.decision_note ?? '—' },
    {
      label: 'Investigation',
      value:
        d.case_id === null ? (
          'None'
        ) : (
          <Link component={RouterLink} to={caseDetailPath(d.case_id)}>
            {d.case_number ?? 'Open investigation'}
          </Link>
        ),
    },
    { label: 'Last computed', value: formatInstantIn(d.computed_at, timeZone) },
    { label: 'Policy', value: d.policy_version },
  ];
  const history = (d: RevenueDifferenceDto): HistoryEvent[] => [
    { key: 'opened', at: d.opened_at, label: 'Difference opened' },
    {
      key: 'explained',
      at: d.explained_at,
      label: 'Explanation proposed',
      by: <PersonName userId={d.explained_by} name={d.explained_by_name} />,
      note: d.explanation_note,
    },
    {
      key: 'decided',
      at: d.decided_at,
      label: DIFFERENCE_STATUS_LABELS[d.status],
      by: <PersonName userId={d.decided_by} name={d.decided_by_name} />,
      note: d.decision_note,
    },
    ...(d.adjustments ?? []).map((a) => ({
      key: `adj-${a.id}`,
      at: a.created_at,
      label: `Adjusted: ${ADJUSTMENT_CAUSE_LABELS[a.cause_type] ?? a.cause_type} (${a.previous_difference} → ${a.new_difference} ${d.currency})`,
      by: <PersonName userId={a.created_by} name={a.created_by_name} />,
    })),
  ];
  const links = (d: RevenueDifferenceDto) => (
    <div className="flex flex-wrap gap-2">
      <Button component={RouterLink} to={dailySheetDayPath(d.machine_id, d.local_from)}>
        Daily sheet
      </Button>
      <Button component={RouterLink} to={engineHoursMachinePath(d.machine_id)}>
        Engine hours
      </Button>
    </div>
  );
  const close = () => {
    setDialog(null);
  };
  const node =
    dialog === null ? null : dialog.kind === 'explain' ? (
      <ExplainDifferenceDialog
        difference={dialog.d}
        onClose={close}
        onDone={(d) => {
          notify.success('Explanation proposed; someone else decides it.');
          onChanged(d);
        }}
      />
    ) : (
      <DecideDifferenceDialog
        difference={dialog.d}
        timeZone={timeZone}
        onClose={close}
        onDone={(d) => {
          notify.success(`Difference: ${DIFFERENCE_STATUS_LABELS[d.status].toLowerCase()}.`);
          onChanged(d);
        }}
      />
    );
  return { decideCell, actionsFor, dialog: node, items, history, links };
}

/** Decide command, dialog, details and history of non-revenue approvals. */
export interface ApprovalKit {
  /** List cell: Decide, disabled with the reason on your own explanation. */
  decideCell: (a: NonRevenueApprovalDto) => ReactNode;
  actionsFor: (a: NonRevenueApprovalDto) => RowAction[];
  dialog: ReactNode;
  items: (a: NonRevenueApprovalDto) => KeyValueItem[];
  history: (a: NonRevenueApprovalDto) => HistoryEvent[];
}

/** Decide (tenant.revenue.decide), never one's own explanation. */
export function useApprovalKit(onChanged: (a: NonRevenueApprovalDto) => void): ApprovalKit {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const { me } = useSession();
  const canDecide = useCanMutate(PERMISSIONS.tenantRevenueDecide);
  const [deciding, setDeciding] = useState<NonRevenueApprovalDto | null>(null);
  const actionsFor = (a: NonRevenueApprovalDto): RowAction[] => [
    {
      key: 'decide',
      label: 'Decide',
      hidden: !canDecide || a.status !== 'PROPOSED',
      disabled: me !== null && a.proposed_by === me.user_id,
      disabledReason: OWN_REQUEST_TEXT,
      onClick: () => {
        setDeciding(a);
      },
    },
  ];
  const decideCell = (a: NonRevenueApprovalDto) =>
    canDecide && a.status === 'PROPOSED' ? (
      <DecideButton
        proposedBy={a.proposed_by}
        onClick={() => {
          setDeciding(a);
        }}
      />
    ) : null;
  const items = (a: NonRevenueApprovalDto): KeyValueItem[] => [
    { label: 'Machine', value: differenceMachine(a) },
    { label: 'Job', value: jobLink(a.job_id, a.job_number) },
    { label: 'Type', value: activityTypeLabel(a.activity_type) },
    { label: 'Hours', value: `${a.hours} h` },
    { label: 'From', value: formatInstantIn(a.started_at, timeZone) },
    { label: 'To', value: formatInstantIn(a.ended_at, timeZone) },
    { label: 'Reason', value: a.reason_name ?? '—' },
    { label: 'What happened', value: a.note },
    {
      label: 'Explained by',
      value: <PersonName userId={a.proposed_by} name={a.proposed_by_name} />,
    },
    { label: 'Decided by', value: <PersonName userId={a.decided_by} name={a.decided_by_name} /> },
    { label: 'Decision note', value: a.decision_note ?? '—' },
    { label: 'Policy', value: a.policy_version },
  ];
  const history = (a: NonRevenueApprovalDto): HistoryEvent[] => [
    {
      key: 'proposed',
      at: a.proposed_at,
      label: 'Explanation proposed',
      by: <PersonName userId={a.proposed_by} name={a.proposed_by_name} />,
      note: a.note,
    },
    {
      key: 'decided',
      at: a.status === 'PROPOSED' ? null : a.decided_at,
      label: APPROVAL_STATUS_LABELS[a.status] ?? a.status,
      by: <PersonName userId={a.decided_by} name={a.decided_by_name} />,
      note: a.decision_note,
    },
  ];
  const dialog =
    deciding === null ? null : (
      <DecideNonRevenueDialog
        approval={deciding}
        timeZone={timeZone}
        onClose={() => {
          setDeciding(null);
        }}
        onDone={(a) => {
          notify.success(
            a.status === 'APPROVED'
              ? 'Approved as non-revenue time.'
              : 'Rejected; the time counts as revenue.',
          );
          onChanged(a);
        }}
      />
    );
  return { decideCell, actionsFor, dialog, items, history };
}

/** "Explain" for non-revenue time (tenant.revenue.explain): not yet explained or rejected before. */
export function useExplainActivity(onChanged: () => void): {
  canExplain: (a: NonRevenueActivityDto) => boolean;
  open: (a: NonRevenueActivityDto) => void;
  dialog: ReactNode;
} {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const allowed = useCanMutate(PERMISSIONS.tenantRevenueExplain);
  const [explaining, setExplaining] = useState<NonRevenueActivityDto | null>(null);
  const dialog =
    explaining === null ? null : (
      <ExplainNonRevenueDialog
        activity={explaining}
        timeZone={timeZone}
        onClose={() => {
          setExplaining(null);
        }}
        onDone={(a) => {
          notify.success(
            a.status === 'APPROVED'
              ? 'Recorded as non-revenue time.'
              : 'Explanation proposed; someone else approves it.',
          );
          onChanged();
        }}
      />
    );
  return {
    canExplain: (a) =>
      allowed && (a.approval_status === 'NONE' || a.approval_status === 'REJECTED'),
    open: setExplaining,
    dialog,
  };
}
