import Add from '@mui/icons-material/Add';
import { Box, Button, Chip, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { CanMutate } from '../../../../access/CanMutate';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import type { DailyReportDto } from '../../../../api/allocationTypes';
import { allocationService } from '../../../../api/services/allocationService';
import type { MachineDto } from '../../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { PageHeader } from '../../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { recordPath } from '../../../../navigation/recordRoutes';
import { initialFilter } from '../../../../navigation/urlFilters';
import { useNotify } from '../../../../notifications/useNotify';
import { formatDate } from '../../../../utils/dates';
import { MachineFilter } from '../../shared/financePickers';
import { machineText } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import { isNonZero, REPORT_STATUS_OPTIONS } from './allocationDisplay';
import { ReportChips } from './dailyReportKit';
import { SubmitDailyReportDialog } from './SubmitDailyReportDialog';

const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);

/** Each machine's daily operational reports: hours, billable and unbillable, and their review. */
export function DailyReportsPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [params] = useSearchParams();
  const [status, setStatus] = useState(() =>
    initialFilter(params, 'status', REPORT_STATUS_OPTIONS, ''),
  );
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<DailyReportDto>>(
    (query, signal) => allocationService.listReports(query, signal),
    [],
  );
  const columns: DataColumn<DailyReportDto>[] = [
    { id: 'day', header: 'Report date', render: (r) => formatDate(r.report_date) },
    {
      id: 'machine',
      header: 'Machine',
      render: (r) => machineText(r.machine_code, r.machine_name, r.machine_id),
    },
    {
      id: 'readings',
      header: 'Opening → closing',
      render: (r) => (
        <span className="font-mono">
          {r.opening_reading} → {r.closing_reading}
        </span>
      ),
    },
    {
      id: 'total',
      header: 'Total',
      align: 'right',
      render: (r) => <span className="font-mono">{r.total_hours}</span>,
    },
    {
      id: 'billable',
      header: 'Billable',
      align: 'right',
      render: (r) => <span className="font-mono">{r.billable_hours}</span>,
    },
    {
      id: 'unbillable',
      header: 'Unbillable',
      align: 'right',
      render: (r) => <span className="font-mono">{r.unbillable_hours}</span>,
    },
    {
      id: 'difference',
      header: 'Difference',
      align: 'right',
      render: (r) =>
        isNonZero(r.difference_hours) ? (
          <Chip size="small" color="error" label={`${r.difference_hours} h`} />
        ) : (
          '—'
        ),
    },
    {
      id: 'by',
      header: 'Submitted by',
      render: (r) => <PersonName userId={r.submitted_by} name={r.submitted_by_name} />,
    },
    { id: 'status', header: 'Status', render: (r) => <ReportChips report={r} /> },
  ];
  return (
    <>
      <PageHeader
        title="Daily reports"
        subtitle="One report per machine and day: readings, billable and unbillable hours, evidence"
        actions={
          <CanMutate permission={PERMISSIONS.tenantMeterCapture}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New daily report
            </Button>
          </CanMutate>
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        searchPlaceholder="Search machine code or name"
        reloadKey={reloadKey}
        filters={{
          status: status || undefined,
          machine_id: machine?.id,
          from: isDay(from) ? from : undefined,
          to: isDay(to) ? to : undefined,
        }}
        emptyTitle="No daily reports"
        isRowMuted={(r) => r.status === 'SUPERSEDED'}
        onRowClick={(r) => {
          void navigate(recordPath('DAILY_REPORT', r.id));
        }}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={REPORT_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
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
      {creating && (
        <SubmitDailyReportDialog
          onClose={() => {
            setCreating(false);
          }}
          onSubmitted={() => {
            notify.success('Daily report submitted.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
