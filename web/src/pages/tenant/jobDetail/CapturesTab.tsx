import AddAPhoto from '@mui/icons-material/AddAPhoto';
import { Alert, Box, Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { meterService } from '../../../api/services/meterService';
import type { ExceptionDto, JobDto, MeterCaptureDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { NEUTRAL_REVIEW_NOTICE } from '../../../components/meter/exceptionText';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { CaptureCard } from './CaptureCard';
import { readingKindFor, resultMessage } from './capturePolicy';
import { ConsoleCaptureDialog } from './ConsoleCaptureDialog';

interface Loaded {
  captures: MeterCaptureDto[];
  findings: Map<string, ExceptionDto[]>;
}

/** Findings are the job's exceptions grouped by the capture that raised them. */
function groupByCapture(items: readonly ExceptionDto[]): Map<string, ExceptionDto[]> {
  const map = new Map<string, ExceptionDto[]>();
  for (const e of items) {
    if (e.meter_capture_id === null) continue;
    const list = map.get(e.meter_capture_id) ?? [];
    list.push(e);
    map.set(e.meter_capture_id, list);
  }
  return map;
}

interface CapturesTabProps {
  job: JobDto;
  timeZone: string;
  onChanged: () => void;
  /** false where another control records readings (the Field work job workspace). */
  allowRecord?: boolean;
}

/** Readings & evidence: every capture with GPS, tracker comparison, map and findings. */
export function CapturesTab({ job, timeZone, onChanged, allowRecord = true }: CapturesTabProps) {
  const notify = useNotify();
  const canCapture = useCanMutate(PERMISSIONS.tenantMeterCapture) && allowRecord;
  const [recording, setRecording] = useState(false);
  const kind = readingKindFor(job);
  const load = useCallback(
    async (signal: AbortSignal): Promise<Loaded> => {
      const [captures, exceptions] = await Promise.all([
        meterService.listCaptures(job.id, signal),
        meterService.listExceptions(
          { page: 1, page_size: 200, filters: { job_id: job.id } },
          signal,
        ),
      ]);
      return { captures, findings: groupByCapture(exceptions.items) };
    },
    [job.id],
  );
  const resource = useAsyncResource(load);
  return (
    <Stack spacing={2}>
      <Box className="flex flex-wrap items-center justify-between gap-2">
        <Alert severity="info" className="grow">
          {NEUTRAL_REVIEW_NOTICE}
        </Alert>
        {canCapture && kind !== null && (
          <Button
            variant="contained"
            startIcon={<AddAPhoto />}
            onClick={() => {
              setRecording(true);
            }}
          >
            Record {kind === 'OPENING' ? 'opening' : 'closing'} reading
          </Button>
        )}
      </Box>
      <AsyncContent
        resource={resource}
        isEmpty={(d) => d.captures.length === 0}
        emptyTitle="No readings yet"
        emptyDescription="Opening readings are taken once the job is approved; closing readings while it is in progress."
        errorTitle="Could not load readings"
      >
        {(d) => (
          <Stack spacing={2}>
            {d.captures.map((c) => (
              <CaptureCard
                key={c.id}
                capture={c}
                findings={d.findings.get(c.id) ?? []}
                timeZone={timeZone}
              />
            ))}
          </Stack>
        )}
      </AsyncContent>
      {recording && kind !== null && (
        <ConsoleCaptureDialog
          job={job}
          kind={kind}
          onClose={() => {
            setRecording(false);
          }}
          onRecorded={(r) => {
            if (r.findings.length > 0) notify.info(resultMessage(r));
            else notify.success(resultMessage(r));
            resource.reload();
            onChanged();
          }}
        />
      )}
    </Stack>
  );
}
