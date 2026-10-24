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
import { compareDecimal, isDecimalString } from '../../../utils/money';
import { optionalDecimal, requiredDecimal } from '../shared/formRules';
import {
  cancelLabelFor,
  isFieldRequest,
  JOB_ERROR_HINTS,
  JOB_TRANSITIONS,
  PENDING_PRICE,
  type TransitionDef,
} from '../shared/jobDisplay';
import { FieldRequestInfo } from './FieldRequestInfo';

interface TransitionValues {
  reason: string;
  /** APPROVE only: the approved hourly price (required for a job without a price yet). */
  hourly_rate: string;
}

const schemaFor = (
  reasonRequired: boolean,
  priceRequired: boolean,
): ObjectSchema<TransitionValues> =>
  object({
    reason: reasonRequired
      ? string().trim().required('A reason is required').max(1000, 'At most 1000 characters')
      : string().trim().ensure().max(1000, 'At most 1000 characters'),
    hourly_rate: priceRequired ? requiredDecimal('Hourly rate') : optionalDecimal('Hourly rate'),
  });

/** Send a price with APPROVE only when one is needed or the approver changed it. */
function approvedRate(job: JobDto, entered: string): string | null {
  const rate = entered.trim();
  if (rate === '') return null;
  if (job.rate_source === PENDING_PRICE) return rate;
  return isDecimalString(job.hourly_rate) && compareDecimal(rate, job.hourly_rate) === 0
    ? null
    : rate;
}

interface TransitionDialogProps {
  job: JobDto;
  def: TransitionDef;
  onClose: () => void;
  onDone: (job: JobDto) => void;
}

/** Confirms one lifecycle action; failures keep the dialog open with the stable error code. */
export function TransitionDialog({ job, def, onClose, onDone }: TransitionDialogProps) {
  const keyFor = useIdempotencyKey();
  const approve = def.action === 'APPROVE';
  const decline = def.action === 'CANCEL' && isFieldRequest(job);
  const pendingPrice = approve && job.rate_source === PENDING_PRICE;
  const label = def.action === 'CANCEL' ? cancelLabelFor(job) : def.label;
  return (
    <FormDialog<TransitionValues>
      open
      title={`${label} · ${job.job_number}`}
      initialValues={{ reason: '', hourly_rate: pendingPrice ? '' : job.hourly_rate }}
      validationSchema={schemaFor(def.reasonRequired, pendingPrice)}
      submitLabel={label}
      onClose={onClose}
      onSubmit={async (v) => {
        const rate = approve ? approvedRate(job, v.hourly_rate) : null;
        const body = {
          action: def.action,
          reason: v.reason.trim() === '' ? null : v.reason.trim(),
          ...(rate === null ? {} : { hourly_rate: rate }),
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
      {(approve || decline) && <FieldRequestInfo job={job} />}
      <Typography variant="body2">
        {decline
          ? 'Decline the request. The supervisor is told your reason; the job stays on record as cancelled.'
          : def.description}
      </Typography>
      {approve && (
        <FormikTextField
          name="hourly_rate"
          label={`Hourly rate (${job.currency})`}
          required={pendingPrice}
          helperText={
            pendingPrice
              ? 'No rate card applies; the job is approved at this price.'
              : 'Change only to approve at a different price.'
          }
          slotProps={{ htmlInput: { inputMode: 'decimal' } }}
        />
      )}
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
          {t.action === 'CANCEL' ? cancelLabelFor(job) : t.label}
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
