import Draw from '@mui/icons-material/Draw';
import { Alert, Box, Button, Paper, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { jobService } from '../../../api/services/jobService';
import { meterService } from '../../../api/services/meterService';
import type { JobDto, JobStatus } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { labelOf } from '../shared/display';
import { ACK_METHOD_OPTIONS } from '../shared/jobDisplay';
import { AcknowledgementDialog } from './AcknowledgementDialog';

const ACKABLE: readonly JobStatus[] = ['APPROVED', 'IN_PROGRESS', 'COMPLETED'];

interface AcknowledgementTabProps {
  job: JobDto;
  suggestedHours: string | null;
  timeZone: string;
  onChanged: () => void;
}

/** Customer acknowledgements (name confirmation or signature image) recorded for the job. */
export function AcknowledgementTab({
  job,
  suggestedHours,
  timeZone,
  onChanged,
}: AcknowledgementTabProps) {
  const notify = useNotify();
  const { hasPermission } = useSession();
  const canRecord = useCanMutate(PERMISSIONS.tenantJobLog) && ACKABLE.includes(job.status);
  const canViewEvidence = hasPermission(PERMISSIONS.tenantMeterRead);
  const [open, setOpen] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => jobService.listAcknowledgements(job.id, signal),
    [job.id],
  );
  const resource = useAsyncResource(load);
  return (
    <Stack spacing={2}>
      <Box className="flex flex-wrap items-center justify-between gap-2">
        <Alert severity="info" className="grow">
          Completing a job requires a customer acknowledgement (ACK_REQUIRED otherwise). There is no
          external customer app: the supervisor records the representative&apos;s confirmation or
          signature.
        </Alert>
        {canRecord && (
          <Button
            variant="contained"
            startIcon={<Draw />}
            onClick={() => {
              setOpen(true);
            }}
          >
            Record acknowledgement
          </Button>
        )}
      </Box>
      <AsyncContent
        resource={resource}
        isEmpty={(d) => d.length === 0}
        emptyTitle="No acknowledgement recorded"
        errorTitle="Could not load acknowledgements"
      >
        {(d) => (
          <Stack spacing={2}>
            {d.map((ack) => (
              <Paper
                key={ack.id}
                variant="outlined"
                className="p-3"
                aria-label={`Acknowledgement by ${ack.signer_name}`}
              >
                <Stack spacing={1}>
                  <KeyValueGrid
                    columns={4}
                    items={[
                      { label: 'Method', value: labelOf(ACK_METHOD_OPTIONS, ack.method) },
                      { label: 'Customer representative', value: ack.signer_name },
                      { label: 'Phone', value: ack.signer_phone ?? '—' },
                      {
                        label: 'Acknowledged hours',
                        value:
                          ack.acknowledged_hours === null ? '—' : `${ack.acknowledged_hours} h`,
                      },
                      {
                        label: 'Acknowledged at',
                        value: formatInstantIn(ack.captured_at, timeZone),
                      },
                    ]}
                  />
                  {ack.signature_attachment_id !== null && canViewEvidence && (
                    <AttachmentPhoto
                      attachmentId={ack.signature_attachment_id}
                      fetchUrl={(id) => meterService.attachmentUrl(id)}
                      label="View signature"
                    />
                  )}
                </Stack>
              </Paper>
            ))}
          </Stack>
        )}
      </AsyncContent>
      {open && (
        <AcknowledgementDialog
          job={job}
          suggestedHours={suggestedHours}
          timeZone={timeZone}
          onClose={() => {
            setOpen(false);
          }}
          onRecorded={() => {
            notify.success('Customer acknowledgement recorded.');
            resource.reload();
            onChanged();
          }}
        />
      )}
    </Stack>
  );
}
