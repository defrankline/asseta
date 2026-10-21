import { Alert, Box } from '@mui/material';
import { useState } from 'react';
import { object } from 'yup';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type { NewRateVersionIn, RateVersionDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatDate, todayIsoDate } from '../../../utils/dates';
import {
  RATE_POLICY_FIELDS,
  RATE_PRICE_FIELDS,
  RATE_TERM_DEFAULTS,
  rateTermsShape,
  toRateTermsIn,
  type RateTermsValues,
} from '../shared/rateTerms';
import { RatePolicyFields, RatePriceFields } from '../shared/RateTermsFields';
import { RateTermsReview } from '../shared/RateTermsReview';
import { isoDateField, reasonField } from '../shared/validators';

interface NewRateValues extends RateTermsValues {
  effective_from: string;
  reason: string;
}

function fromCurrent(rate: RateVersionDto | null): RateTermsValues {
  if (rate === null) return { ...RATE_TERM_DEFAULTS };
  return {
    currency: rate.currency,
    cadence: rate.cadence,
    unit_price: rate.unit_price,
    minimum_billable_assets: String(rate.minimum_billable_assets),
    discount_percent: rate.discount_percent,
    tax_name: rate.tax_name ?? '',
    tax_rate_percent: rate.tax_rate_percent,
    mid_cycle_add: rate.mid_cycle_add,
    mid_cycle_remove: rate.mid_cycle_remove,
    rounding_mode: rate.rounding_mode,
  };
}

interface NewRateVersionDialogProps {
  subscriptionId: string;
  currentRate: RateVersionDto | null;
  onClose: () => void;
  onCreated: (rate: RateVersionDto) => void;
}

/** Renegotiation creates a new immutable, effective-dated rate version (no backdating). */
export function NewRateVersionDialog({
  subscriptionId,
  currentRate,
  onClose,
  onCreated,
}: NewRateVersionDialogProps) {
  const keyFor = useIdempotencyKey();
  const today = todayIsoDate();
  const [initialValues] = useState<NewRateValues>(() => ({
    ...fromCurrent(currentRate),
    effective_from: today,
    reason: '',
  }));
  const [schema] = useState(() =>
    object({
      ...rateTermsShape,
      effective_from: isoDateField('Effective from').test(
        'not-backdated',
        'Rate versions cannot be backdated',
        (v) => v >= today,
      ),
      reason: reasonField(),
    }),
  );

  return (
    <StepperFormDialog<NewRateValues>
      open
      title="New rate version"
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Create rate version"
      onClose={onClose}
      steps={[
        {
          label: 'Price',
          fields: ['effective_from', 'reason', ...RATE_PRICE_FIELDS],
          render: () => (
            <>
              <Alert severity="info">
                Previous versions stay unchanged and issued invoices are never rewritten. Changing
                the cadence requires a new subscription.
              </Alert>
              <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormikDateField
                  name="effective_from"
                  label="Effective from"
                  required
                  minDate={today}
                />
                <FormikTextField name="reason" label="Reason" required />
              </Box>
              <RatePriceFields />
            </>
          ),
        },
        {
          label: 'Adjustments & policy',
          fields: RATE_POLICY_FIELDS,
          render: () => <RatePolicyFields />,
        },
      ]}
      renderReview={(v) => (
        <>
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Effective from', value: formatDate(v.effective_from) },
              { label: 'Reason', value: v.reason.trim() },
            ]}
          />
          <RateTermsReview values={v} />
        </>
      )}
      onSubmit={async (v) => {
        const body: NewRateVersionIn = {
          ...toRateTermsIn(v),
          effective_from: v.effective_from,
          reason: v.reason.trim(),
        };
        onCreated(await subscriptionService.createRateVersion(subscriptionId, body, keyFor(body)));
      }}
    />
  );
}
