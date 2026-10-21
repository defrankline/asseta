import {
  Alert,
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCallback, useState } from 'react';
import { profitabilityService } from '../../../api/services/financeService';
import type { ProfitabilityGroupBy, ProfitabilityRowDto } from '../../../api/types';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { isIsoDate, todayIsoDate } from '../../../utils/dates';
import { signOfDecimal } from '../../../utils/money';
import { groupByCurrency } from '../shared/financeDisplay';

const GROUP_LABELS: Readonly<Record<ProfitabilityGroupBy, string>> = {
  MACHINE: 'Machine',
  JOB: 'Job',
  CUSTOMER: 'Customer',
};

const COLUMNS = [
  'Revenue',
  'Reversed',
  'Net revenue',
  'Expenses',
  'Fuel',
  'Direct cost',
  'Margin',
] as const;

function CurrencyTable({
  currency,
  rows,
  groupBy,
}: {
  currency: string;
  rows: ProfitabilityRowDto[];
  groupBy: ProfitabilityGroupBy;
}) {
  const m = (v: string, strong = false) => (
    <MoneyText amount={v} currency={currency} strong={strong} />
  );
  return (
    <Paper
      variant="outlined"
      component="section"
      aria-label={`Profitability in ${currency}`}
      className="p-3"
    >
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
        {currency}
      </Typography>
      <TableContainer>
        <Table size="small" aria-label={`${currency} profitability`}>
          <TableHead>
            <TableRow>
              <TableCell>{GROUP_LABELS[groupBy]}</TableCell>
              {COLUMNS.map((c) => (
                <TableCell key={c} align="right">
                  {c}
                </TableCell>
              ))}
              <TableCell>Costs by category</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => {
              const unattributed = r.group_key === null;
              return (
                <TableRow
                  key={`${r.group_key ?? 'none'}-${r.currency}`}
                  data-unattributed={unattributed ? 'true' : undefined}
                >
                  <TableCell>
                    {unattributed ? (
                      <Typography variant="body2" sx={{ fontStyle: 'italic' }}>
                        Unattributed (no {GROUP_LABELS[groupBy].toLowerCase()})
                      </Typography>
                    ) : (
                      r.label || r.group_key
                    )}
                  </TableCell>
                  <TableCell align="right">{m(r.revenue)}</TableCell>
                  <TableCell align="right">{m(r.reversed_revenue)}</TableCell>
                  <TableCell align="right">{m(r.net_revenue)}</TableCell>
                  <TableCell align="right">{m(r.expense_cost)}</TableCell>
                  <TableCell align="right">{m(r.fuel_cost)}</TableCell>
                  <TableCell align="right">{m(r.direct_cost)}</TableCell>
                  <TableCell
                    align="right"
                    sx={{ color: signOfDecimal(r.margin) < 0 ? 'error.main' : undefined }}
                  >
                    {m(r.margin, true)}
                  </TableCell>
                  <TableCell>
                    {Object.keys(r.cost_by_category).length === 0
                      ? '—'
                      : Object.entries(r.cost_by_category).map(([code, amount]) => (
                          <Box key={code} component="div" className="whitespace-nowrap">
                            {code}: {m(amount)}
                          </Box>
                        ))}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

/** Basic profitability (recognized revenue vs categorized direct costs), per currency, never mixed. */
export function ProfitabilityPage() {
  const [groupBy, setGroupBy] = useState<ProfitabilityGroupBy>('MACHINE');
  const [from, setFrom] = useState(() => dayjs().startOf('month').format('YYYY-MM-DD'));
  const [to, setTo] = useState(todayIsoDate);
  const valid = isIsoDate(from) && isIsoDate(to) && from <= to;
  const load = useCallback(
    (signal: AbortSignal) => profitabilityService.report(groupBy, from, to, signal),
    [groupBy, from, to],
  );
  const res = useAsyncResource(load, [], valid);
  return (
    <>
      <PageHeader
        title="Profitability"
        subtitle="Recognized hire revenue (issued invoices, excluding tax; voids reverse) against approved, categorized direct costs"
      />
      <Box className="flex flex-col gap-3">
        <Box className="flex flex-wrap items-center gap-3">
          <ToggleButtonGroup
            exclusive
            size="small"
            value={groupBy}
            aria-label="Group by"
            onChange={(_e, v: ProfitabilityGroupBy | null) => {
              if (v !== null) setGroupBy(v);
            }}
          >
            <ToggleButton value="MACHINE">By machine</ToggleButton>
            <ToggleButton value="JOB">By job</ToggleButton>
            <ToggleButton value="CUSTOMER">By customer</ToggleButton>
          </ToggleButtonGroup>
          <TextField
            size="small"
            type="date"
            label="From"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
            }}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            size="small"
            type="date"
            label="To"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
            }}
            slotProps={{ inputLabel: { shrink: true } }}
          />
        </Box>
        {!valid && (
          <Alert severity="error">Choose a valid period (from must not be after to).</Alert>
        )}
        <AsyncContent
          resource={res}
          isEmpty={(d) => d.rows.length === 0}
          emptyTitle="No revenue or costs in this period"
          errorTitle="Could not load profitability"
        >
          {(d) => (
            <Box className="flex flex-col gap-3">
              <Typography variant="body2" color="text.secondary">
                {d.period_from} to {d.period_to}, tenant-local days ({d.timezone}). Pending and
                rejected expenses never count; costs without a{' '}
                {GROUP_LABELS[d.group_by].toLowerCase()} are shown as Unattributed. Each currency is
                reported separately.
              </Typography>
              {groupByCurrency(d.rows).map(([currency, rows]) => (
                <CurrencyTable
                  key={currency}
                  currency={currency}
                  rows={rows}
                  groupBy={d.group_by}
                />
              ))}
            </Box>
          )}
        </AsyncContent>
      </Box>
    </>
  );
}
