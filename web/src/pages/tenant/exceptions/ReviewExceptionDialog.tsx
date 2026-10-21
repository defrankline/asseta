import { Typography } from '@mui/material';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { meterService } from '../../../api/services/meterService';
import type { ExceptionDto, ReviewOutcome } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { EXCEPTION_TYPE_LABELS } from '../../../components/meter/exceptionText';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../shared/errorHints';
import { REVIEW_OUTCOME_OPTIONS } from './exceptionDisplay';

interface ReviewValues {
  outcome: ReviewOutcome | '';
  note: string;
}

export const NOTE_REQUIRED = 'A review note is required';

const schema: ObjectSchema<ReviewValues> = object({
  outcome: mixed<ReviewOutcome | ''>()
    .oneOf(['EXPLAINED', 'CONFIRMED'], 'Choose an outcome')
    .required('Choose an outcome'),
  note: string()
    .trim()
    .required(NOTE_REQUIRED)
    .min(5, 'At least 5 characters')
    .max(2000, 'At most 2000 characters'),
});

const HINTS: Readonly<Record<string, string>> = {
  ALREADY_REVIEWED: 'Someone else has already reviewed this exception; reload the list.',
};

interface ReviewExceptionDialogProps {
  exception: ExceptionDto;
  onClose: () => void;
  onReviewed: (exception: ExceptionDto) => void;
}

/** Records the human review of one exception with a mandatory note (audited). */
export function ReviewExceptionDialog({
  exception,
  onClose,
  onReviewed,
}: ReviewExceptionDialogProps) {
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog<ReviewValues>
      open
      title={`Review · ${EXCEPTION_TYPE_LABELS[exception.exception_type]}`}
      initialValues={{ outcome: '', note: '' }}
      validationSchema={schema}
      submitLabel="Record review"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { outcome: v.outcome === '' ? 'EXPLAINED' : v.outcome, note: v.note.trim() };
        try {
          onReviewed(
            await meterService.reviewException(
              exception.id,
              body,
              keyFor({ id: exception.id, ...body }),
            ),
          );
        } catch (err) {
          throw withErrorCode(err, HINTS);
        }
      }}
    >
      <Typography variant="body2" color="text.secondary">
        Record what the review found. The note is kept in the audit trail together with the original
        evidence, which is never changed.
      </Typography>
      <FormikSelectField name="outcome" label="Outcome" options={REVIEW_OUTCOME_OPTIONS} required />
      <FormikTextField name="note" label="Review note" required multiline minRows={3} />
    </FormDialog>
  );
}
