import Add from '@mui/icons-material/Add';
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';
import { Alert, Box, Button, IconButton, Paper, Typography } from '@mui/material';
import { FieldArray, type FormikProps } from 'formik';
import { useState } from 'react';
import { array, mixed, object, string, type ObjectSchema } from 'yup';
import type {
  AllocationCorrectionDto,
  AllocationCorrectionIn,
  AllocationKind,
  WorkAllocationDto,
} from '../../../../api/allocationTypes';
import { engineHoursService } from '../../../../api/services/engineHoursService';
import { allocationService } from '../../../../api/services/allocationService';
import type { AttachmentDto, EngineHourReasonDto } from '../../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../../components/data/AsyncAutocomplete';
import { FormDialog } from '../../../../components/forms/FormDialog';
import { FormikAsyncIdAutocomplete } from '../../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../../hooks/useIdempotencyKey';
import { withErrorCode } from '../../shared/errorHints';
import { FormikCustomerIdPicker, FormikJobIdPicker } from '../../shared/financePickers';
import { optionId } from '../../shared/lookups';
import { ENGINE_HOURS_ERROR_HINTS } from '../engineHoursDisplay';
import { reasonLabel, resolveReason } from '../engineHoursLookups';
import { fromHundredths, HOURS_PATTERN, KIND_OPTIONS, toHundredths } from './allocationDisplay';
import { EvidenceUpload } from './EvidenceUpload';

/** The server takes at most this many parts in one correction. */
const MAX_PARTS = 10;

interface PartValues {
  hours: string;
  kind: AllocationKind;
  customer_id: string;
  job_id: string;
  reason_id: string;
}

interface CorrectionValues {
  parts: PartValues[];
  reason: string;
}

/** Sum of the parts' hours, in hundredths; a part not yet valid counts as nothing. */
const partsTotal = (parts: readonly PartValues[]): number =>
  parts.reduce((n, p) => n + (HOURS_PATTERN.test(p.hours) ? toHundredths(p.hours) : 0), 0);

const partSchema: ObjectSchema<PartValues> = object({
  hours: string()
    .trim()
    .required('Hours are required')
    .matches(HOURS_PATTERN, 'Up to 2 decimals')
    .test('positive', 'More than 0', (v) => Number(v) > 0),
  kind: mixed<AllocationKind>()
    .oneOf(['CUSTOMER_WORK', 'AUTHORIZED_ACTIVITY', 'UNEXPLAINED'])
    .required('Choose the kind'),
  customer_id: string()
    .ensure()
    .test(
      'customer',
      'Choose the customer',
      (v, ctx) => (ctx.parent as PartValues).kind !== 'CUSTOMER_WORK' || v !== '',
    ),
  job_id: string().ensure(),
  reason_id: string()
    .ensure()
    .test(
      'reason',
      'Choose the category or reason',
      (v, ctx) => (ctx.parent as PartValues).kind !== 'AUTHORIZED_ACTIVITY' || v !== '',
    ),
});

const schemaFor = (total: string): ObjectSchema<CorrectionValues> =>
  object({
    parts: array(partSchema)
      .min(1)
      .max(MAX_PARTS)
      .required()
      .test(
        'total',
        `The parts must total ${total} h`,
        (parts) => partsTotal(parts) === toHundredths(total),
      ),
    reason: string()
      .trim()
      .required('A reason is required')
      .min(5, 'At least 5 characters')
      .max(2000, 'At most 2000 characters'),
  });

/** Non-customer categories and variance reasons (an authorized activity takes either list). */
const searchActivityReasons = async (
  q: string,
  signal: AbortSignal,
): Promise<EngineHourReasonDto[]> =>
  (
    await engineHoursService.listReasons({ page: 1, page_size: LOOKUP_PAGE_SIZE, q }, signal)
  ).items.filter((r) => r.kind !== 'UNBILLABLE_REASON');

const emptyPart = (): PartValues => ({
  hours: '',
  kind: 'CUSTOMER_WORK',
  customer_id: '',
  job_id: '',
  reason_id: '',
});

