import { Alert, Box, TextField, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { cashService } from '../../../../api/services/cashService';
import type { CashSupervisorSummaryDto } from '../../../../api/types';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import { MoneyText } from '../../../../components/display/MoneyText';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { formatDate, isIsoDate, todayIsoDate } from '../../../../utils/dates';
import { CURRENCY_FILTER_OPTIONS } from '../../shared/financeDisplay';
import { ENTITY } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';

const money = (amount: string, currency: string, strong = false) => (
  <MoneyText amount={amount} currency={currency} strong={strong} />
);

const COLUMNS: DataColumn<CashSupervisorSummaryDto>[] = [
  { id: 'supervisor', header: 'Supervisor', render: (s) => s.staff_name },
  { id: 'currency', header: 'Currency', render: (s) => s.currency },
  {
    id: 'outstanding',
    header: 'Outstanding accountability',
    align: 'right',
    render: (s) => money(s.closing_outstanding, s.currency, true),
  },
  {
    id: 'handovers',
    header: 'Claimed handovers (not yet verified)',
    align: 'right',
    render: (s) => money(s.claimed_unverified_handovers, s.currency),
  },
  {
    id: 'pending',
    header: 'Expenses pending approval',
    align: 'right',
    render: (s) => money(s.pending_spending, s.currency),
  },
  { id: 'asof', header: 'As of', render: (s) => formatDate(s.period_to) },
];

interface SupervisorsTabProps {
  /** Opens that supervisor's custody tab. */
  onOpenSupervisor: (row: CashSupervisorSummaryDto) => void;
}

/** Every supervisor's cash accountability at the end of one tenant-local day, one row per currency. */
export function SupervisorsTab({ onOpenSupervisor }: SupervisorsTabProps) {
  const [asOf, setAsOf] = useState(todayIsoDate);
  const [currency, setCurrency] = useState('');
  const valid = isIsoDate(asOf);
  const load = useCallback(
    (signal: AbortSignal) =>
      cashService.supervisorSummary(
        { from: asOf, to: asOf, currency: currency || undefined },
        signal,
      ),
    [asOf, currency],
  );
  const res = useAsyncResource(load, [], valid);
  useLiveRefresh([ENTITY.cashHandover, ENTITY.customerPayment, ENTITY.expense], res.reload);
  return (
    <Box className="flex flex-col gap-3">
      <Typography variant="body2" color="text.secondary">
        Outstanding = floats + collections − approved cash expenses − verified handovers, at the end
        of the chosen day. Claims do not reduce it until verified. Choose a row to open that
        supervisor’s custody.
      </Typography>
      <Box className="flex flex-wrap items-center gap-3">
        <TextField
          size="small"
          type="date"
          label="As of"
          value={asOf}
          onChange={(e) => {
            setAsOf(e.target.value);
          }}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <StaticSelectFilter
          label="Currency"
          value={currency}
          options={CURRENCY_FILTER_OPTIONS}
          allLabel="All currencies"
          onChange={setCurrency}
        />
      </Box>
      {!valid && <Alert severity="error">Choose a valid date.</Alert>}
      <AsyncContent
        resource={res}
        isEmpty={(d) => d.length === 0}
        emptyTitle="No supervisor holds company cash"
        errorTitle="Could not load the supervisor cash summary"
      >
        {(rows) => (
          <StaticTable
            ariaLabel="Cash by supervisor"
            columns={COLUMNS}
            rows={rows}
            getRowId={(s) => `${s.staff_member_id}:${s.currency}`}
            onRowClick={onOpenSupervisor}
          />
        )}
      </AsyncContent>
    </Box>
  );
}
