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
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCallback, useState } from 'react';
import { cashService } from '../../../../api/services/cashService';
import type {
  CashReconciliationDayDto,
  CashReconciliationDto,
  StaffDto,
} from '../../../../api/types';
import { ExportMenu } from '../../../../components/data/ExportMenu';
import { MoneyText } from '../../../../components/display/MoneyText';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../../components/feedback/EmptyState';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { formatDate, isIsoDate, todayIsoDate } from '../../../../utils/dates';
import { CURRENCY_FILTER_OPTIONS } from '../../shared/financeDisplay';
import { StaffFilter } from '../../shared/financePickers';
import { ENTITY } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';

/** The reconciliation identity (acceptance §10 #8), as computed by the server per tenant-local day. */
export const RECONCILIATION_FORMULA =
  'Opening + floats + collections − approved cash expenses − verified handovers = outstanding';

function FormulaCard({ day: d, currency }: { day: CashReconciliationDayDto; currency: string }) {
  const m = (v: string, strong = false) => (
    <MoneyText amount={v} currency={currency} strong={strong} />
  );
  const lines: [string, string, string][] = [
    ['', 'Opening cash', d.opening],
    ['+', 'Floats issued', d.floats_issued],
    ['+', 'Cash collections', d.collections],
    ['−', 'Approved cash expenses', d.approved_spending],
    ['−', 'Verified handovers', d.verified_handovers],
  ];
  return (
    <Paper
      variant="outlined"
      className="p-4"
      component="section"
      aria-label={`Reconciliation ${d.day}`}
    >
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
        {formatDate(d.day)} — closing accountability
      </Typography>
      <Box className="flex flex-wrap gap-8">
        <Table
          size="small"
          sx={{ width: 'auto', minWidth: 340 }}
          aria-label="Outstanding calculation"
        >
          <TableBody>
            {lines.map(([sign, label, value]) => (
              <TableRow key={label}>
                <TableCell sx={{ width: 24 }}>{sign}</TableCell>
                <TableCell>{label}</TableCell>
                <TableCell align="right">{m(value)}</TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell>=</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Outstanding</TableCell>
              <TableCell align="right" data-testid="outstanding">
                {m(d.outstanding, true)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <Table size="small" sx={{ width: 'auto', minWidth: 340 }} aria-label="Not yet verified">
          <TableBody>
            <TableRow>
              <TableCell colSpan={2}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Claims not yet counted (shown separately)
                </Typography>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Claimed handovers awaiting verification</TableCell>
              <TableCell align="right">{m(d.claimed_unverified_handovers)}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Cash expenses pending approval</TableCell>
              <TableCell align="right">{m(d.pending_spending)}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Collections not yet verified (included above)</TableCell>
              <TableCell align="right">{m(d.unverified_collections)}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>
                Outstanding if claimed handovers are verified
              </TableCell>
              <TableCell align="right" data-testid="outstanding-if-verified">
                {m(d.outstanding_if_claims_verified, true)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Box>
    </Paper>
  );
}

const HEADERS = [
  'Day',
  'Opening',
  '+ Floats',
  '+ Collections',
  '− Approved expenses',
  '− Verified handovers',
  '= Outstanding',
  'Claimed handovers',
  'Pending expenses',
  'Unverified collections',
  'Outstanding if claims verified',
] as const;

function DaysTable({ data }: { data: CashReconciliationDto }) {
  const c = data.currency;
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small" aria-label="Daily reconciliation">
        <TableHead>
          <TableRow>
            {HEADERS.map((h, i) => (
              <TableCell key={h} align={i === 0 ? 'left' : 'right'}>
                {h}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {data.days.map((d) => (
            <TableRow key={d.day}>
              <TableCell>{formatDate(d.day)}</TableCell>
              {[
                d.opening,
                d.floats_issued,
                d.collections,
                d.approved_spending,
                d.verified_handovers,
                d.outstanding,
                d.claimed_unverified_handovers,
                d.pending_spending,
                d.unverified_collections,
                d.outstanding_if_claims_verified,
              ].map((v, i) => (
                <TableCell key={HEADERS[i + 1]} align="right">
                  <MoneyText amount={v} currency={c} strong={i === 5} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

interface ReconciliationTabProps {
  supervisor: StaffDto | null;
  onSupervisorChange: (s: StaffDto | null) => void;
}

/** Daily cash reconciliation per supervisor and currency; every figure comes from the API. */
export function ReconciliationTab({ supervisor, onSupervisorChange }: ReconciliationTabProps) {
  const [from, setFrom] = useState(() => dayjs().subtract(6, 'day').format('YYYY-MM-DD'));
  const [to, setTo] = useState(todayIsoDate);
  const [currency, setCurrency] = useState('');
  const staffId = supervisor?.id ?? '';
  const valid = isIsoDate(from) && isIsoDate(to) && from <= to;
  const load = useCallback(
    (signal: AbortSignal) =>
      cashService.reconciliation(
        { staffMemberId: staffId, from, to, currency: currency || undefined },
        signal,
      ),
    [staffId, from, to, currency],
  );
  const res = useAsyncResource(load, [], staffId !== '' && valid);
  useLiveRefresh([ENTITY.cashHandover, ENTITY.customerPayment, ENTITY.expense], res.reload);
  return (
    <Box className="flex flex-col gap-3">
      <Alert severity="info">
        <strong>{RECONCILIATION_FORMULA}.</strong> Claimed (unverified) handovers and expenses
        pending approval never reduce accountability until verified / approved; they are listed
        separately.
      </Alert>
      <Box className="flex flex-wrap items-center gap-3">
        <Box sx={{ minWidth: 260 }}>
          <StaffFilter
            label="Supervisor"
            placeholder="Choose a supervisor"
            supervisorsOnly
            value={supervisor}
            onChange={onSupervisorChange}
          />
        </Box>
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
        <StaticSelectFilter
          label="Currency"
          value={currency}
          options={CURRENCY_FILTER_OPTIONS}
          allLabel="Tenant base currency"
          onChange={setCurrency}
        />
        <Box className="flex-1" />
        <ExportMenu
          reports={[
            {
              code: 'cash',
              filters: valid ? { from, to, currency, staff_member_id: supervisor?.id } : {},
            },
          ]}
        />
      </Box>
      {!valid && <Alert severity="error">Choose a valid period (from must not be after to).</Alert>}
      {supervisor === null ? (
        <EmptyState title="Choose a supervisor" description="Reconciliation is per supervisor." />
      ) : (
        <AsyncContent resource={res} errorTitle="Could not load the reconciliation">
          {(data) => {
            const last = data.days[data.days.length - 1];
            return (
              <Box className="flex flex-col gap-3">
                <Typography variant="body2" color="text.secondary">
                  {data.currency} · days in the tenant’s time zone ({data.timezone})
                </Typography>
                {last !== undefined && <FormulaCard day={last} currency={data.currency} />}
                <DaysTable data={data} />
              </Box>
            );
          }}
        </AsyncContent>
      )}
    </Box>
  );
}
