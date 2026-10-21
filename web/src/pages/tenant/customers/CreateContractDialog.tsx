import { useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { customerService } from '../../../api/services/customerService';
import type { ContractDto, CustomerDto, JobSiteDto } from '../../../api/types';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { jobSiteLabel } from '../shared/lookups';
import {
  contractFormSchema,
  emptyContractValues,
  toContractPayload,
  type ContractFormValues,
} from './contractForm';
import { ContractReview } from './ContractReview';
import { contractSteps } from './contractSteps';

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
  return (
    <StepperFormDialog<ContractFormValues>
      open
      title={`New contract · ${customer.name}`}
      steps={contractSteps({
        timeZone,
        canPickSite: hasPermission(PERMISSIONS.tenantGeofenceRead),
        onSiteChange: setSite,
      })}
      initialValues={initialValues}
      validationSchema={contractFormSchema}
      submitLabel="Create contract"
      renderReview={(v) => (
        <ContractReview
          values={v}
          customerLabel={`${customer.code} · ${customer.name}`}
          siteLabel={siteLabel}
          timeZone={timeZone}
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
