import Download from '@mui/icons-material/Download';
import { Box, Button, Chip, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router';
import type { AdjustmentEntryDto } from '../../../../api/adjustmentTypes';
import { adjustmentService } from '../../../../api/services/adjustmentService';
import type { CustomerDto, MachineDto, StaffDto } from '../../../../api/types';
import { saveBlob } from '../../../../components/data/exportFile';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { StatusChip } from '../../../../components/display/StatusChip';
import { PageHeader } from '../../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { ADJUSTMENT_ROUTES, adjustmentEntryPath } from '../../../../navigation/adjustmentRoutes';
import { initialFilter } from '../../../../navigation/urlFilters';
import { useNotify } from '../../../../notifications/useNotify';
import { isIsoDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import { CustomerFilter, MachineFilter, StaffFilter } from '../../shared/financePickers';
import { machineText } from '../../shared/names';
import {
  ADJUSTMENT_TYPE_LABELS,
  ADJUSTMENT_TYPE_OPTIONS,
  ENTRY_STATUS_LABELS,
  ENTRY_STATUS_OPTIONS,
  ENTRY_STATUS_TONES,
  unitValue,
} from './adjustmentDisplay';

const forWhom = (e: AdjustmentEntryDto): string =>
  e.customer_name ??
  e.staff_member_name ??
  (e.machine_id === null ? '—' : machineText(e.machine_code, e.machine_name, e.machine_id));

/** Finance → Adjustments ledger: every decided change to money, hours and readings. */
export function AdjustmentsLedgerPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const [params] = useSearchParams();
  const originalId = params.get('original_id') ?? undefined;
  const [type, setType] = useState(() =>
    initialFilter(params, 'type', ADJUSTMENT_TYPE_OPTIONS, ''),
  );
  const [status, setStatus] = useState(() =>
    initialFilter(params, 'status', ENTRY_STATUS_OPTIONS, ''),
  );
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [q, setQ] = useState('');
  const [exporting, setExporting] = useState(false);
  const fetchPage = useCallback<FetchPage<AdjustmentEntryDto>>(
    (query, signal) => adjustmentService.listEntries(query, signal),
    [],
  );
  const filters = {
    type: type === '' ? undefined : type,
    status: status === '' ? undefined : status,
    customer_id: customer?.id,
    machine_id: machine?.id,
    staff_member_id: staff?.id,
    date_from: isIsoDate(from) ? from : undefined,
    date_to: isIsoDate(to) ? to : undefined,
    original_id: originalId,
  };
  const exportCsv = async () => {
    setExporting(true);
    try {
      const chosen = Object.entries({ ...filters, q: q === '' ? undefined : q }).filter(
        (kv): kv is [string, string] => kv[1] !== undefined,
      );
      const file = await adjustmentService.exportCsv(Object.fromEntries(chosen));
      saveBlob(file.blob, file.filename);
    } catch (err) {
      notify.error(err, 'Could not export the ledger.');
    } finally {
      setExporting(false);
    }
  };
  const value = (e: AdjustmentEntryDto, v: string | null) => (
    <span className="font-mono">{unitValue(v, e.unit, e.currency)}</span>
  );
  const columns: DataColumn<AdjustmentEntryDto>[] = [
    { id: 'at', header: 'Posted', render: (e) => formatInstantIn(e.posted_at, timeZone) },
    {
      id: 'type',
      header: 'Type',
      render: (e) => (
        <Chip size="small" variant="outlined" label={ADJUSTMENT_TYPE_LABELS[e.adjustment_type]} />
      ),
    },
    { id: 'ref', header: 'Original record', render: (e) => e.original_reference ?? '—' },
    { id: 'for', header: 'For', render: forWhom },
    { id: 'old', header: 'Original', align: 'right', render: (e) => value(e, e.original_value) },
    { id: 'new', header: 'New', align: 'right', render: (e) => value(e, e.new_value) },
    {
      id: 'bal',
      header: 'Resulting balance',
      align: 'right',
      render: (e) => value(e, e.resulting_balance),
    },
    { id: 'why', header: 'Reason', render: (e) => e.reason_label ?? e.reason ?? '—' },
    {
      id: 'status',
      header: 'Status',
      render: (e) => (
        <StatusChip
          status={e.status}
          tones={ENTRY_STATUS_TONES}
          label={ENTRY_STATUS_LABELS[e.status]}
        />
      ),
    },
  ];
  const dateField = (label: string, v: string, set: (next: string) => void) => (
    <TextField
      size="small"
      type="date"
      label={label}
      value={v}
      onChange={(e) => {
        set(e.target.value);
      }}
      slotProps={{ inputLabel: { shrink: true } }}
    />
  );
  return (
    <>
      <PageHeader
        title="Adjustments ledger"
        subtitle="Every decided correction, refund, reversal and write-off. Entries are never edited."
        actions={
          <Box className="flex flex-wrap gap-2">
            <Button component={RouterLink} to={ADJUSTMENT_ROUTES.requests} variant="outlined">
              Requests
            </Button>
            <Button
              variant="outlined"
              startIcon={<Download />}
              loading={exporting}
              onClick={() => {
                void exportCsv();
              }}
            >
              Export CSV
            </Button>
          </Box>
        }
      />
      <Box className="flex flex-col gap-3">
        <Box className="flex flex-wrap gap-1" role="group" aria-label="Adjustment type">
          <Chip
            size="small"
            label="All types"
            color={type === '' ? 'primary' : 'default'}
            onClick={() => {
              setType('');
            }}
          />
          {ADJUSTMENT_TYPE_OPTIONS.map((o) => (
            <Chip
              key={o.value}
              size="small"
              label={o.label}
              color={type === o.value ? 'primary' : 'default'}
              onClick={() => {
                setType(o.value);
              }}
            />
          ))}
        </Box>
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(e) => e.id}
          filters={filters}
          searchPlaceholder="Search reference or reason"
          onSearchChange={setQ}
          emptyTitle="No adjustments"
          isRowMuted={(e) => e.status !== 'APPROVED'}
          onRowClick={(e) => {
            void navigate(adjustmentEntryPath(e.id));
          }}
          toolbar={
            <Box className="flex flex-wrap gap-3">
              <StaticSelectFilter
                label="Status"
                value={status}
                options={ENTRY_STATUS_OPTIONS}
                onChange={setStatus}
              />
              <Box sx={{ minWidth: 220 }}>
                <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <MachineFilter label="Machine" value={machine} onChange={setMachine} />
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <StaffFilter label="Custodian" value={staff} onChange={setStaff} />
              </Box>
              {dateField('From', from, setFrom)}
              {dateField('To', to, setTo)}
            </Box>
          }
        />
      </Box>
    </>
  );
}
