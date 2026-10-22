import { Alert, Typography } from '@mui/material';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { caseService } from '../../../api/services/caseService';
import type {
  AnomalyCaseDetailDto,
  AnomalyCaseDto,
  CaseOutcomeKind,
  PersonDto,
} from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../shared/errorHints';
import {
  CASE_ERROR_HINTS,
  EXPLANATION_MAX,
  EXPLANATION_MIN,
  EXPLANATION_TOO_SHORT,
  OUTCOME_OPTIONS,
  OUTCOME_REQUIRED,
  personId,
  personLabel,
  REOPEN_REASON_MAX,
  searchPeople,
} from './caseDisplay';

interface CaseDialogProps {
  case: AnomalyCaseDto;
  onClose: () => void;
  onDone: (detail: AnomalyCaseDetailDto) => void;
  /** Reload the case after STALE_VERSION (the dialog closes). */
  onReload: () => void;
}

// ---- Assign -------------------------------------------------------------------------------------

interface AssignValues {
  assignee_user_id: string;
}

const assignSchema: ObjectSchema<AssignValues> = object({
  assignee_user_id: string().required('Choose who reviews this case'),
});

/** Assign the case to a tenant member (never someone whose own records are part of the evidence). */
export function AssignCaseDialog({ case: c, onClose, onDone, onReload }: CaseDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  return (
    <FormDialog<AssignValues>
      open
      title={`Assign ${c.case_number}`}
      initialValues={{ assignee_user_id: '' }}
      validationSchema={assignSchema}
      submitLabel="Assign"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { assignee_user_id: v.assignee_user_id, version: c.version };
        try {
          onDone(await guard(() => caseService.assign(c.id, body, keyFor(body))));
        } catch (err) {
          throw withErrorCode(err, CASE_ERROR_HINTS);
        }
      }}
    >
      {stale && (
        <StaleVersionAlert
          onReload={() => {
            onReload();
            onClose();
          }}
        />
      )}
      <Typography variant="body2" color="text.secondary">
        The assignee reviews the evidence and records notes. People whose own captures, expenses or
        custody are part of the evidence cannot be assigned.
      </Typography>
      <FormikAsyncIdAutocomplete<PersonDto>
        name="assignee_user_id"
        label="Assignee"
        required
        fetchOptions={searchPeople}
        getOptionId={personId}
        getOptionLabel={personLabel}
      />
    </FormDialog>
  );
}

// ---- Resolve ------------------------------------------------------------------------------------

interface ResolveValues {
  outcome: CaseOutcomeKind | '';
  explanation: string;
}

const resolveSchema: ObjectSchema<ResolveValues> = object({
  outcome: mixed<CaseOutcomeKind | ''>()
    .oneOf(['CONFIRMED_ISSUE', 'UNCONFIRMED', 'LEGITIMATE_EXPLANATION'], OUTCOME_REQUIRED)
    .required(OUTCOME_REQUIRED),
  explanation: string()
    .trim()
    .required('An explanation is required')
    .min(EXPLANATION_MIN, EXPLANATION_TOO_SHORT)
    .max(EXPLANATION_MAX, `At most ${String(EXPLANATION_MAX)} characters`),
});

/** Record the review outcome with an explanation; the outcome is kept unchanged (append-only). */
export function ResolveCaseDialog({ case: c, onClose, onDone, onReload }: CaseDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  return (
    <FormDialog<ResolveValues>
      open
      title={`Resolve ${c.case_number}`}
      initialValues={{ outcome: '', explanation: '' }}
      validationSchema={resolveSchema}
      submitLabel="Record outcome"
      onClose={onClose}
      onSubmit={async (v) => {
        if (v.outcome === '') return;
        const body = { outcome: v.outcome, explanation: v.explanation.trim(), version: c.version };
        try {
          onDone(await guard(() => caseService.resolve(c.id, body, keyFor(body))));
        } catch (err) {
          throw withErrorCode(err, CASE_ERROR_HINTS);
        }
      }}
    >
      {stale && (
        <StaleVersionAlert
          onReload={() => {
            onReload();
            onClose();
          }}
        />
      )}
      <Alert severity="info">
        Record what the review found. The outcome describes the evidence, not a person, and stays
        unchanged in the case history. You cannot resolve a case built on your own records.
      </Alert>
      <FormikSelectField name="outcome" label="Outcome" options={OUTCOME_OPTIONS} required />
      <FormikTextField
        name="explanation"
        label="Explanation"
        required
        multiline
        minRows={3}
        helperText={`${String(EXPLANATION_MIN)}–${String(EXPLANATION_MAX)} characters; kept with the outcome for audit.`}
      />
    </FormDialog>
  );
}

// ---- Reopen -------------------------------------------------------------------------------------

interface ReopenValues {
  reason: string;
}

const reopenSchema: ObjectSchema<ReopenValues> = object({
  reason: string()
    .trim()
    .required('A reason is required')
    .min(EXPLANATION_MIN, EXPLANATION_TOO_SHORT)
    .max(REOPEN_REASON_MAX, `At most ${String(REOPEN_REASON_MAX)} characters`),
});

/** Reopen a resolved case (back to In review); the earlier outcome stays in the history. */
export function ReopenCaseDialog({ case: c, onClose, onDone, onReload }: CaseDialogProps) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  return (
    <FormDialog<ReopenValues>
      open
      title={`Reopen ${c.case_number}`}
      initialValues={{ reason: '' }}
      validationSchema={reopenSchema}
      submitLabel="Reopen case"
      onClose={onClose}
      onSubmit={async (v) => {
        const body = { reason: v.reason.trim(), version: c.version };
        try {
          onDone(await guard(() => caseService.reopen(c.id, body, keyFor(body))));
        } catch (err) {
          throw withErrorCode(err, CASE_ERROR_HINTS);
        }
      }}
    >
      {stale && (
        <StaleVersionAlert
          onReload={() => {
            onReload();
            onClose();
          }}
        />
      )}
      <Typography variant="body2" color="text.secondary">
        The case returns to In review. The recorded outcome is kept; the next resolution records a
        new one. The reason is added to the case notes.
      </Typography>
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </FormDialog>
  );
}
