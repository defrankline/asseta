import Download from '@mui/icons-material/Download';
import {
  Alert,
  Box,
  Button,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCallback, useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import type {
  HoursStatementDto,
  HoursStatementLineDto,
  HoursStatementPurchaseDto,
  HoursStatementUsageDto,
} from '../../../api/hoursTypes';
import { withErrorCode } from '../../../api/lifecycle';
import { hoursStatementService } from '../../../api/services/hoursStatementService';
import type { MachineDto } from '../../../api/types';
import { saveBlob } from '../../../components/data/exportFile';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { hoursPurchasePath, lowBalanceAlertsPath } from '../../../navigation/hoursRoutes';
import { jobDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate, isIsoDate, todayIsoDate } from '../../../utils/dates';
import { isZeroDecimal } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { MachineFilter } from '../shared/financePickers';
import { machineText, nameOr } from '../shared/names';
import {
  hoursText,
  LEDGER_TYPE_LABELS,
  PROVISIONAL_LABEL,
  PURCHASE_STATUS_LABELS,
  PURCHASE_STATUS_TONES,
  STATEMENT_ERROR_HINTS,
  USAGE_BASIS_LABELS,
} from './hoursDisplay';

/** The API accepts at most 366 tenant-local days. */
const MAX_DAYS = 366;
const daysBetween = (a: string, b: string) => dayjs(b).diff(dayjs(a), 'day') + 1;

const machineOf = (r: {
  machine_id: string;
  machine_code?: string | null;
  machine_name?: string | null;
}) => machineText(r.machine_code, r.machine_name, r.machine_id);

function JobLink({ id, number }: { id: string | null; number?: string | null | undefined }) {
  if (id === null) return <>—</>;
  return (
    <Link component={RouterLink} to={jobDetailPath(id)}>
      {nameOr(number, id)}
    </Link>
  );
}

function SubSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Stack spacing={1}>
      <Typography variant="subtitle1" component="h3">
        {title}
      </Typography>
      {children}
    </Stack>
  );
}