function PartsFields({ formik, total }: { formik: FormikProps<CorrectionValues>; total: string }) {
  const { parts } = formik.values;
  const sum = partsTotal(parts);
  const gap = toHundredths(total) - sum;
  const partsError =
    formik.submitCount > 0 && typeof formik.errors.parts === 'string' ? formik.errors.parts : null;
  return (
    <FieldArray name="parts">
      {(helpers) => (
        <Box className="flex flex-col gap-2">
          {parts.map((p, i) => (
            <Paper key={i} variant="outlined" className="flex flex-col gap-3 p-3">
              <Box className="flex items-center justify-between">
                <Typography variant="subtitle2">Part {i + 1}</Typography>
                {parts.length > 1 && (
                  <IconButton
                    size="small"
                    aria-label={`Remove part ${String(i + 1)}`}
                    onClick={() => {
                      helpers.remove(i);
                    }}
                  >
                    <DeleteOutlined fontSize="small" />
                  </IconButton>
                )}
              </Box>
              <Box className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <FormikTextField name={`parts.${String(i)}.hours`} label="Hours" required />
                <FormikSelectField
                  name={`parts.${String(i)}.kind`}
                  label="Kind"
                  options={KIND_OPTIONS}
                  required
                />
              </Box>
              {p.kind === 'CUSTOMER_WORK' && (
                <Box className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <FormikCustomerIdPicker
                    name={`parts.${String(i)}.customer_id`}
                    label="Customer"
                    required
                  />
                  <FormikJobIdPicker name={`parts.${String(i)}.job_id`} label="Job (optional)" />
                </Box>
              )}
              {p.kind === 'AUTHORIZED_ACTIVITY' && (
                <FormikAsyncIdAutocomplete<EngineHourReasonDto>
                  name={`parts.${String(i)}.reason_id`}
                  label="Category or reason"
                  required
                  fetchOptions={searchActivityReasons}
                  resolveOption={resolveReason}
                  getOptionId={optionId}
                  getOptionLabel={reasonLabel}
                />
              )}
            </Paper>
          ))}
          <Box className="flex flex-wrap items-center justify-between gap-2">
            <Button
              size="small"
              startIcon={<Add />}
              disabled={parts.length >= MAX_PARTS}
              onClick={() => {
                helpers.push(emptyPart());
              }}
            >
              Add part
            </Button>
            <Typography variant="body2" color={gap === 0 ? 'text.secondary' : 'error'}>
              Parts total {fromHundredths(sum)} of {total} h
              {gap !== 0 && ` (${fromHundredths(Math.abs(gap))} h ${gap > 0 ? 'short' : 'over'})`}
            </Typography>
          </Box>
          {partsError !== null && <Alert severity="error">{partsError}</Alert>}
        </Box>
      )}
    </FieldArray>
  );
}

interface AllocationCorrectionDialogProps {
  allocation: WorkAllocationDto;
  onClose: () => void;
  onProposed: (c: AllocationCorrectionDto) => void;
}

/** Propose new entries replacing this one: parts total the original; the original stays on record. */
export function AllocationCorrectionDialog({
  allocation,
  onClose,
  onProposed,
}: AllocationCorrectionDialogProps) {
  const keyFor = useIdempotencyKey();
  const [evidence, setEvidence] = useState<AttachmentDto[]>([]);
  return (
    <FormDialog<CorrectionValues>
      open
      title={`Propose a correction · ${allocation.hours} h`}
      initialValues={{
        parts: [
          {
            hours: fromHundredths(toHundredths(allocation.hours)),
            kind: allocation.kind,
            customer_id: allocation.customer_id ?? '',
            job_id: allocation.job_id ?? '',
            reason_id: allocation.reason_id ?? '',
          },
        ],
        reason: '',
      }}
      validationSchema={schemaFor(allocation.hours)}
      submitLabel="Propose correction"
      maxWidth="md"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: AllocationCorrectionIn = {
          parts: v.parts.map((p) => ({
            hours: p.hours.trim(),
            kind: p.kind,
            customer_id: p.kind === 'CUSTOMER_WORK' ? p.customer_id : null,
            job_id: p.kind === 'CUSTOMER_WORK' && p.job_id !== '' ? p.job_id : null,
            reason_id: p.kind === 'AUTHORIZED_ACTIVITY' ? p.reason_id : null,
          })),
          reason: v.reason.trim(),
          evidence_attachment_ids: evidence.map((a) => a.id),
        };
        try {
          onProposed(await allocationService.proposeCorrection(allocation.id, body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, ENGINE_HOURS_ERROR_HINTS);
        }
      }}
    >
      {(formik) => (
        <>
          <Alert severity="info">
            Split the entry into parts that total its hours. The original stays on record; a second
            person decides unless your company&apos;s policy applies corrections directly.
          </Alert>
          <PartsFields formik={formik} total={allocation.hours} />
          <FormikTextField
            name="reason"
            label="Reason for the correction"
            required
            multiline
            minRows={2}
            helperText="Kept on the record for audit (at least 5 characters)."
          />
          <EvidenceUpload value={evidence} onChange={setEvidence} />
        </>
      )}
    </FormDialog>
  );
}
