import { Alert, Chip, MenuItem, Stack, TextField } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useSearchParams, useParams } from 'react-router';
import { meterService } from '../../../api/services/meterService';
import type { ExceptionDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import {
  EXCEPTION_TYPE_LABELS,
  explainException,
  NEUTRAL_REVIEW_NOTICE,
} from '../../../components/meter/exceptionText';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { useMachineLabels } from '../shared/useMachineLabels';
import {
  EXCEPTION_STATUS_LABELS,
  EXCEPTION_STATUS_OPTIONS,
  EXCEPTION_STATUS_TONES,
  EXCEPTION_TYPE_OPTIONS,
} from './exceptionDisplay';
import { ExceptionDetailDialog } from './ExceptionDetailDialog';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { initialFilter } from '../../../navigation/urlFilters';
import { useFocusedRecord } from '../shared/useFocusedRecord';
import { FocusMissingAlert } from '../shared/FocusMissingAlert';

/** Meter/GPS exceptions awaiting or after human review; filtered by status and type. */
export function ExceptionsPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const machineName = useMachineLabels();
  const [params] = useSearchParams();
  const { focusId } = useParams();
  const [status, setStatus] = useState(() =>
    focusId !== undefined ? '' : initialFilter(params, 'status', EXCEPTION_STATUS_OPTIONS, 'OPEN'),
  );
  const [type, setType] = useState(() =>
    initialFilter(params, 'exception_type', EXCEPTION_TYPE_OPTIONS, ''),
  );
  const [selected, setSelected] = useState<ExceptionDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.meterException, ENTITY.meterCapture], liveReload);
  const filters = useMemo(
    () => ({
      status: status || undefined,
      exception_type: type || undefined,
    }),
    [status, type],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      meterService.listExceptions(
        { page: q.page, page_size: q.page_size, filters: q.filters },
        signal,
      ),
    [],
  );
  const loadFocused = useCallback(
    (id: string, signal: AbortSignal) => meterService.getException(id, signal),
    [],
  );
  const focus = useFocusedRecord<ExceptionDto>(loadFocused, focusId, setSelected);
  const columns: DataColumn<ExceptionDto>[] = [
    { id: 'created', header: 'Recorded', render: (e) => formatInstantIn(e.created_at, timeZone) },
    { id: 'type', header: 'Type', render: (e) => EXCEPTION_TYPE_LABELS[e.exception_type] },
    {
      id: 'status',
      header: 'Status',
      render: (e) => (
        <StatusChip
          status={e.status}
          tones={EXCEPTION_STATUS_TONES}
          label={EXCEPTION_STATUS_LABELS[e.status]}
        />
      ),
    },
    { id: 'machine', header: 'Machine', render: (e) => machineName(e.machine_id) },
    {
      id: 'explanation',
      header: 'What was recorded',
      render: (e) => explainException(e.exception_type, e.evidence),
    },
    {
      id: 'blocking',
      header: 'Billing',
      render: (e) =>
        e.blocking ? <Chip size="small" variant="outlined" label="Blocks billing" /> : '—',
    },
  ];
  return (
    <>
      <PageHeader
        title="Exceptions"
        subtitle="Meter and GPS evidence that requires review before billing"
      />
      <FocusMissingAlert missing={focus.missing} />
      <Stack spacing={2}>
        <Alert severity="info">{NEUTRAL_REVIEW_NOTICE}</Alert>
        <ServerDataTable<ExceptionDto>
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(e) => e.id}
          filters={filters}
          searchable={false}
          emptyTitle="No exceptions match these filters"
          reloadKey={reloadKey}
          onRowClick={setSelected}
          toolbar={
            <>
              <TextField
                select
                size="small"
                label="Status"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                }}
                sx={{ minWidth: 220 }}
              >
                <MenuItem value="">All statuses</MenuItem>
                {EXCEPTION_STATUS_OPTIONS.map((o) => (
                  <MenuItem key={o.value} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="Type"
                value={type}
                onChange={(e) => {
                  setType(e.target.value);
                }}
                sx={{ minWidth: 240 }}
              >
                <MenuItem value="">All types</MenuItem>
                {EXCEPTION_TYPE_OPTIONS.map((o) => (
                  <MenuItem key={o.value} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </TextField>
            </>
          }
        />
      </Stack>
      {selected !== null && (
        <ExceptionDetailDialog
          exception={selected}
          machineName={machineName(selected.machine_id)}
          timeZone={timeZone}
          onClose={() => {
            setSelected(null);
          }}
          onReviewed={() => {
            notify.success('Review recorded.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
