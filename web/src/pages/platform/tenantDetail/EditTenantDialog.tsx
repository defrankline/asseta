import { Stack } from '@mui/material';
import { useState } from 'react';
import { withErrorCode } from '../../../api/lifecycle';
import { tenantService } from '../../../api/services/tenantService';
import type { TenantDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import {
  COMPANY_EDIT_FIELDS,
  CONTACT_EDIT_FIELDS,
  registrationLocked,
  TENANT_ERROR_HINTS,
  tenantEditSchema,
  toTenantUpdate,
  valuesFromTenant,
  type TenantEditValues,
} from './tenantEditForm';

interface EditTenantDialogProps {
  tenant: TenantDto;
  onClose: () => void;
  onSaved: (tenant: TenantDto) => void;
  /** The server reported STALE_VERSION and the user chose Reload. */
  onReload: () => void;
}

const dash = (v: string) => (v.trim() === '' ? '—' : v.trim());

/** Edit a tenant's company details with the `version` that was read. Mount only while open. */
export function EditTenantDialog({ tenant, onClose, onSaved, onReload }: EditTenantDialogProps) {
  const [initialValues] = useState(() => valuesFromTenant(tenant));
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const locked = registrationLocked(tenant);

  const steps: FormStep<TenantEditValues>[] = [
    {
      label: 'Company',
      fields: COMPANY_EDIT_FIELDS,
      render: () => (
        <>
          <FormikTextField name="legal_name" label="Legal name" required />
          <FormikTextField name="display_name" label="Display name" required />
          <FormikTextField
            name="registration_number"
            label="Registration number"
            disabled={locked}
            {...(locked ? { helperText: 'Fixed once the company is verified.' } : {})}
          />
        </>
      ),
    },
    {
      label: 'Contact',
      fields: CONTACT_EDIT_FIELDS,
      render: () => (
        <>
          <FormikTextField name="contact_name" label="Contact name" required />
          <FormikTextField name="contact_email" label="Contact email" type="email" required />
          <FormikTextField name="contact_phone" label="Contact phone" />
        </>
      ),
    },
  ];

  return (
    <StepperFormDialog<TenantEditValues>
      open
      title={`Edit ${tenant.display_name}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={tenantEditSchema}
      submitLabel="Save changes"
      onClose={onClose}
      renderReview={(v) => (
        <Stack spacing={2}>
          {stale && (
            <StaleVersionAlert
              onReload={() => {
                onReload();
                onClose();
              }}
            />
          )}
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Legal name', value: dash(v.legal_name) },
              { label: 'Display name', value: dash(v.display_name) },
              { label: 'Registration no.', value: dash(v.registration_number) },
              { label: 'Contact name', value: dash(v.contact_name) },
              { label: 'Contact email', value: dash(v.contact_email) },
              { label: 'Contact phone', value: dash(v.contact_phone) },
            ]}
          />
        </Stack>
      )}
      onSubmit={async (v) => {
        const body = toTenantUpdate(
          locked ? { ...v, registration_number: initialValues.registration_number } : v,
          tenant.version,
        );
        try {
          onSaved(await guard(() => tenantService.update(tenant.id, body, keyFor(body))));
        } catch (err) {
          throw withErrorCode(err, TENANT_ERROR_HINTS);
        }
      }}
    />
  );
}
