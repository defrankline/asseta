import { Alert, Box, Link, TextField } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { insightsService } from '../../../api/services/insightsService';
import type {
  MachineDto,
  ManualOverrideItemDto,
  ManualOverrideSummaryDto,
  Page,
  PersonDto,
} from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { exceptionsPath, jobDetailPath } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { isIsoDate } from '../../../utils/dates';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { personLabel, searchPeople } from '../cases/caseDisplay';
import { MachinePicker } from '../shared/MachinePicker';
import { PersonName } from '../shared/PersonName';
import { formatNumber, localDayEndExclusive, localDayStart } from './insightsDisplay';

function SummaryGrid({ summary }: { summary: ManualOverrideSummaryDto }) {
  return (
    <KeyValueGrid
      columns={4}
      items={[
        { label: 'Captures with an OCR value entered by hand', value: String(summary.total) },
        { label: 'OCR value corrected', value: String(summary.manual_corrections) },
        {
          label: 'Manual mode although OCR read a value',
          value: String(summary.manual_mode_with_ocr),
        },
        { label: 'Entered value differs from OCR', value: String(summary.value_differs) },
        { label: 'Related exceptions not yet reviewed', value: String(summary.exceptions_open) },
      ]}
    />
  );
}

/**
 * OCR manual-override audit (`tenant.meter.read`): captures where OCR read a value but the stored
 * reading was entered by a person. Period, machine and person filters run on the server.
 */
export function ManualOverridesTab({ timeZone }: { timeZone: string }) {
  const { hasPermission } = useSession();
  const canSearchPeople = hasPermission(PERMISSIONS.tenantDirectoryRead);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [person, setPerson] = useState<PersonDto | null>(null);
  const [summary, setSummary] = useState<ManualOverrideSummaryDto | null>(null);
  const fromOk = from === '' || isIsoDate(from);
  const toOk = to === '' || isIsoDate(to);
  const rangeOk = fromOk && toOk && (from === '' || to === '' || from <= to);
  const filters = useMemo(
    () => ({
      captured_from: rangeOk && from !== '' ? localDayStart(from, timeZone) : undefined,
      captured_to: rangeOk && to !== '' ? localDayEndExclusive(to, timeZone) : undefined,
      machine_id: machine?.id,
      user_id: person?.user_id,
    }),
    [from, to, rangeOk, machine, person, timeZone],
  );
  const fetchPage = useCallback(
    async (q: ServerQuery, signal: AbortSignal): Promise<Page<ManualOverrideItemDto>> => {
      const report = await insightsService.manualOverrides(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      );
      setSummary(report.summary);
      return report;
    },
    [],
  );
  const columns: DataColumn<ManualOverrideItemDto>[] = [
    { id: 'when', header: 'Captured', render: (o) => formatInstantIn(o.captured_at, timeZone) },
    { id: 'machine', header: 'Machine', render: (o) => `${o.asset_code} · ${o.machine_name}` },
    {
      id: 'job',
      header: 'Job',
      render: (o) => (
        <Link component={RouterLink} to={jobDetailPath(o.job_id)}>
          {o.job_number ?? 'Open job'}
        </Link>
      ),
    },
    { id: 'kind', header: 'Reading', render: (o) => humanize(o.kind) },
    { id: 'ocr', header: 'OCR value', align: 'right', render: (o) => o.ocr_value ?? '—' },
    { id: 'entered', header: 'Entered value', align: 'right', render: (o) => o.entered_value },
    { id: 'diff', header: 'Difference', align: 'right', render: (o) => o.difference ?? '—' },
    {
      id: 'confidence',
      header: 'OCR confidence',
      align: 'right',
      render: (o) =>
        o.ocr_confidence === null ? '—' : `${formatNumber(o.ocr_confidence * 100, 0)}%`,
    },
    {
      id: 'who',
      header: 'Entered by',
      render: (o) => o.captured_by_name ?? <PersonName userId={o.captured_by_user_id} />,
    },
    {
      id: 'review',
      header: 'Review',
      render: (o) =>
        o.exception_id === null ? (
          o.manually_corrected ? (
            'Corrected'
          ) : (
            humanize(o.capture_mode)
          )
        ) : (
          <Link component={RouterLink} to={exceptionsPath(o.job_id)}>
            {humanize(o.exception_status ?? 'exception')}
          </Link>
        ),
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      {summary !== null && <SummaryGrid summary={summary} />}
      {!rangeOk && (
        <Alert severity="error">Choose a valid period (from must not be after to).</Alert>
      )}
      <ServerDataTable<ManualOverrideItemDto>
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(o) => o.capture_id}
        filters={filters}
        searchable={false}
        emptyTitle="No manual overrides match these filters"
        toolbar={
          <>
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
            <Box className="min-w-56">
              <MachinePicker value={machine} onChange={setMachine} />
            </Box>
            {canSearchPeople && (
              <Box className="min-w-56">
                <AsyncAutocomplete<PersonDto>
                  label="Entered by"
                  value={person}
                  onChange={setPerson}
                  fetchOptions={searchPeople}
                  getOptionLabel={personLabel}
                  isOptionEqualToValue={(a, b) => a.user_id === b.user_id}
                />
              </Box>
            )}
          </>
        }
      />
    </Box>
  );
}
