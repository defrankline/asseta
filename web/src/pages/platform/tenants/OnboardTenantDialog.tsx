import { Alert, Box } from '@mui/material';
import { useMemo, useState } from 'react';
import { tenantService } from '../../../api/services/tenantService';
import type { OnboardResultDto } from '../../../api/types';
import { FormikAutocompleteField } from '../../../components/forms/FormikAutocompleteField';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { todayIsoDate } from '../../../utils/dates';
import { CURRENCY_OPTIONS } from '../shared/billingDisplay';
import { RatePolicyFields, RatePriceFields } from '../shared/RateTermsFields';
import {
  COMMERCIAL_FIELDS,
  COMPANY_FIELDS,
  initialOnboardingValues,
  onboardingSchema,
  OWNER_FIELDS,
  SETTINGS_FIELDS,
  timezoneOptions,
  toOnboardPayload,
  type OnboardingValues,
} from './onboardingForm';
import { OnboardingReview } from './OnboardingReview';

interface OnboardTenantDialogProps {
  onClose: () => void;
  onOnboarded: (result: OnboardResultDto) => void;
}

const grid = 'grid grid-cols-1 gap-4 sm:grid-cols-2';

/** Company → Settings → Owner → Commercial terms → Review. Mount only while open. */
export function OnboardTenantDialog({ onClose, onOnboarded }: OnboardTenantDialogProps) {
  const [initialValues] = useState(() => initialOnboardingValues(todayIsoDate()));
  const keyFor = useIdempotencyKey();
  const zones = useMemo(() => timezoneOptions(), []);

  const steps: FormStep<OnboardingValues>[] = [
    {
      label: 'Company',
      fields: COMPANY_FIELDS,
      render: () => (
        <Box className={grid}>
          <FormikTextField name="legal_name" label="Legal name" required />
          <FormikTextField name="display_name" label="Display name" required />
          <FormikTextField name="registration_number" label="Registration no." />
          <FormikTextField name="contact_name" label="Contact name" required />
          <FormikTextField name="contact_email" label="Contact email" type="email" required />
          <FormikTextField name="contact_phone" label="Contact phone" />
        </Box>
      ),
    },
    {
      label: 'Settings',
      fields: SETTINGS_FIELDS,
      render: () => (
        <Box className={grid}>
          <FormikAutocompleteField name="timezone" label="Timezone" options={zones} required />
          <FormikSelectField name="currency" label="Currency" options={CURRENCY_OPTIONS} required />
          <FormikTextField name="locale" label="Locale" required helperText="e.g. en, sw" />
        </Box>
      ),
    },
    {
      label: 'Owner',
      fields: OWNER_FIELDS,
      render: () => (
        <Box className={grid}>
          <FormikTextField name="owner.email" label="Owner email" type="email" required />
          <span />
          <FormikTextField name="owner.first_name" label="First name" required />
          <FormikTextField name="owner.last_name" label="Last name" required />
        </Box>
      ),
    },
    {
      label: 'Commercial terms',
      fields: COMMERCIAL_FIELDS,
      render: () => (
        <>
          <Alert severity="info">
            Price is negotiated per tenant: amount per billable asset per billing period.
          </Alert>
          <Box className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <FormikDateField name="subscription.start_date" label="Start date" required />
            <FormikTextField
              name="subscription.trial_days"
              label="Trial days"
              slotProps={{ htmlInput: { inputMode: 'numeric' } }}
            />
            <FormikTextField
              name="subscription.payment_terms_days"
              label="Payment terms (days)"
              slotProps={{ htmlInput: { inputMode: 'numeric' } }}
            />
          </Box>
          <RatePriceFields prefix="subscription.rate." />
          <RatePolicyFields prefix="subscription.rate." />
        </>
      ),
    },
  ];

  return (
    <StepperFormDialog<OnboardingValues>
      open
      title="Onboard tenant"
      steps={steps}
      initialValues={initialValues}
      validationSchema={onboardingSchema}
      renderReview={(values) => <OnboardingReview values={values} />}
      submitLabel="Onboard tenant"
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toOnboardPayload(values);
        const result = await tenantService.onboard(payload, keyFor(payload));
        onOnboarded(result);
      }}
    />
  );
}
