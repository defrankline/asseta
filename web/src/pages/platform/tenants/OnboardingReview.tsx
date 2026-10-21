import { Divider, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { formatDate } from '../../../utils/dates';
import { RateTermsReview } from '../shared/RateTermsReview';
import type { OnboardingValues } from './onboardingForm';

const dash = (v: string) => (v.trim() === '' ? '—' : v.trim());

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Stack spacing={1}>
      <Typography variant="subtitle2">{title}</Typography>
      {children}
    </Stack>
  );
}

export function OnboardingReview({ values: v }: { values: OnboardingValues }) {
  return (
    <Stack spacing={2} divider={<Divider flexItem />}>
      <Section title="Company">
        <KeyValueGrid
          items={[
            { label: 'Legal name', value: dash(v.legal_name) },
            { label: 'Display name', value: dash(v.display_name) },
            { label: 'Registration no.', value: dash(v.registration_number) },
            { label: 'Contact name', value: dash(v.contact_name) },
            { label: 'Contact email', value: dash(v.contact_email) },
            { label: 'Contact phone', value: dash(v.contact_phone) },
          ]}
        />
      </Section>
      <Section title="Settings">
        <KeyValueGrid
          items={[
            { label: 'Timezone', value: v.timezone },
            { label: 'Currency', value: v.currency },
            { label: 'Locale', value: v.locale },
          ]}
        />
      </Section>
      <Section title="Initial owner">
        <KeyValueGrid
          items={[
            { label: 'Email', value: dash(v.owner.email) },
            { label: 'Name', value: `${v.owner.first_name.trim()} ${v.owner.last_name.trim()}` },
          ]}
        />
      </Section>
      <Section title="Commercial terms">
        <KeyValueGrid
          items={[
            { label: 'Start date', value: formatDate(v.subscription.start_date) },
            { label: 'Trial days', value: v.subscription.trial_days },
            { label: 'Payment terms (days)', value: v.subscription.payment_terms_days },
          ]}
        />
        <RateTermsReview values={v.subscription.rate} />
      </Section>
    </Stack>
  );
}
