import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { meterService } from '../../../api/services/meterService';
import type { CaptureState, MeterCaptureDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { CaptureStateChip } from '../../../components/meter/CaptureStateChip';
import { GPS_STATUS_LABELS } from '../../../components/meter/gps';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { fieldJobPath } from '../../../navigation/routes';
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { CaptureCard } from '../jobDetail/CaptureCard';
import { useFieldJobLabels, useFieldMachineLabels } from './fieldLookups';

/** Server `state` filter; PROVISIONAL and REJECTED are the readings that need attention. */
const STATE_OPTIONS: readonly { value: CaptureState; label: string }[] = [
  { value: 'PROVISIONAL', label: 'Requires review (provisional)' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'ACCEPTED', label: 'Accepted' },
  { value: 'SUPERSEDED', label: 'Superseded' },
];

const KIND_OPTIONS = [
  { value: 'OPENING', label: 'Opening' },
  { value: 'CLOSING', label: 'Closing' },
];

function ReadingDialog({
  capture,
  jobLabel,
  timeZone,
  onClose,
}: {
  capture: MeterCaptureDto;
  jobLabel: string;
  timeZone: string;
  onClose: () => void;
}) {
  const load = useCallback(
    async (signal: AbortSignal) =>
      (
        await meterService.listExceptions(
          { page: 1, page_size: 200, filters: { job_id: capture.job_id } },
          signal,
        )
      ).items.filter((e) => e.meter_capture_id === capture.id),
    [capture.id, capture.job_id],
  );
  const findings = useAsyncResource(load);
  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {humanize(capture.kind)} reading · job {jobLabel}
      </DialogTitle>
      <DialogContent>
        <AsyncContent resource={findings} errorTitle="Could not load the reading's findings">
          {(f) => <CaptureCard capture={capture} findings={f} timeZone={timeZone} />}
        </AsyncContent>
      </DialogContent>
      <DialogActions>
        <Button component={RouterLink} to={fieldJobPath(capture.job_id)}>
          Open job
        </Button>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

/** The caller's meter readings with their state, evidence, findings and reviewer notes. */
export function FieldReadingsPage() {
  const timeZone = useDisplayTimeZone();
  const jobLabel = useFieldJobLabels();
  const machineLabel = useFieldMachineLabels();
  const [state, setState] = useState('');
  const [kind, setKind] = useState('');
  const [viewing, setViewing] = useState<MeterCaptureDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.meterCapture, ENTITY.meterException], liveReload);
  const fetchPage = useCallback<FetchPage<MeterCaptureDto>>(
    (query, signal) =>
      meterService.listAllCaptures(
        { ...query, filters: { ...query.filters, mine: 'true' } },
        signal,
      ),
    [],
  );
  const columns: DataColumn<MeterCaptureDto>[] = [
    { id: 'at', header: 'Captured', render: (c) => formatInstantIn(c.captured_at, timeZone) },
    { id: 'job', header: 'Job', render: (c) => jobLabel(c.job_id) },
    { id: 'machine', header: 'Machine', render: (c) => machineLabel(c.machine_id) },
    { id: 'kind', header: 'Reading', render: (c) => humanize(c.kind) },
    {
      id: 'value',
      header: 'Value',
      align: 'right',
      render: (c) => <span className="font-mono">{c.reading}</span>,
    },
    { id: 'ocr', header: 'OCR', render: (c) => c.ocr_value ?? '—' },
    {
      id: 'photo',
      header: 'Photo',
      render: (c) => (c.photo_attachment_id === null ? 'No' : 'Yes'),
    },
    { id: 'gps', header: 'GPS', render: (c) => GPS_STATUS_LABELS[c.gps_status] },
    { id: 'state', header: 'State', render: (c) => <CaptureStateChip state={c.state} /> },
  ];
  return (
    <>
      <PageHeader
        title="Readings"
        subtitle="Your opening and closing meter readings, how the policy judged them, and any review notes"
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(c) => c.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ state: state || undefined, kind: kind || undefined }}
        emptyTitle="No readings"
        emptyDescription="Readings recorded from My jobs (or the field apps) appear here."
        isRowMuted={(c) => c.state === 'SUPERSEDED'}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="State"
              value={state}
              options={STATE_OPTIONS}
              onChange={setState}
            />
            <StaticSelectFilter
              label="Reading"
              value={kind}
              options={KIND_OPTIONS}
              onChange={setKind}
            />
          </Box>
        }
      />
      {viewing !== null && (
        <ReadingDialog
          capture={viewing}
          jobLabel={jobLabel(viewing.job_id)}
          timeZone={timeZone}
          onClose={() => {
            setViewing(null);
          }}
        />
      )}
    </>
  );
}