function Totals({ s }: { s: HoursStatementDto }) {
  const t = s.totals;
  const rows: [string, string, boolean?][] = [
    ['Opening balance', t.opening_balance, true],
    ['Bought in the period', t.bought],
    ['Activated', t.activated],
    ['Transferred in', t.transferred_in],
    ['Used', t.used],
    ['Transferred out', t.transferred_out],
    ['Expired', t.expired],
    ['Cancelled', t.cancelled],
    ['Closing balance', t.closing_balance, true],
  ];
  return (
    <Stack spacing={1}>
      <Table size="small" sx={{ width: 'auto', minWidth: 360 }} aria-label="Hours statement totals">
        <TableBody>
          {rows.map(([label, value, strong]) => (
            <TableRow key={label}>
              <TableCell sx={strong === true ? { fontWeight: 700 } : undefined}>{label}</TableCell>
              <TableCell align="right" sx={strong === true ? { fontWeight: 700 } : undefined}>
                {hoursText(value)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {!isZeroDecimal(t.provisional_at_close) && (
        <Typography variant="body2" color="text.secondary">
          Of the hours used, {hoursText(t.provisional_at_close)} are{' '}
          {PROVISIONAL_LABEL.toLowerCase()} at the end of the period (final when each job
          completes).
        </Typography>
      )}
      {!isZeroDecimal(t.awaiting_activation) && (
        <Typography variant="body2" color="text.secondary">
          {hoursText(t.awaiting_activation)} bought but not yet activated (awaiting payment or
          credit).
        </Typography>
      )}
    </Stack>
  );
}

function StatementBody({ s, timeZone }: { s: HoursStatementDto; timeZone: string }) {
  const purchaseColumns: DataColumn<HoursStatementPurchaseDto>[] = [
    {
      id: 'no',
      header: 'Purchase',
      render: (p) => (
        <Link component={RouterLink} to={hoursPurchasePath(p.purchase_id)}>
          {nameOr(p.purchase_number, p.purchase_id)}
        </Link>
      ),
    },
    { id: 'machine', header: 'Machine', render: machineOf },
    { id: 'bought', header: 'Bought', render: (p) => formatInstantIn(p.bought_at, timeZone) },
    { id: 'hours', header: 'Hours', align: 'right', render: (p) => hoursText(p.hours) },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (p) => <MoneyText amount={p.amount} currency={p.currency} />,
    },
    {
      id: 'remaining',
      header: 'Remaining at close',
      align: 'right',
      render: (p) => hoursText(p.remaining_at_close),
    },
    {
      id: 'expiry',
      header: 'Next expiry',
      render: (p) =>
        p.next_expiry_at === null
          ? '—'
          : `${hoursText(p.expiring_hours)} on ${formatInstantIn(p.next_expiry_at, timeZone)}`,
    },
    {
      id: 'status',
      header: 'Status',
      render: (p) => (
        <StatusChip
          status={p.status}
          tones={PURCHASE_STATUS_TONES}
          label={PURCHASE_STATUS_LABELS[p.status]}
        />
      ),
    },
  ];
  const usageColumns: DataColumn<HoursStatementUsageDto>[] = [
    { id: 'day', header: 'Day', render: (u) => formatDate(u.day) },
    { id: 'job', header: 'Job', render: (u) => <JobLink id={u.job_id} number={u.job_number} /> },
    { id: 'machine', header: 'Machine', render: machineOf },
    { id: 'hours', header: 'Hours', align: 'right', render: (u) => hoursText(u.hours) },
    {
      id: 'basis',
      header: 'Basis',
      render: (u) =>
        u.job_running
          ? `${USAGE_BASIS_LABELS[u.basis]} · job still running`
          : USAGE_BASIS_LABELS[u.basis],
    },
  ];
  const lineColumns: DataColumn<HoursStatementLineDto>[] = [
    { id: 'at', header: 'When', render: (l) => formatInstantIn(l.occurred_at, timeZone) },
    { id: 'type', header: 'Entry', render: (l) => LEDGER_TYPE_LABELS[l.entry_type] },
    {
      id: 'purchase',
      header: 'Purchase',
      render: (l) => (
        <Link component={RouterLink} to={hoursPurchasePath(l.purchase_id)}>
          {nameOr(l.purchase_number, l.purchase_id)}
        </Link>
      ),
    },
    { id: 'machine', header: 'Machine', render: machineOf },
    { id: 'job', header: 'Job', render: (l) => <JobLink id={l.job_id} number={l.job_number} /> },
    { id: 'hours', header: 'Hours', align: 'right', render: (l) => hoursText(l.hours) },
    {
      id: 'balance',
      header: 'Balance',
      align: 'right',
      render: (l) => hoursText(l.balance_after),
    },
    { id: 'reason', header: 'Reason', render: (l) => l.reason ?? '—' },
  ];
  return (
    <Stack spacing={3}>
      <Typography variant="body2" color="text.secondary">
        {nameOr(s.customer_name, s.customer_id)}
        {s.machine_id === null
          ? ', all machines'
          : `, ${machineOf({ ...s, machine_id: s.machine_id })}`}
        {' · '}
        {formatDate(s.date_from)} to {formatDate(s.date_to)} ({s.timezone} days) · generated{' '}
        {formatInstantIn(s.generated_at, timeZone)}
      </Typography>
      <Totals s={s} />
      <SubSection title="Purchases">
        {s.purchases.length === 0 ? (
          <Typography variant="body2">No purchases for this customer and machine.</Typography>
        ) : (
          <StaticTable
            ariaLabel="Statement purchases"
            columns={purchaseColumns}
            rows={s.purchases}
            getRowId={(p) => p.purchase_id}
          />
        )}
      </SubSection>
      <SubSection title="Usage">
        {s.usage.length === 0 ? (
          <Typography variant="body2">No hours used in this period.</Typography>
        ) : (
          <StaticTable
            ariaLabel="Statement usage"
            columns={usageColumns}
            rows={s.usage}
            getRowId={(u) => `${u.day}:${u.job_id ?? ''}:${u.machine_id}:${u.basis}`}
          />
        )}
      </SubSection>
      <SubSection title="Movements">
        {s.lines.length === 0 ? (
          <Typography variant="body2">No movements in this period.</Typography>
        ) : (
          <StaticTable
            ariaLabel="Statement movements"
            columns={lineColumns}
            rows={s.lines}
            getRowId={(l) => l.entry_id}
          />
        )}
      </SubSection>
    </Stack>
  );
}

/**
 * Customer hours statement (DEC-031 P3): bought, activated, used per day and job, transferred, expired,
 * cancelled and remaining hours for a period (default this month to date), optionally one machine;
 * the same statement downloads as a PDF.
 */
export function HoursStatementPanel({
  customerId,
  timeZone,
}: {
  customerId: string;
  timeZone: string;
}) {
  const notify = useNotify();
  const [from, setFrom] = useState(() => dayjs().startOf('month').format('YYYY-MM-DD'));
  const [to, setTo] = useState(todayIsoDate);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [downloading, setDownloading] = useState(false);
  const datesOk = isIsoDate(from) && isIsoDate(to);
  const badOrder = datesOk && from > to;
  const tooLong = datesOk && !badOrder && daysBetween(from, to) > MAX_DAYS;
  const valid = datesOk && !badOrder && !tooLong;
  const machineId = machine?.id;
  const load = useCallback(
    (signal: AbortSignal) =>
      hoursStatementService.statement(
        customerId,
        { machine_id: machineId, date_from: from, date_to: to },
        signal,
      ),
    [customerId, machineId, from, to],
  );
  const res = useAsyncResource(load, [], valid);
  const download = async (pdfPath: string) => {
    setDownloading(true);
    try {
      const file = await hoursStatementService.downloadPdf(pdfPath);
      saveBlob(file.blob, file.filename);
    } catch (err) {
      notify.error(withErrorCode(err, STATEMENT_ERROR_HINTS));
    } finally {
      setDownloading(false);
    }
  };
  return (
    <Stack spacing={2}>
      <Box className="flex flex-wrap items-center gap-3">
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
        <Box sx={{ minWidth: 240 }}>
          <MachineFilter label="Machine" value={machine} onChange={setMachine} />
        </Box>
        <Box className="flex flex-1 justify-end gap-2">
          <Button
            component={RouterLink}
            to={lowBalanceAlertsPath({ customer_id: customerId })}
            size="small"
          >
            Low-balance warnings
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<Download />}
            disabled={!valid || res.data === null || downloading}
            onClick={() => {
              if (res.data !== null) void download(res.data.pdf_path);
            }}
          >
            {downloading ? 'Preparing PDF…' : 'Download PDF'}
          </Button>
        </Box>
      </Box>
      {badOrder && <Alert severity="error">{STATEMENT_ERROR_HINTS.INVALID_PERIOD}</Alert>}
      {tooLong && <Alert severity="error">{STATEMENT_ERROR_HINTS.PERIOD_TOO_LONG}</Alert>}
      {valid && (
        <AsyncContent resource={res} errorTitle="Could not load the hours statement">
          {(s) => <StatementBody s={s} timeZone={timeZone} />}
        </AsyncContent>
      )}
    </Stack>
  );
}
