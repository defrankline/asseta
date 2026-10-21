import { Alert, Box } from '@mui/material';
import { useState } from 'react';
import { customerService } from '../../../api/services/customerService';
import type { CategoryDto, RateCardDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { DateTimeField } from '../../../components/forms/DateTimeField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatInstantIn } from '../../../utils/time';
import { withErrorCode } from '../shared/errorHints';
import {
  emptyRateCardValues,
  RATE_FIELDS,
  rateCardFormSchema,
  toRateCardPayload,
  VERSION_FIELDS,
  type RateCardFormValues,
} from './rateCardForm';

const HINTS: Readonly<Record<string, string>> = {
  RATE_BACKDATED: 'Rate cards cannot be backdated; choose now or a future time.',
};

interface RateCardDialogProps {
  categories: readonly CategoryDto[];
  timeZone: string;
  onClose: () => void;
  onCreated: (card: RateCardDto) => void;
}

export const VERSIONING_NOTE =
  'Saving creates a new rate-card version from its effective time. Earlier versions are kept, and jobs already created keep the price they were created with.';

/** Rate → Version → Review. Owner-facing; each save is a new effective-dated version. */
export function RateCardDialog({ categories, timeZone, onClose, onCreated }: RateCardDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState(emptyRateCardValues);
  const categoryName = (id: string) => categories.find((c) => c.id === id)?.name ?? id;
  const steps: FormStep<RateCardFormValues>[] = [
    {
      label: 'Rate',
      fields: RATE_FIELDS,
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Box className="sm:col-span-2">
            <FormikSelectField
              name="machine_category_id"
              label="Machine category"
              required
              options={categories.map((c) => ({ value: c.id, label: c.name }))}
            />
          </Box>
          <FormikTextField
            name="hourly_rate"
            label="Hourly rate"
            required
            helperText="In the tenant currency"
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
          <FormikTextField
            name="minimum_hours"
            label="Minimum hours"
            required
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
        </Box>
      ),
    },
    {
      label: 'Version',
      fields: VERSION_FIELDS,
      render: (formik) => (
        <>
          <Alert severity="info">{VERSIONING_NOTE}</Alert>
          <DateTimeField
            label="Effective from (empty = now)"
            value={formik.values.effective_from === '' ? null : formik.values.effective_from}
            onChange={(v) => {
              void formik.setFieldValue('effective_from', v ?? '');
            }}
            timezone={timeZone}
            helperText="Rate cards cannot be backdated."
          />
          <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
        </>
      ),
    },
  ];
  return (
    <StepperFormDialog<RateCardFormValues>
      open
      title="New rate-card version"
      steps={steps}
      initialValues={initialValues}
      validationSchema={rateCardFormSchema}
      submitLabel="Create version"
      renderReview={(v) => (
        <>
          <Alert severity="info">{VERSIONING_NOTE}</Alert>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Machine category', value: categoryName(v.machine_category_id) },
              { label: 'Hourly rate', value: v.hourly_rate.trim() },
              { label: 'Minimum hours', value: `${v.minimum_hours.trim()} h` },
              {
                label: 'Effective from',
                value:
                  v.effective_from === '' ? 'Now' : formatInstantIn(v.effective_from, timeZone),
              },
              { label: 'Reason', value: v.reason.trim() },
            ]}
          />
        </>
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toRateCardPayload(values);
        try {
          onCreated(await customerService.createRateCard(payload, keyFor(payload)));
        } catch (err) {
          throw withErrorCode(err, HINTS);
        }
      }}
    />
  );
}
