import { Link } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { meterService } from '../../../api/services/meterService';
import type { ExceptionDto, MeterCaptureDto } from '../../../api/types';
import { CaptureStateChip } from '../../../components/meter/CaptureStateChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { jobDetailPath, ROUTES } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { humanize } from '../../../utils/text';
import { CaptureCard } from '../jobDetail/CaptureCard';
import { RecordDetail } from '../shared/RecordDetail';
import { useMachineLabels } from '../shared/useMachineLabels';
import { useRecordById } from '../shared/useRecordById';

/** The findings recorded against one reading, loaded from the server by the reading's id. */
function ReadingEvidence({ capture, timeZone }: { capture: MeterCaptureDto; timeZone: string }) {
  const load = useCallback(
    async (signal: AbortSignal): Promise<ExceptionDto[]> =>
      (
        await meterService.listExceptions(
          { page: 1, page_size: 100, filters: { meter_capture_id: capture.id } },
          signal,
        )
      ).items,
    [capture.id],
  );
  const findings = useAsyncResource(load);
  return (
    <AsyncContent resource={findings} errorTitle="Could not load the reading's findings">
      {(f) => <CaptureCard capture={capture} findings={f} timeZone={timeZone} />}
    </AsyncContent>
  );
}

/** One meter reading, by its own link: the page management opens from a record that cites a reading. */
export function MeterCaptureDetailPage() {
  const { captureId } = useParams();
  const timeZone = useDisplayTimeZone();
  const machineName = useMachineLabels();
  const load = useCallback(
    (id: string, signal: AbortSignal) => meterService.getCapture(id, signal),
    [],
  );
  const res = useRecordById<MeterCaptureDto>(load, captureId);
  return (
    <RecordDetail
      resource={res}
      what="meter reading"
      back={{ label: 'Exceptions', to: ROUTES.tenantExceptions }}
      timeZone={timeZone}
      title={(c) => `${humanize(c.kind)} reading ${c.reading}`}
      status={(c) => <CaptureStateChip state={c.state} />}
      links={(c) =>
        c.job_id === null ? null : (
          <Link component={RouterLink} to={jobDetailPath(c.job_id)}>
            Open job
          </Link>
        )
      }
      items={(c) => [
        { label: 'Machine', value: machineName(c.machine_id) },
        { label: 'Captured', value: formatInstantIn(c.captured_at, timeZone) },
        { label: 'Received', value: formatInstantIn(c.received_at, timeZone) },
        { label: 'Reading', value: c.reading },
      ]}
      history={(c) => [
        { key: 'captured', at: c.captured_at, label: 'Captured' },
        { key: 'received', at: c.received_at, label: 'Received' },
      ]}
    >
      {(c) => <ReadingEvidence capture={c} timeZone={timeZone} />}
    </RecordDetail>
  );
}
