import Add from '@mui/icons-material/Add';
import { Button, Chip, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { CanMutate } from '../../../access/CanMutate';
import { expenseService } from '../../../api/services/expenseService';
import type { ExpenseDto, ExpenseStatus, Page } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { formatInstantIn } from '../../../utils/time';
import { ExpenseDetailsDrawer } from '../expenses/ExpenseDetailsDrawer';
import { RecordExpenseDialog } from '../expenses/RecordExpenseDialog';
import { PAID_FROM_LABELS } from '../shared/financeDisplay';
import { useExpenseCategoryLabels } from '../shared/useFinanceLabels';
import { useFieldJobLabels } from './fieldLookups';

/** Status groups in the order a supervisor follows up; each shows its latest entries. */
const GROUPS: readonly { status: ExpenseStatus; title: string; empty: string }[] = [
  { status: 'PENDING_APPROVAL', title: 'Waiting for approval', empty: 'Nothing is waiting.' },
  { status: 'REJECTED', title: 'Rejected', empty: 'No rejected expenses.' },
  { status: 'APPROVED', title: 'Approved', empty: 'No approved expenses yet.' },
];
const GROUP_PAGE_SIZE = 25;

/** The caller's expenses grouped by approval status, with the office's decision notes. */
export function FieldExpensesPage() {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const categoryLabel = useExpenseCategoryLabels();
  const jobLabel = useFieldJobLabels();
  const [viewing, setViewing] = useState<ExpenseDto | null>(null);
  const [recording, setRecording] = useState(false);
  const load = useCallback(
    (signal: AbortSignal): Promise<Page<ExpenseDto>[]> =>
      Promise.all(
        GROUPS.map((g) =>
          expenseService.list(
            {
              page: 1,
              page_size: GROUP_PAGE_SIZE,
              filters: { status: g.status, mine: 'true' },
            },
            signal,
          ),
        ),
      ),
    [],
  );
  const resource = useAsyncResource(load);
  useLiveRefresh([ENTITY.expense, ENTITY.approval], resource.reload);
  const columns: DataColumn<ExpenseDto>[] = [
    { id: 'at', header: 'Incurred', render: (e) => formatInstantIn(e.incurred_at, timeZone) },
    { id: 'desc', header: 'Description', render: (e) => e.description },
    { id: 'cat', header: 'Category', render: (e) => categoryLabel(e.category_id) },
    { id: 'job', header: 'Job', render: (e) => (e.job_id === null ? '—' : jobLabel(e.job_id)) },
    { id: 'paid', header: 'Paid from', render: (e) => PAID_FROM_LABELS[e.paid_from] },
    { id: 'note', header: 'Office note', render: (e) => e.decision_note ?? '—' },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (e) => <MoneyText amount={e.amount} currency={e.currency} />,
    },
  ];
  return (
    <>
      <PageHeader
        title="Expenses"
        subtitle="Expenses you submitted, their approval status and the office's notes"
        actions={
          <CanMutate permission={PERMISSIONS.tenantExpenseWrite}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setRecording(true);
              }}
            >
              Submit expense
            </Button>
          </CanMutate>
        }
      />
      <AsyncContent
        resource={resource}
        errorTitle="Could not load your expenses"
        loadingLabel="Loading expenses"
      >
        {(pages) => (
          <Stack spacing={3}>
            {GROUPS.map((g, i) => {
              const page = pages[i];
              const rows = page?.items ?? [];
              const total = page?.total ?? 0;
              return (
                <Paper
                  key={g.status}
                  variant="outlined"
                  className="p-3"
                  component="section"
                  aria-label={g.title}
                >
                  <Stack direction="row" spacing={1} className="mb-2 items-center">
                    <Typography variant="h6" component="h2">
                      {g.title}
                    </Typography>
                    <Chip size="small" label={String(total)} />
                  </Stack>
                  {rows.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      {g.empty}
                    </Typography>
                  ) : (
                    <StaticTable
                      ariaLabel={g.title}
                      columns={columns}
                      rows={rows}
                      getRowId={(e) => e.id}
                      onRowClick={setViewing}
                    />
                  )}
                  {total > rows.length && (
                    <Typography variant="caption" color="text.secondary">
                      Showing the latest {String(rows.length)} of {String(total)}.
                    </Typography>
                  )}
                </Paper>
              );
            })}
          </Stack>
        )}
      </AsyncContent>
      {viewing !== null && (
        <ExpenseDetailsDrawer
          expense={viewing}
          timeZone={timeZone}
          onClose={() => {
            setViewing(null);
          }}
        />
      )}
      {recording && (
        <RecordExpenseDialog
          variant="field"
          timeZone={timeZone}
          onClose={() => {
            setRecording(false);
          }}
          onRecorded={(e) => {
            notify.success(
              e.status === 'APPROVED'
                ? 'Expense recorded and auto-approved under the policy limit.'
                : 'Expense recorded; it is waiting for approval.',
            );
            resource.reload();
          }}
        />
      )}
    </>
  );
}
