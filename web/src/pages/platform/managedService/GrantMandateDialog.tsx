import { Alert, Box } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { mandateService } from '../../../api/services/mandateService';
import { tenantService } from '../../../api/services/tenantService';
import type { MandateDetailDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikSelectField, type SelectOption } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatDate, todayIsoDate } from '../../../utils/dates';
import { optionLabel } from '../shared/billingDisplay';
import { grantSchema, SCOPE_OPTIONS, toGrantBody, type GrantFormValues } from './grantForm';

/** Clients offered in the grant form (the platform tenant list, first page by name). */
const TENANT_QUERY = { page: 1, page_size: 200, sort: 'name' } as const;

interface GrantMandateDialogProps {
  onClose: () => void;
  onGranted: (mandate: MandateDetailDto) => void;
}

/** Client & scope → Consent & term → Review. Mount only while open. */
export function GrantMandateDialog({ onClose, onGranted }: GrantMandateDialogProps) {
  const keyFor = useIdempotencyKey();
  const loadTenants = useCallback(
    (signal: AbortSignal) => tenantService.list(TENANT_QUERY, signal),
    [],
  );
  const tenants = useAsyncResource(loadTenants);
  const tenantOptions = useMemo<SelectOption[]>(
    () => (tenants.data?.items ?? []).map((t) => ({ value: t.id, label: t.display_name })),
    [tenants.data],
  );
  const [initialValues] = useState<GrantFormValues>(() => ({
    tenant_id: '',
    scope: 'FULL',
    starts_on: todayIsoDate(),
    ends_on: '',
    consent_reference: '',
    notes: '',
  }));

  const steps: FormStep<GrantFormValues>[] = [
    {
      label: 'Client & scope',
      fields: ['tenant_id', 'scope'],
      render: () => (
        <>
          {tenants.error !== null && (
            <Alert severity="error">Could not load clients: {tenants.error.message}</Alert>
          )}
          <FormikSelectField
            name="tenant_id"
            label="Client tenant"
            options={tenantOptions}
            required
            disabled={tenants.loading}
          />
          <FormikSelectField
            name="scope"
            label="Scope"
            options={SCOPE_OPTIONS}
            required
            helperText="Operations only excludes the client's user & role administration and the mandate itself"
          />
        </>
      ),
    },
    {
      label: 'Consent & term',
      fields: ['starts_on', 'ends_on', 'consent_reference', 'notes'],
      render: (formik) => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikDateField name="starts_on" label="Starts on" required />
          <FormikDateField
            name="ends_on"
            label="Ends on (optional)"
            helperText="Leave empty to run until ended or revoked"
            {...(formik.values.starts_on !== '' ? { minDate: formik.values.starts_on } : {})}
          />
          <FormikTextField
            name="consent_reference"
            label="Consent reference"
            required
            helperText="The client's written consent (letter, signed form or ticket number)"
          />
          <FormikTextField name="notes" label="Notes" multiline minRows={2} />
        </Box>
      ),
    },
  ];

  return (
    <StepperFormDialog<GrantFormValues>
      open
      title="Grant managed-service mandate"
      steps={steps}
      initialValues={initialValues}
      validationSchema={grantSchema}
      submitLabel="Grant mandate"
      renderReview={(v) => (
        <KeyValueGrid
          items={[
            { label: 'Client', value: optionLabel(tenantOptions, v.tenant_id) },
            { label: 'Scope', value: optionLabel(SCOPE_OPTIONS, v.scope) },
            { label: 'From', value: formatDate(v.starts_on) },
            { label: 'Until', value: v.ends_on === '' ? 'Until ended' : formatDate(v.ends_on) },
            { label: 'Consent reference', value: v.consent_reference.trim() },
            { label: 'Notes', value: v.notes.trim() || '—' },
          ]}
        />
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const body = toGrantBody(values);
        onGranted(await mandateService.grant(body, keyFor(body)));
      }}
    />
  );
}
