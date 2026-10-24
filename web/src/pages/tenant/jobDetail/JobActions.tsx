import { Box, Button, Typography } from '@mui/material';
import { useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { useMutationGuard } from '../../../access/useCanMutate';
import { jobService } from '../../../api/services/jobService';
import type { JobDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../shared/errorHints';
import { JOB_ERROR_HINTS, JOB_TRANSITIONS, type TransitionDef } from '../shared/jobDisplay';

interface ReasonValues {
  reason: string;
}

const schemaFor = (required: boolean): ObjectSchema<ReasonValues> =>
  object({
    reason: required
      ? string().trim().required('A reason is required').max(1000, 'At most 1000 characters')
      : string().trim().ensure().max(1000, 'At most 1000 characters'),
  });

interface TransitionDialogProps {
  job: JobDto;
  def: TransitionDef;
  onClose: () => void;
  onDone: (job: JobDto) => void;
}

/** Confirms one lifecycle action; failures keep the dialog open with the stable error code. */
export function TransitionDialog({ job, def, onClose, onDone }: TransitionDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<ReasonValues>
      open
      title={`${def.label} · ${job.job_number}`}
      initialValues={{ reason: '' }}
      validationSchema={schemaFor(def.reasonRequired)}
      submitLabel={def.label}
      onClose={onClose}
      onSubmit={async (v) => {
        const body = {
          action: def.action,
          reason: v.reason.trim() === '' ? null : v.reason.trim(),
        };
        try {
          onDone(
            await jobService.transition(job.id, body, keyFor({ ...body, version: job.version })),
          );
        } catch (err) {
          throw withErrorCode(err, JOB_ERROR_HINTS);
        }
      }}
    >
      <Typography variant="body2">{def.description}</Typography>
      <FormikTextField
        name="reason"
        label={def.reasonRequired ? 'Reason' : 'Note (optional)'}
        required={def.reasonRequired}
        multiline
        minRows={2}
      />
    </FormDialog>
  );
}

interface JobActionsProps {
  job: JobDto;
  onChanged: (job: JobDto) => void;
}

/** One button per lifecycle action allowed by the job status and the user's permissions. */
export function JobActions({ job, onChanged }: JobActionsProps) {
  const canMutate = useMutationGuard();
  const [active, setActive] = useState<TransitionDef | null>(null);
  const available = JOB_TRANSITIONS.filter(
    (t) => t.from.includes(job.status) && canMutate(t.permission),
  );
  if (available.length === 0) return null;
  return (
    <Box className="flex flex-wrap gap-2">
      {available.map((t) => (
        <Button
          key={t.action}
          variant={t.action === 'CANCEL' ? 'outlined' : 'contained'}
          color={t.action === 'CANCEL' ? 'error' : 'primary'}
          onClick={() => {
            setActive(t);
          }}
        >
          {t.label}
        </Button>
      ))}
      {active !== null && (
        <TransitionDialog
          job={job}
          def={active}
          onClose={() => {
            setActive(null);
          }}
          onDone={onChanged}
        />
      )}
    </Box>
  );
}
