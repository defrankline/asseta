import { Stack } from '@mui/material';
import { useState } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { withErrorCode } from '../../../api/lifecycle';
import { customerService } from '../../../api/services/customerService';
import type { ContractDto, CustomerDto, JobSiteDto } from '../../../api/types';
import { StepperFormDialog } from '../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useSession } from '../../../session/useSession';
import { jobSiteLabel } from '../shared/lookups';
import {
  contractFormSchema,
  toContractUpdatePayload,
  valuesFromContract,
  type ContractFormValues,
} from './contractForm';
import { ContractReview } from './ContractReview';
import { contractSteps } from './contractSteps';
import { CONTRACT_ERROR_HINTS } from './customerLifecycle';

interface EditContractDialogProps {
  contract: ContractDto;
  customer: CustomerDto;
  timeZone: string;
  onClose: () => void;
  onSaved: (contract: ContractDto) => void;
  onReload: () => void;
}

/** Edit a contract that is not closed (the customer is fixed). Mount only while open. */
export function EditContractDialog({
  contract,
  customer,
  timeZone,
  onClose,
  onSaved,
  onReload,
}: EditContractDialogProps) {
  const keyFor = useIdempotencyKey();
  const { hasPermission } = useSession();
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const siteLabel = (id: string) => (id === '' ? '—' : site?.id === id ? jobSiteLabel(site) : id);
  const [initialValues] = useState(() => valuesFromContract(contract));
  const { stale, guard } = useStaleVersion();
  return (
    <StepperFormDialog<ContractFormValues>
      open
      title={`Edit contract ${contract.contract_number}`}
      steps={contractSteps({
        timeZone,
        canPickSite: hasPermission(PERMISSIONS.tenantGeofenceRead),
        onSiteChange: setSite,
      })}
      initialValues={initialValues}
      validationSchema={contractFormSchema}
      submitLabel="Save changes"
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
          <ContractReview
            values={v}
            customerLabel={`${customer.code} · ${customer.name}`}
            siteLabel={siteLabel}
            timeZone={timeZone}
          />
        </Stack>
      )}
      onClose={onClose}
      onSubmit={async (values) => {
        const payload = toContractUpdatePayload(values, contract.version);
        try {
          onSaved(
            await guard(() =>
              customerService.updateContract(contract.id, payload, keyFor(payload)),
            ),
          );
        } catch (err) {
          throw withErrorCode(err, CONTRACT_ERROR_HINTS);
        }
      }}
    />
  );
}
