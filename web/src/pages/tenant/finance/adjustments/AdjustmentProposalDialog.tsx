import { Alert } from '@mui/material';
import type { FormikProps, FormikValues } from 'formik';
import type { ReactNode } from 'react';
import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type { AdjustmentPreviewIn } from '../../../../api/adjustmentTypes';
import type { ReasonKind } from '../../../../api/hoursTypes';
import type { AttachmentDto } from '../../../../api/types';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { EvidenceUpload } from '../../engineHours/allocations/EvidenceUpload';
import { FormikReasonCodePicker } from '../../hours/hoursPickers';
import { withErrorCode } from '../../shared/errorHints';
import { ADJUSTMENT_ERROR_HINTS } from './adjustmentDisplay';
import { AdjustmentForecast } from './AdjustmentForecast';
import { useAdjustmentPolicy } from './useAdjustmentPolicy';

interface CommonValues {
  reason: string;
  reason_code_id: string;
  evidence: AttachmentDto[];
}

/** What every correction, refund, reversal and void carries. */
export interface ProposalCommon {
  reason: string;
  reason_code_id: string | null;
  evidence_attachment_ids: string[];
}

interface Props<E extends FormikValues, T> {
  title: string;
  submitLabel: string;
  reasonKind: ReasonKind;
  summary?: ReactNode;
  /** The form's own fields beyond reason and evidence. */
  initial: E;
  shape?: Parameters<typeof object>[0];
  fields?: (formik: FormikProps<E & CommonValues>) => ReactNode;
  /** Forecast shown before proposing: the request as it stands, or null while it is incomplete. */
  forecast?: (values: E) => AdjustmentPreviewIn | null;
  submit: (common: ProposalCommon, values: E, key: string) => Promise<T>;
  onDone: (result: T) => void;
  onClose: () => void;
}

/** Shared form of the adjustment actions: reason from the tenant list, free text, evidence. */
export function AdjustmentProposalDialog<E extends FormikValues, T>({
  title,
  submitLabel,
  reasonKind,
  summary,
  initial,
  shape = {},
  fields,
  forecast,
  submit,
  onDone,
  onClose,
}: Props<E, T>) {
  const keyFor = useIdempotencyKey();
  const policy = useAdjustmentPolicy();
  const evidenceRequired = policy.evidenceRequired;
  const schema = object({
    ...shape,
    reason: string()
      .trim()
      .required('A reason is required')
      .min(3, 'At least 3 characters')
      .max(1000, 'At most 1000 characters'),
    reason_code_id: string()
      .ensure()
      .test(
        'required',
        'Choose a reason from the list',
        (v) => !policy.reasonCodeRequired || v !== '',
      ),
    evidence: array(mixed<AttachmentDto>().required())
      .required()
      .test('required', 'Attach the supporting evidence', (v) => !evidenceRequired || v.length > 0),
  }) as unknown as ObjectSchema<E & CommonValues>;
  const initialValues = { ...initial, reason: '', reason_code_id: '', evidence: [] };
  return (
    <FormDialog<E & CommonValues>
      open
      title={title}
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel={submitLabel}
      onClose={onClose}
      onSubmit={async (v) => {
        const common: ProposalCommon = {
          reason: v.reason.trim(),
          reason_code_id: v.reason_code_id === '' ? null : v.reason_code_id,
          evidence_attachment_ids: v.evidence.map((a) => a.id),
        };
        const key = keyFor({ ...v, evidence: common.evidence_attachment_ids });
        try {
          onDone(await submit(common, v, key));
        } catch (err) {
          throw withErrorCode(err, ADJUSTMENT_ERROR_HINTS);
        }
      }}
    >
      {(f) => (
        <>
          {summary}
          {fields?.(f)}
          {forecast !== undefined && <AdjustmentForecast body={forecast(f.values)} />}
          <FormikReasonCodePicker
            name="reason_code_id"
            kind={reasonKind}
            label="Reason from your list"
            required={policy.reasonCodeRequired}
          />
          <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
          <EvidenceUpload
            value={f.values.evidence}
            onChange={(next) => {
              void f.setFieldValue('evidence', next);
            }}
            purpose="ADJUSTMENT_EVIDENCE"
            label="Evidence"
            required={evidenceRequired}
            helperText={
              policy.known
                ? 'Stored unchanged with its SHA-256 hash.'
                : 'Your company policy may require evidence.'
            }
          />
          {f.submitCount > 0 && typeof f.errors.evidence === 'string' && (
            <Alert severity="error">{f.errors.evidence}</Alert>
          )}
        </>
      )}
    </FormDialog>
  );
}
