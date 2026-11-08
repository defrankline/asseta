import { Alert, Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useMutationGuard } from '../../../access/useCanMutate';
import { caseService } from '../../../api/services/caseService';
import { expenseService } from '../../../api/services/expenseService';
import type { AnomalyCaseDetailDto, AnomalyCaseDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { NEUTRAL_SIGNAL_NOTICE } from '../../../components/intelligence/signalText';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { jobDetailPath, machineDetailPath, ROUTES } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { ENTITY, entityKey } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { formatInstantIn } from '../../../utils/time';
import { ExpenseDetailsDrawer } from '../expenses/ExpenseDetailsDrawer';
import { DecisionDialog } from '../shared/DecisionDialog';
import { PersonName } from '../shared/PersonName';
import { useMyUserId } from '../shared/useFinanceLabels';
import { useStaffLabels } from '../shared/useFinanceLabels';
import { useMachineLabels } from '../shared/useMachineLabels';
import { AssignCaseDialog, ReopenCaseDialog, ResolveCaseDialog } from './CaseDialogs';
import {
  CASE_OWN_CLOSURE_TEXT,
  CASE_STATUS_LABELS,
  CASE_STATUS_TONES,
  OUTCOME_LABELS,
  OUTCOME_TONES,
  policyVersionLabel,
  SEVERITY_LABELS,
  SEVERITY_TONES,
  subjectPath,
  SUBJECT_TYPE_LABELS,
} from './caseDisplay';
import { EvidenceSection, NotesSection, OutcomesSection } from './CaseSections';
import { JobNumber, SubjectLabel } from './SubjectLabel';

type Dialog = 'assign' | 'resolve' | 'reopen' | 'closure' | null;

/** Loads one expense and shows its evidence drawer (receipts, GPS, approval). */
function ExpenseDrawer({
  expenseId,
  timeZone,
  onClose,
}: {
  expenseId: string;
  timeZone: string;
  onClose: () => void;
}) {
  const load = useCallback(
    (signal: AbortSignal) => expenseService.get(expenseId, signal),
    [expenseId],
  );
  const res = useAsyncResource(load);
  if (res.error !== null) {
    return (
      <Alert severity="warning" onClose={onClose}>
        Could not open the expense: {res.error.message}
      </Alert>
    );
  }
  return res.data === null ? null : (
    <ExpenseDetailsDrawer expense={res.data} timeZone={timeZone} onClose={onClose} />
  );
}

function CaseStatusChips({ c }: { c: AnomalyCaseDto }) {
  return (
    <>
      <StatusChip
        status={c.status}
        tones={CASE_STATUS_TONES}
        label={CASE_STATUS_LABELS[c.status]}
      />
      <StatusChip status={c.severity} tones={SEVERITY_TONES} label={SEVERITY_LABELS[c.severity]} />
      {c.latest_outcome != null && (
        <StatusChip
          status={c.latest_outcome}
          tones={OUTCOME_TONES}
          label={OUTCOME_LABELS[c.latest_outcome]}
        />
      )}
    </>
  );
}

function CaseSummary({
  c,
  timeZone,
  onOpenExpense,
}: {
  c: AnomalyCaseDto;
  timeZone: string;
  onOpenExpense: (id: string) => void;
}) {
  const machineName = useMachineLabels();
  const staffName = useStaffLabels();
  const label = (
    <SubjectLabel
      subjectType={c.subject_type}
      subjectId={c.subject_id}
      machineName={machineName}
      staffName={staffName}
    />
  );
  const path = subjectPath(c);
  let subject = label;
  if (path !== null) subject = <RouterLink to={path}>{label}</RouterLink>;
  else if (c.subject_type === 'EXPENSE') {
    subject = (
      <Button
        size="small"
        onClick={() => {
          onOpenExpense(c.subject_id);
        }}
      >
        {label}
      </Button>
    );
  }
  const related = [
    ...(c.machine_id !== null && c.subject_type !== 'MACHINE'
      ? [
          {
            label: 'Machine',
            value: (
              <RouterLink to={machineDetailPath(c.machine_id)}>
                {machineName(c.machine_id)}
              </RouterLink>
            ),
          },
        ]
      : []),
    ...(c.job_id !== null && c.subject_type !== 'JOB'
      ? [
          {
            label: 'Job',
            value: (
              <RouterLink to={jobDetailPath(c.job_id)}>
                <JobNumber jobId={c.job_id} />
              </RouterLink>
            ),
          },
        ]
      : []),
  ];
  return (
    <DetailSection title="Summary">
      <KeyValueGrid
        columns={3}
        items={[
          { label: `Subject (${SUBJECT_TYPE_LABELS[c.subject_type]})`, value: subject },
          ...related,
          {
            label: 'Assignee',
            value: <PersonName userId={c.assignee_user_id} empty="Unassigned" />,
          },
          { label: 'Opened', value: formatInstantIn(c.opened_at, timeZone) },
          { label: 'Last signal', value: formatInstantIn(c.last_signal_at, timeZone) },
          {
            label: 'Resolved',
            value:
              c.resolved_at === null ? (
                'Not resolved'
              ) : (
                <>
                  {formatInstantIn(c.resolved_at, timeZone)} by{' '}
                  <PersonName userId={c.resolved_by} />
                </>
              ),
          },
          { label: 'Signals', value: String(c.signal_count) },
          { label: 'Policy version', value: policyVersionLabel(c.policy_version) },
        ]}
      />
    </DetailSection>
  );
}

/** One investigation case: summary, linked evidence, append-only notes, outcomes and review commands. */
export function CaseDetailPage() {
  const { caseId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const can = useMutationGuard();
  const canManage = can(PERMISSIONS.tenantCaseManage);
  const canResolve = can(PERMISSIONS.tenantCaseResolve);
  const me = useMyUserId();
  const [dialog, setDialog] = useState<Dialog>(null);
  const [expenseId, setExpenseId] = useState<string | null>(null);
  const load = useCallback((signal: AbortSignal) => caseService.get(caseId, signal), [caseId]);
  const res = useAsyncResource(load);
  const reload = res.reload;
  useLiveRefresh([entityKey(ENTITY.anomalyCase, caseId)], reload);
  const c = res.data?.case ?? null;
  const resolved = c?.status === 'RESOLVED';
  const closurePending = c !== null && !resolved && c.closure_proposed_at != null;
  const closureMine = closurePending && me !== null && c.closure_proposed_by === me;
  const actions: RowAction[] = [
    {
      key: 'assign',
      label: c?.assignee_user_id == null ? 'Assign' : 'Reassign',
      hidden: !canManage || resolved,
      onClick: () => {
        setDialog('assign');
      },
    },
    {
      key: 'resolve',
      label: 'Resolve',
      hidden: !canResolve || resolved || closurePending,
      onClick: () => {
        setDialog('resolve');
      },
    },
    {
      key: 'closure',
      label: closureMine ? `Decide closure (${CASE_OWN_CLOSURE_TEXT})` : 'Decide closure',
      hidden: !canResolve || !closurePending,
      disabled: closureMine,
      disabledReason: CASE_OWN_CLOSURE_TEXT,
      onClick: () => {
        setDialog('closure');
      },
    },
    {
      key: 'reopen',
      label: 'Reopen',
      hidden: !canManage || !resolved,
      onClick: () => {
        setDialog('reopen');
      },
    },
  ];
  const close = () => {
    setDialog(null);
  };
  const done = (message: string) => () => {
    notify.success(message);
    reload();
  };
  return (
    <>
      <EntityDetailsLayout
        title={c === null ? 'Investigation case' : `${c.case_number} · ${c.title}`}
        subtitle="Investigation case"
        back={{ label: 'All investigations', to: ROUTES.tenantCases }}
        {...(c !== null
          ? {
              status: <CaseStatusChips c={c} />,
              actions: <ActionButtons actions={actions} primaryKey="resolve" />,
            }
          : {})}
      >
        <Alert severity="info">{NEUTRAL_SIGNAL_NOTICE}</Alert>
        {closurePending && c.closure_outcome != null && (
          <Alert severity="warning">
            Closure proposed as {OUTCOME_LABELS[c.closure_outcome]}: {c.closure_explanation ?? '—'}.
            Someone else decides it.
          </Alert>
        )}
        <AsyncContent
          resource={res}
          errorTitle="Could not load the case"
          loadingLabel="Loading case"
        >
          {(detail) => (
            <Box className="flex flex-col gap-6">
              <CaseSummary c={detail.case} timeZone={timeZone} onOpenExpense={setExpenseId} />
              <EvidenceSection detail={detail} timeZone={timeZone} onOpenExpense={setExpenseId} />
              <NotesSection
                caseId={detail.case.id}
                notes={detail.notes}
                timeZone={timeZone}
                canAdd={canManage}
                onAdded={() => {
                  notify.success('Note added.');
                  reload();
                }}
              />
              <OutcomesSection outcomes={detail.outcomes} timeZone={timeZone} />
            </Box>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {c !== null && dialog === 'assign' && (
        <AssignCaseDialog
          case={c}
          onClose={close}
          onDone={done('Case assigned.')}
          onReload={reload}
        />
      )}
      {c !== null && dialog === 'resolve' && (
        <ResolveCaseDialog
          case={c}
          onClose={close}
          onDone={(d) => {
            done(
              d.case.status === 'RESOLVED'
                ? 'Outcome recorded.'
                : 'Closure proposed; someone else decides it.',
            )();
          }}
          onReload={reload}
        />
      )}
      {c !== null && dialog === 'closure' && (
        <DecisionDialog<AnomalyCaseDetailDto>
          title={`Decide closure of ${c.case_number}`}
          kind="approve"
          summary={
            <KeyValueGrid
              columns={1}
              items={[
                {
                  label: 'Proposed outcome',
                  value: c.closure_outcome == null ? '—' : OUTCOME_LABELS[c.closure_outcome],
                },
                { label: 'Explanation', value: c.closure_explanation ?? '—' },
                {
                  label: 'Proposed by',
                  value: (
                    <PersonName
                      userId={c.closure_proposed_by ?? null}
                      name={c.closure_proposed_by_name}
                    />
                  ),
                },
              ]}
            />
          }
          explanation="Approving records this outcome and resolves the case. Rejecting returns it to review."
          onDecide={(approve, note, key) =>
            caseService.decideResolution(c.id, { approve, note, version: c.version }, key)
          }
          onDone={(d) => {
            done(d.case.status === 'RESOLVED' ? 'Closure approved.' : 'Closure rejected.')();
          }}
          onClose={close}
        />
      )}
      {c !== null && dialog === 'reopen' && (
        <ReopenCaseDialog
          case={c}
          onClose={close}
          onDone={done('Case reopened.')}
          onReload={reload}
        />
      )}
      {expenseId !== null && (
        <ExpenseDrawer
          expenseId={expenseId}
          timeZone={timeZone}
          onClose={() => {
            setExpenseId(null);
          }}
        />
      )}
    </>
  );
}
