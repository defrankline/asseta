import { Box } from '@mui/material';
import { useState } from 'react';
import { customerService } from '../../../api/services/customerService';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { ContractDto, CustomerDto, JobSiteDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikDateTimeField } from '../../../components/forms/FormikDateTimeField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { FormikJobSitePicker } from '../shared/lookupPickers';
import { jobSiteLabel } from '../shared/lookups';
import {
  CONTRACT_FIELDS,
  contractFormSchema,
  emptyContractValues,
  PERIOD_FIELDS,
  toContractPayload,
  type ContractFormValues,
} from './contractForm';

interface CreateContractDialogProps {
  customer: CustomerDto;
  timeZone: string;
  onClose: () => void;
  onCreated: (contract: ContractDto) => void;
}

/** Contract → Period → Review. Mount only while open. */
export function CreateContractDialog({
  customer,
  timeZone,
  onClose,
  onCreated,
}: CreateContractDialogProps) {
  const keyFor = useIdempotencyKey();
  const { hasPermission } = useSession();
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const siteLabel = (id: string) => (id === '' ? '—' : site?.id === id ? jobSiteLabel(site) : id);
  const [initialValues] = useState(() => emptyContractValues(new Date().toISOString()));
  const steps: FormStep<ContractFormValues>[] = [
    {
      label: 'Contract',
      fields: CONTRACT_FIELDS,
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikTextField name="contract_number" label="Contract number" required />
          <FormikTextField name="reference" label="Customer reference" />
          {hasPermission(PERMISSIONS.tenantGeofenceRead) && (
            <FormikJobSitePicker
              name="job_site_id"
              label="Default job site"
              helperText="Jobs under this contract default to this site"
              onOptionChange={setSite}
            />
          )}
        </Box>
      ),
    },
    {
      label: 'Period',
      fields: PERIOD_FIELDS,
      render: () => (
        <Box className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormikDateTimeField name="starts_on" label="Starts" timeZone={timeZone} required />
          <FormikDateTimeField
            name="ends_on"
            label="Ends (optional)"
            timeZone={timeZone}
            helperText="Leave empty for an open-ended contract"
          />
          <Box className="sm:col-span-2">
            <FormikTextField name="notes" label="Notes" multiline minRows={2} />
          </Box>
        </Box>
      ),
    },
  ];
  return (
    <StepperFormDialog<ContractFormValues>
      open
      title={`New contract · ${customer.name}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={contractFormSchema}
      submitLabel="Create contract"
      renderReview={(v) => (
        <KeyValueGrid
          columns={2}
          items={[
            { label: 'Customer', value: `${customer.code} · ${customer.name}` },
            { label: 'Contract number', value: v.contract_number.trim() },
            { label: 'Reference', value: v.reference.trim() || '—' },
            { label: 'Default job site', value: siteLabel(v.job_site_id) },
            { label: 'Starts', value: formatInstantIn(v.starts_on, timeZone) },
            {
              label: 'Ends',
              value: v.ends_on === '' ? 'Open-ended' : formatInstantIn(v.ends_on, timeZone),
            },
            { label: 'Notes', value: v.notes.trim() || '—' },
          ]}
        />
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toContractPayload(customer.id, values);
        onCreated(await customerService.createContract(payload, keyFor(payload)));
      }}
    />
  );
}
