import {
  Alert,
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCallback, useState } from 'react';
import { receivablesService } from '../../../api/services/financeService';
import type { CustomerBalanceDto, CustomerPaymentDto, StatementLineDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { isIsoDate, todayIsoDate } from '../../../utils/dates';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { PAYMENT_METHOD_LABELS } from '../shared/financeDisplay';

function useBalances(customerId: string) {
  const load = useCallback(
    (signal: AbortSignal) => receivablesService.balances(customerId, signal),
    [customerId],
  );
  return useAsyncResource(load);
}

function BalanceCard({ b }: { b: CustomerBalanceDto }) {
  const m = (v: string, strong = false) => (
    <MoneyText amount={v} currency={b.currency} strong={strong} />
  );
  return (
    <Paper
      variant="outlined"
      className="p-4"
      component="section"
      aria-label={`Balance in ${b.currency}`}
    >
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
        {b.currency}
      </Typography>
      <KeyValueGrid
        columns={4}
        items={[
          { label: 'Invoiced', value: m(b.invoiced) },
          { label: 'Reversed (voided invoices)', value: m(b.reversed) },
          { label: 'Verified payments', value: m(b.verified_payments) },
          { label: 'Balance due', value: m(b.balance, true) },
          { label: 'Unallocated credit (deposits / advances)', value: m(b.unallocated_credit) },
          { label: 'Open invoices', value: String(b.open_invoices) },
        ]}
      />
      <Alert severity="warning" className="mt-3">
        Claimed, not yet verified: {m(b.claimed_unverified, true)}. Claimed payments are not
        deducted from the balance until verified.
      </Alert>
    </Paper>
  );
}

/** Receivable per currency (never summed across currencies). */
export function CustomerBalanceTab({ customerId }: { customerId: string }) {
  const res = useBalances(customerId);
  return (
    <AsyncContent
      resource={res}
      isEmpty={(rows) => rows.length === 0}
      emptyTitle="No invoices or payments yet"
      errorTitle="Could not load the balance"
    >
      {(rows) => (
        <Box className="flex flex-col gap-3">
          {rows.map((b) => (
            <BalanceCard key={b.currency} b={b} />
          ))}
        </Box>
      )}
    </AsyncContent>
  );
}

function StatementView({
  customerId,
  currency,
  timeZone,
}: {
  customerId: string;
  currency: string;
  timeZone: string;
}) {
  const [from, setFrom] = useState(() => dayjs().startOf('month').format('YYYY-MM-DD'));
  const [to, setTo] = useState(todayIsoDate);
  const valid = isIsoDate(from) && isIsoDate(to) && from <= to;
  const load = useCallback(
    (signal: AbortSignal) =>
      receivablesService.statement(customerId, { from, to, currency }, signal),
    [customerId, from, to, currency],
  );
  const res = useAsyncResource(load, [], valid);
  const m = (v: string, strong = false) => (
    <MoneyText amount={v} currency={currency} strong={strong} />
  );
  const lineColumns: DataColumn<StatementLineDto>[] = [
    { id: 'at', header: 'Date', render: (l) => formatInstantIn(l.at, timeZone) },
    { id: 'kind', header: 'Type', render: (l) => humanize(l.kind) },
    { id: 'ref', header: 'Reference', render: (l) => l.reference },
    { id: 'desc', header: 'Description', render: (l) => l.description },
    { id: 'debit', header: 'Debit', align: 'right', render: (l) => m(l.debit) },
    { id: 'credit', header: 'Credit', align: 'right', render: (l) => m(l.credit) },
    { id: 'bal', header: 'Balance', align: 'right', render: (l) => m(l.running_balance) },
  ];
  const claimColumns: DataColumn<CustomerPaymentDto>[] = [
    { id: 'at', header: 'Received', render: (p) => formatInstantIn(p.received_at, timeZone) },
    { id: 'method', header: 'Method', render: (p) => PAYMENT_METHOD_LABELS[p.method] },
    { id: 'ref', header: 'Reference', render: (p) => p.reference ?? '—' },
    { id: 'amt', header: 'Amount', align: 'right', render: (p) => m(p.amount) },
  ];
  return (
    <Box className="flex flex-col gap-3">
      <Box className="flex flex-wrap gap-3">
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
      {!valid && <Alert severity="error">Choose a valid period (from must not be after to).</Alert>}
      <AsyncContent resource={res} errorTitle="Could not load the statement">
        {(s) => (
          <Box className="flex flex-col gap-3">
            <Typography variant="body2" color="text.secondary">
              {s.currency} statement, {s.period_from} to {s.period_to} (tenant-local days)
            </Typography>
            <Table
              size="small"
              sx={{ width: 'auto', minWidth: 360 }}
              aria-label="Statement summary"
            >
              <TableBody>
                <TableRow>
                  <TableCell>Opening balance</TableCell>
                  <TableCell align="right">{m(s.opening_balance, true)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Total debits (invoices)</TableCell>
                  <TableCell align="right">{m(s.total_debits)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Total credits (verified payments, reversals)</TableCell>
                  <TableCell align="right">{m(s.total_credits)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Closing balance</TableCell>
                  <TableCell align="right">{m(s.closing_balance, true)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
            {s.lines.length === 0 ? (
              <Typography variant="body2">No entries in this period.</Typography>
            ) : (
              <StaticTable
                ariaLabel="Statement lines"
                columns={lineColumns}
                rows={s.lines}
                getRowId={(l) => `${l.at}-${l.kind}-${l.reference}`}
              />
            )}
            <Paper variant="outlined" className="p-3">
              <Typography variant="subtitle2">
                Claimed payments not yet verified (not on the statement):{' '}
                {m(s.claimed_unverified_total, true)}
              </Typography>
              {s.claimed_unverified.length > 0 && (
                <StaticTable
                  ariaLabel="Claimed unverified payments"
                  columns={claimColumns}
                  rows={s.claimed_unverified}
                  getRowId={(p) => p.id}
                />
              )}
            </Paper>
          </Box>
        )}
      </AsyncContent>
    </Box>
  );
}

/** Statement per currency: pick one of the customer's currencies (they are never mixed). */
export function CustomerStatementTab({
  customerId,
  timeZone,
}: {
  customerId: string;
  timeZone: string;
}) {
  const balances = useBalances(customerId);
  const [picked, setPicked] = useState<string | null>(null);
  return (
    <AsyncContent
      resource={balances}
      isEmpty={(rows) => rows.length === 0}
      emptyTitle="No invoices or payments yet"
      errorTitle="Could not load the customer’s currencies"
    >
      {(rows) => {
        const currencies = rows.map((r) => r.currency);
        const currency =
          picked !== null && currencies.includes(picked) ? picked : (currencies[0] ?? '');
        return (
          <Box className="flex flex-col gap-3">
            <ToggleButtonGroup
              exclusive
              size="small"
              value={currency}
              aria-label="Statement currency"
              onChange={(_e, v: string | null) => {
                if (v !== null) setPicked(v);
              }}
            >
              {currencies.map((c) => (
                <ToggleButton key={c} value={c}>
                  {c}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
            <StatementView
              key={currency}
              customerId={customerId}
              currency={currency}
              timeZone={timeZone}
            />
          </Box>
        );
      }}
    </AsyncContent>
  );
}
