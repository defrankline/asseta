import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import { useCallback, useState } from 'react';
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
import { ENTITY } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { humanize } from '../../../utils/text';
import { formatInstantIn } from '../../../utils/time';
import { CAPABILITY, useCapabilityEnabled } from '../../../access/capabilities';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { useNotify } from '../../../notifications/useNotify';
import { ProposeBaselineDialog } from '../engineHours/BaselineDialogs';
import { SubmitDailyReportDialog } from '../engineHours/allocations/SubmitDailyReportDialog';
import { ProposeCorrectionDialog } from '../engineHours/ProposeCorrectionDialog';
import { CaptureCard } from '../readings/CaptureCard';
import { resultMessage } from '../readings/capturePolicy';
import { ConsoleCaptureDialog } from '../readings/ConsoleCaptureDialog';
import { useFieldMachineLabels } from './fieldLookups';

/** Server `state` filter; PROVISIONAL and REJECTED are the readings that need attention. */
const STATE_OPTIONS: readonly { value: CaptureState; label: string }[] = [
  { value: 'PROVISIONAL', label: 'Requires review (provisional)' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'ACCEPTED', label: 'Accepted' },
  { value: 'SUPERSEDED', label: 'Superseded' },
];

/** Live readings (not superseded or rejected) may be corrected through a proposal. */
const isLive = (c: MeterCaptureDto) => c.state === 'ACCEPTED' || c.state === 'PROVISIONAL';

function ReadingDialog({
  capture,
  machineLabel,
  timeZone,
  onCorrect,
  onClose,
}: {
  capture: MeterCaptureDto;
  machineLabel: string;
  timeZone: string;
  /** Present when the caller may propose a correction of this reading. */
  onCorrect?: (() => void) | undefined;
  onClose: () => void;
}) {
  const load = useCallback(
    async (signal: AbortSignal) =>
      (
        await meterService.listExceptions(
          {
            page: 1,
            page_size: 200,
            filters: { mine: 'true' },
          },
          signal,
        )
      ).items.filter((e) => e.meter_capture_id === capture.id),
    [capture.id],
  );
  const findings = useAsyncResource(load);
  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {humanize(capture.kind)} reading · {machineLabel}
      </DialogTitle>
      <DialogContent>
        <AsyncContent resource={findings} errorTitle="Could not load the reading's findings">
          {(f) => <CaptureCard capture={capture} findings={f} timeZone={timeZone} />}
        </AsyncContent>
      </DialogContent>
      <DialogActions>
        {onCorrect !== undefined && isLive(capture) && (
          <Button onClick={onCorrect}>Propose correction</Button>
        )}
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

/** The caller's meter readings with their state, evidence, findings and reviewer notes. */
export function FieldReadingsPage() {
  const timeZone = useDisplayTimeZone();
  const machineLabel = useFieldMachineLabels();
  const [state, setState] = useState('');
  const [viewing, setViewing] = useState<MeterCaptureDto | null>(null);
  const [correcting, setCorrecting] = useState<MeterCaptureDto | null>(null);
  const [recording, setRecording] = useState<'daily' | 'baseline' | 'report' | null>(null);
  const notify = useNotify();
  const canCapture = useCanMutate(PERMISSIONS.tenantMeterCapture);
  /** Off: no daily readings, baselines or corrections. */
  const engineHoursOn = useCapabilityEnabled(CAPABILITY.engineHours);
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
        subtitle="Your meter readings, how the policy judged them, and any review notes"
        actions={
          canCapture && engineHoursOn ? (
            <Box className="flex flex-wrap gap-2">
              <Button
                variant="contained"
                onClick={() => {
                  setRecording('daily');
                }}
              >
                Record daily reading
              </Button>
              <Button
                variant="outlined"
                onClick={() => {
                  setRecording('report');
                }}
              >
                Submit daily report
              </Button>
              <Button
                variant="outlined"
                onClick={() => {
                  setRecording('baseline');
                }}
              >
                Propose baseline
              </Button>
            </Box>
          ) : undefined
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(c) => c.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ state: state || undefined }}
        emptyTitle="No readings"
        emptyDescription="Daily readings and readings from the field apps appear here."
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
          </Box>
        }
      />
      {viewing !== null && (
        <ReadingDialog
          capture={viewing}
          machineLabel={machineLabel(viewing.machine_id)}
          timeZone={timeZone}
          onCorrect={
            canCapture && engineHoursOn
              ? () => {
                  setCorrecting(viewing);
                  setViewing(null);
                }
              : undefined
          }
          onClose={() => {
            setViewing(null);
          }}
        />
      )}
      {correcting !== null && (
        <ProposeCorrectionDialog
          capture={correcting}
          machineLabel={machineLabel(correcting.machine_id)}
          onClose={() => {
            setCorrecting(null);
          }}
          onProposed={(c) => {
            notify.success(
              c.status === 'APPROVED'
                ? 'Reading corrected.'
                : 'Correction proposed; a second person decides it.',
            );
            liveReload();
          }}
        />
      )}
      {recording === 'daily' && (
        <ConsoleCaptureDialog
          kind="DAILY"
          variant="field"
          onClose={() => {
            setRecording(null);
          }}
          onRecorded={(r) => {
            notify.success(resultMessage(r));
            liveReload();
          }}
        />
      )}
      {recording === 'report' && (
        <SubmitDailyReportDialog
          onClose={() => {
            setRecording(null);
          }}
          onSubmitted={() => {
            notify.success('Daily report submitted.');
          }}
        />
      )}
      {recording === 'baseline' && (
        <ProposeBaselineDialog
          onClose={() => {
            setRecording(null);
          }}
          onProposed={() => {
            notify.success('Baseline proposed; a second person decides it.');
          }}
        />
      )}
    </>
  );
}
