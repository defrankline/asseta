import { Stack, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { expenseService, fuelService } from '../../../api/services/expenseService';
import type { ExpenseDto, FuelEventDto, JobDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { formatInstantIn } from '../../../utils/time';
import { ExpenseDetailsDrawer } from '../expenses/ExpenseDetailsDrawer';
import { labelOf } from '../shared/display';
import {
  EXPENSE_STATUS_OPTIONS,
  EXPENSE_STATUS_TONES,
  FUEL_EVENT_OPTIONS,
} from '../shared/financeDisplay';
import { useExpenseCategoryLabels } from '../shared/useFinanceLabels';

/** At most this many of each per job (a job's field costs are a short list). */
const PAGE = 100;

interface JobCostsTabProps {
  job: JobDto;
  timeZone: string;
}

/** Expenses and fuel attributed to the job (the server limits field users to their own records). */
export function JobCostsTab({ job, timeZone }: JobCostsTabProps) {
  const categoryLabel = useExpenseCategoryLabels();
  const [viewing, setViewing] = useState<ExpenseDto | null>(null);
  const load = useCallback(
    async (signal: AbortSignal) => {
      const query = { page: 1, page_size: PAGE, filters: { job_id: job.id } };
      const [expenses, fuel] = await Promise.all([
        expenseService.list(query, signal),
        fuelService.list(query, signal),
      ]);
      return { expenses: expenses.items, fuel: fuel.items };
    },
    [job.id],
  );
  const resource = useAsyncResource(load);
  const expenseColumns: DataColumn<ExpenseDto>[] = [
    { id: 'at', header: 'Incurred', render: (e) => formatInstantIn(e.incurred_at, timeZone) },
    { id: 'desc', header: 'Description', render: (e) => e.description },
    { id: 'cat', header: 'Category', render: (e) => categoryLabel(e.category_id) },
    {
      id: 'status',
      header: 'Status',
      render: (e) => (
        <StatusChip
          status={e.status}
          tones={EXPENSE_STATUS_TONES}
          label={labelOf(EXPENSE_STATUS_OPTIONS, e.status)}
        />
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (e) => <MoneyText amount={e.amount} currency={e.currency} />,
    },
  ];
  const fuelColumns: DataColumn<FuelEventDto>[] = [
    { id: 'at', header: 'Occurred', render: (f) => formatInstantIn(f.occurred_at, timeZone) },
    { id: 'type', header: 'Type', render: (f) => labelOf(FUEL_EVENT_OPTIONS, f.event_type) },
    { id: 'litres', header: 'Litres', align: 'right', render: (f) => f.litres },
    { id: 'meter', header: 'Meter', render: (f) => f.meter_reading ?? '—' },
    {
      id: 'cost',
      header: 'Attributed cost',
      align: 'right',
      render: (f) => <MoneyText amount={f.attributed_cost} currency={f.currency} />,
    },
  ];
  return (
    <AsyncContent resource={resource} errorTitle="Could not load the job's expenses and fuel">
      {(d) => (
        <Stack spacing={3}>
          <Stack spacing={1}>
            <Typography variant="subtitle1" component="h3">
              Expenses
            </Typography>
            {d.expenses.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No expenses recorded for this job.
              </Typography>
            ) : (
              <StaticTable
                ariaLabel="Job expenses"
                columns={expenseColumns}
                rows={d.expenses}
                getRowId={(e) => e.id}
                onRowClick={setViewing}
                isRowMuted={(e) => e.status === 'REJECTED'}
              />
            )}
          </Stack>
          <Stack spacing={1}>
            <Typography variant="subtitle1" component="h3">
              Fuel
            </Typography>
            {d.fuel.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No fuel recorded for this job.
              </Typography>
            ) : (
              <StaticTable
                ariaLabel="Job fuel"
                columns={fuelColumns}
                rows={d.fuel}
                getRowId={(f) => f.id}
              />
            )}
          </Stack>
          {viewing !== null && (
            <ExpenseDetailsDrawer
              expense={viewing}
              timeZone={timeZone}
              onClose={() => {
                setViewing(null);
              }}
            />
          )}
        </Stack>
      )}
    </AsyncContent>
  );
}
