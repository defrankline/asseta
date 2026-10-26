import FileDownloadOutlined from '@mui/icons-material/FileDownloadOutlined';
import { Alert, Box, Button, TextField, Tooltip, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { revenueService } from '../../../api/services/revenueService';
import type { DailyMachineSheetRowDto, JobSiteDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { saveBlob } from '../../../components/data/exportFile';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { dailySheetDayPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate } from '../../../utils/dates';
import { MachineFilter } from '../shared/financePickers';
import { JobSiteFilter } from '../shared/lookupPickers';
import { withErrorCode } from '../../../api/lifecycle';
import { hoursByTypeText, REVENUE_ERROR_HINTS } from './revenueDisplay';
import { differenceMachine } from './revenueDisplay';
import { JobLinks, MoneyLines, RowFlags } from './sheetParts';

const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);
const MAX_DAYS = 93;

const daysBetween = (a: string, b: string) => (Date.parse(b) - Date.parse(a)) / 86_400_000 + 1;

const hours = (h: string) => <span className="font-mono">{h}</span>;

/** Hours with a muted second line (e.g. what is still pending). */
function HoursWithNote({ value, note }: { value: string; note: string | null }) {
  return (
    <span>
      {hours(value)}
      {note !== null && (
        <Typography variant="caption" color="text.secondary" component="div">
          {note}
        </Typography>
      )}
    </span>
  );
}

const nonZero = (v: string) => Number(v) !== 0;

const columns: DataColumn<DailyMachineSheetRowDto>[] = [
  { id: 'day', header: 'Day', render: (r) => formatDate(r.day) },
  { id: 'machine', header: 'Machine', render: differenceMachine },
  {
    id: 'readings',
    header: 'Readings',
    render: (r) =>
      r.reading_count === 0 ? (
        '—'
      ) : (
        <HoursWithNote
          value={`${r.first_reading ?? '—'} → ${r.last_reading ?? '—'}`}
          note={`${String(r.reading_count)} reading${r.reading_count === 1 ? '' : 's'}`}
        />
      ),
  },
  { id: 'engine', header: 'Engine h', align: 'right', render: (r) => hours(r.engine_hours) },
  {
    id: 'customer',
    header: 'Customer work h',
    align: 'right',
    render: (r) => hours(r.customer_work_hours),
  },
  {
    id: 'nonrevenue',
    header: 'Non-revenue h',
    align: 'right',
    render: (r) => (
      <HoursWithNote
        value={r.non_revenue_hours}
        note={
          [
            nonZero(r.non_revenue_hours) ? hoursByTypeText(r.non_revenue_by_type) : null,
            nonZero(r.non_revenue_pending_hours)
              ? `${r.non_revenue_pending_hours} h awaiting approval`
              : null,
          ]
            .filter((x): x is string => x !== null)
            .join(' · ') || null
        }
      />
    ),
  },
  { id: 'revenue', header: 'Revenue h', align: 'right', render: (r) => hours(r.revenue_hours) },
  {
    id: 'noncustomer',
    header: 'Non-customer h',
    align: 'right',
    render: (r) => hours(r.approved_non_customer_hours),
  },
  {
    id: 'unexplained',
    header: 'Unexplained h',
    align: 'right',
    render: (r) => (
      <HoursWithNote
        value={r.unexplained_hours}
        note={
          [
            nonZero(r.identified_variance_hours)
              ? `${r.identified_variance_hours} h variance`
              : null,
            nonZero(r.pending_review_hours) ? `${r.pending_review_hours} h under review` : null,
          ]
            .filter((x): x is string => x !== null)
            .join(' · ') || null
        }
      />
    ),
  },
  { id: 'jobs', header: 'Jobs', render: (r) => <JobLinks jobs={r.jobs} /> },
  {
    id: 'fuel',
    header: 'Fuel L',
    align: 'right',
    render: (r) => (
      <HoursWithNote
        value={r.fuel_litres}
        note={
          r.fuel_litres_per_engine_hour == null
            ? null
            : `${r.fuel_litres_per_engine_hour} L per engine h`
        }
      />
    ),
  },
  { id: 'money', header: 'Money', render: (r) => <MoneyLines money={r.money} /> },
  {
    id: 'flags',
    header: 'Flags',
    render: (r) => <RowFlags flags={r.flags} machineId={r.machine_id} day={r.day} />,
  },
];

/**
 * One row per machine per day: engine hours split into customer work, non-revenue time and
 * unexplained hours, with jobs, fuel, the money they turned into and flags. Derived from the
 * existing ledgers on every load.
 */
export function DailySheetPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [q, setQ] = useState('');
  const [exporting, setExporting] = useState(false);
  const fetchPage = useCallback<FetchPage<DailyMachineSheetRowDto>>(
    (query, signal) => revenueService.listSheet(query, signal),
    [],
  );
  const badOrder = isDay(from) && isDay(to) && from > to;
  const tooLong = isDay(from) && isDay(to) && !badOrder && daysBetween(from, to) > MAX_DAYS;
  const rangeOk = !badOrder && !tooLong;
  const filters = {
    machine_id: machine?.id,
    site_id: site?.id,
    day_from: isDay(from) && rangeOk ? from : undefined,
    day_to: isDay(to) && rangeOk ? to : undefined,
  };
  const exportCsv = async () => {
    setExporting(true);
    try {
      const params: Record<string, string> = {};
      for (const [k, v] of Object.entries({ ...filters, q })) if (v) params[k] = v;
      const file = await revenueService.exportSheetCsv(params);
      saveBlob(file.blob, file.filename);
    } catch (err) {
      notify.error(withErrorCode(err, REVENUE_ERROR_HINTS));
    } finally {
      setExporting(false);
    }
  };
  return (
    <>
      <PageHeader
        title="Daily machine sheet"
        subtitle="Each machine's day: engine hours, customer work, non-revenue time, fuel, money and flags"
        actions={
          <Tooltip title="Download the sheet with the current filters">
            <span>
              <Button
                variant="outlined"
                startIcon={<FileDownloadOutlined />}
                disabled={exporting || !rangeOk}
                onClick={() => {
                  void exportCsv();
                }}
              >
                Export CSV
              </Button>
            </span>
          </Tooltip>
        }
      />
      {badOrder && <Alert severity="error">The “from” day must not be after the “to” day.</Alert>}
      {tooLong && <Alert severity="error">Choose at most {String(MAX_DAYS)} days at a time.</Alert>}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => `${r.machine_id}:${r.day}`}
        searchPlaceholder="Search machine code or name"
        onSearchChange={setQ}
        filters={filters}
        emptyTitle="No machine days"
        emptyDescription="No machine had readings, jobs or fuel in these days (the last 7 days unless you choose a range)."
        onRowClick={(r) => {
          void navigate(dailySheetDayPath(r.machine_id, r.day));
        }}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <Box sx={{ minWidth: 220 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
            <Box sx={{ minWidth: 220 }}>
              <JobSiteFilter label="Site" value={site} onChange={setSite} />
            </Box>
            <TextField
              size="small"
              type="date"
              label="From day"
              value={from}
              onChange={(e) => {
                setFrom(e.target.value);
              }}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              size="small"
              type="date"
              label="To day"
              value={to}
              onChange={(e) => {
                setTo(e.target.value);
              }}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Box>
        }
      />
    </>
  );
}
