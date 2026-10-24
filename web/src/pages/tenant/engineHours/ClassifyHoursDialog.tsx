import { Alert } from '@mui/material';
import { useFormikContext } from 'formik';
import { useEffect, useRef } from 'react';
import { mixed, object, string, type ObjectSchema } from 'yup';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type {
  ClassificationDto,
  ClassificationIn,
  ClassificationOutcome,
  EngineHourReasonDto,
  LedgerPointDto,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import { optionId } from '../shared/lookups';
import {
  ENGINE_HOURS_ERROR_HINTS,
  hoursText,
  OUTCOME_OPTIONS,
  OUTCOME_REASON_KIND,
  sourceLabel,
} from './engineHoursDisplay';
import { reasonLabel, resolveReason, searchReasons } from './engineHoursLookups';
import { DECISION_NOTE_MIN } from './MeterDecisionDialog';

/** The unallocated hours being explained: one ledger interval between two readings. */
export interface SegmentRef {
  machineId: string;
  machineLabel: string;
  start: LedgerPointDto;
  end: LedgerPointDto;
  hours: string;
}

interface ClassifyValues {
  outcome: ClassificationOutcome | '';
  reason_id: string;
  note: string;
}

const schema: ObjectSchema<ClassifyValues> = object({
  outcome: mixed<ClassificationOutcome | ''>()
    .oneOf(['APPROVED_NON_CUSTOMER', 'IDENTIFIED_VARIANCE'], 'Choose what the hours were')
    .required('Choose what the hours were'),
  reason_id: string().required('Choose the category or reason'),
  note: string()
    .trim()
    .required('Explain what happened')
    .min(DECISION_NOTE_MIN, `At least ${String(DECISION_NOTE_MIN)} characters`)
    .max(2000, 'At most 2000 characters'),
});

/** A reason belongs to one list: changing the outcome clears the chosen entry. */
function ClearReasonOnOutcomeChange({ outcome }: { outcome: string }) {
  const { setFieldValue } = useFormikContext<ClassifyValues>();
  const previous = useRef(outcome);
  useEffect(() => {
    if (previous.current !== outcome) {
      previous.current = outcome;
      void setFieldValue('reason_id', '');
    }
  }, [outcome, setFieldValue]);
  return null;
}

const searchCategories = searchReasons('NON_CUSTOMER_CATEGORY');
const searchVariances = searchReasons('VARIANCE_REASON');

interface ClassifyHoursDialogProps {
  segment: SegmentRef;
  onClose: () => void;
  onProposed: (c: ClassificationDto) => void;
}

/**
 * Explain unallocated engine hours as approved non-customer activity or an identified variance.
 * It takes effect when a second person with the classify permission approves (unless the tenant's
 * policy lets a classify-permission holder record it directly). Time never changes a classification.
 */
export function ClassifyHoursDialog({ segment, onClose, onProposed }: ClassifyHoursDialogProps) {
  const keyFor = useIdempotencyKey();
  const timeZone = useDisplayTimeZone();
  return (
    <FormDialog<ClassifyValues>
      open
      title={`Explain ${hoursText(segment.hours)} · ${segment.machineLabel}`}
      initialValues={{ outcome: '', reason_id: '', note: '' }}
      validationSchema={schema}
      submitLabel="Propose explanation"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: ClassificationIn = {
          machine_id: segment.machineId,
          start_ref: segment.start.ref,
          end_ref: segment.end.ref,
          outcome:
            v.outcome === 'IDENTIFIED_VARIANCE' ? 'IDENTIFIED_VARIANCE' : 'APPROVED_NON_CUSTOMER',
          reason_id: v.reason_id,
          note: v.note.trim(),
        };
        try {
          onProposed(await engineHoursService.proposeClassification(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
        }
      }}
    >
      {(formik) => {
        const kind =
          formik.values.outcome === '' ? null : OUTCOME_REASON_KIND[formik.values.outcome];
        return (
          <>
            <KeyValueGrid
              columns={2}
              items={[
                {
                  label: 'From',
                  value: `${segment.start.reading} h · ${sourceLabel(segment.start.source)} · ${formatInstantIn(segment.start.at, timeZone)}`,
                },
                {
                  label: 'To',
                  value: `${segment.end.reading} h · ${sourceLabel(segment.end.source)} · ${formatInstantIn(segment.end.at, timeZone)}`,
                },
              ]}
            />
            <Alert severity="info">
              Hours outside customer work stay &quot;not yet explained&quot; until someone explains
              them and, where your policy needs it, another person approves. Unexplained hours are
              not a finding against anyone.
            </Alert>
            <FormikSelectField
              name="outcome"
              label="What were these hours?"
              options={OUTCOME_OPTIONS}
              required
            />
            <ClearReasonOnOutcomeChange outcome={formik.values.outcome} />
            {kind !== null && (
              <FormikAsyncIdAutocomplete<EngineHourReasonDto>
                key={kind}
                name="reason_id"
                label={kind === 'NON_CUSTOMER_CATEGORY' ? 'Activity category' : 'Variance reason'}
                fetchOptions={kind === 'NON_CUSTOMER_CATEGORY' ? searchCategories : searchVariances}
                resolveOption={resolveReason}
                getOptionId={optionId}
                getOptionLabel={reasonLabel}
                required
                noOptionsText="No active entries; add them under Engine-hour reasons"
              />
            )}
            <FormikTextField
              name="note"
              label="What happened"
              required
              multiline
              minRows={2}
              helperText="Kept on the record for audit (at least 5 characters)."
            />
          </>
        );
      }}
    </FormDialog>
  );
}
