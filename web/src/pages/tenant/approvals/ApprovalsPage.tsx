import { Alert, Box, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { approvalService, expenseService } from '../../../api/services/expenseService';
import type { ApprovalRequestDto, ApprovalStatus, ExpenseDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { ErrorState } from '../../../components/feedback/ErrorState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { toApiError, type ApiError } from '../../../api/ApiError';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { DecisionDialog } from '../shared/DecisionDialog';
import { APPROVAL_STATUS_OPTIONS, APPROVAL_STATUS_TONES } from '../shared/financeDisplay';
import { PersonName } from '../shared/PersonName';
import { useMyUserId } from '../shared/useFinanceLabels';
import { ExpenseDetailsDrawer } from '../expenses/ExpenseDetailsDrawer';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';

type View = ApprovalStatus | 'ALL';

/** Approval inbox: expenses above the EXPENSE_CAPTURE auto-approval limit. Never your own requests. */
export function ApprovalsPage() {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const me = useMyUserId();
  const canDecide = useCanMutate(PERMISSIONS.tenantApprovalExpense);
  const canReadExpenses = useSession().hasPermission(PERMISSIONS.tenantExpenseRead);
  const [view, setView] = useState<View>('PENDING');
  const [deciding, setDeciding] = useState<ApprovalRequestDto | null>(null);
  const [expense, setExpense] = useState<ExpenseDto | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.approval, ENTITY.expense], liveReload);
  const fetchPage = useCallback<FetchPage<ApprovalRequestDto>>(
    (query, signal) => approvalService.list(query, signal),
    [],
  );
  const mine = (a: ApprovalRequestDto) => a.requested_by !== null && a.requested_by === me;
  const openExpense = (a: ApprovalRequestDto) => {
    setLoadError(null);
    expenseService.get(a.subject_id).then(setExpense, (err: unknown) => {
      setLoadError(toApiError(err));
    });
  };
  const columns: DataColumn<ApprovalRequestDto>[] = [
    { id: 'at', header: 'Requested', render: (a) => formatInstantIn(a.requested_at, timeZone) },
    {
      id: 'subject',
      header: 'Subject',
      render: (a) => (a.subject_type === 'EXPENSE' ? 'Expense' : a.subject_type),
    },
    { id: 'reason', header: 'Why approval is needed', render: (a) => a.reason },
    { id: 'policy', header: 'Policy', render: (a) => a.policy_version },
    { id: 'by', header: 'Requested by', render: (a) => <PersonName userId={a.requested_by} /> },
    {
      id: 'status',
      header: 'Status',
      render: (a) => (
        <StatusChip
          status={a.status}
          tones={APPROVAL_STATUS_TONES}
          label={labelOf(APPROVAL_STATUS_OPTIONS, a.status)}
        />
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (a) => <MoneyText amount={a.amount} currency={a.currency} />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (a) => (
        <RowActionsMenu
          label={`approval ${a.reason}`}
          actions={[
            {
              key: 'view',
              label: 'View expense',
              hidden: a.subject_type !== 'EXPENSE' || !canReadExpenses,
              onClick: () => {
                openExpense(a);
              },
            },
            {
              key: 'decide',
              label: mine(a)
                ? 'Approve / reject (not allowed: your own request)'
                : 'Approve / reject',
              hidden: !canDecide || a.status !== 'PENDING',
              disabled: mine(a),
              onClick: () => {
                setDeciding(a);
              },
            },
          ]}
        />
      ),
    },
  ];
  let dialog: ReactNode = null;
  if (deciding !== null) {
    const a = deciding;
    dialog = (
      <DecisionDialog<ApprovalRequestDto>
        title="Decide expense approval"
        kind="approve"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Amount',
                value: <MoneyText amount={a.amount} currency={a.currency} strong />,
              },
              { label: 'Policy version', value: a.policy_version },
              { label: 'Reason', value: a.reason },
              { label: 'Requested', value: formatInstantIn(a.requested_at, timeZone) },
            ]}
          />
        }
        explanation="Approved expenses count as spending (and, if paid from cash custody, reduce the custodian's outstanding cash). Rejected expenses never count. The submitter cannot decide their own request."
        onDecide={(approve, note, key) => approvalService.decide(a.id, { approve, note }, key)}
        onDone={(r) => {
          notify.success(r.status === 'APPROVED' ? 'Expense approved.' : 'Expense rejected.');
          setReloadKey((k) => k + 1);
        }}
        onClose={() => {
          setDeciding(null);
        }}
      />
    );
  }
  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="Expenses above the EXPENSE_CAPTURE auto-approval limit wait here for someone other than the submitter"
      />
      <Box className="flex flex-col gap-3">
        <ToggleButtonGroup
          exclusive
          size="small"
          value={view}
          aria-label="Approval status"
          onChange={(_e, v: View | null) => {
            if (v !== null) setView(v);
          }}
        >
          <ToggleButton value="PENDING">Pending</ToggleButton>
          <ToggleButton value="APPROVED">Approved</ToggleButton>
          <ToggleButton value="REJECTED">Rejected</ToggleButton>
          <ToggleButton value="ALL">All</ToggleButton>
        </ToggleButtonGroup>
        {canDecide && (
          <Alert severity="info">
            Requests you submitted yourself cannot be approved by you (segregation of duties).
          </Alert>
        )}
        {loadError !== null && <ErrorState error={loadError} title="Could not load the expense" />}
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(a) => a.id}
          searchable={false}
          reloadKey={reloadKey}
          filters={{ status: view === 'ALL' ? undefined : view }}
          emptyTitle="No approval requests"
          isRowMuted={(a) => a.status === 'REJECTED'}
        />
      </Box>
      {expense !== null && (
        <ExpenseDetailsDrawer
          expense={expense}
          timeZone={timeZone}
          onClose={() => {
            setExpense(null);
          }}
        />
      )}
      {dialog}
    </>
  );
}
