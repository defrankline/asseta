import { PERMISSIONS } from '../../../access/permissionCodes';
import type { FieldContractDto, JobDto, MachineDto } from '../../../api/types';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { useSession } from '../../../session/useSession';
import { machineLabel } from '../shared/display';
import { jobOptionLabel, resolveJob, resolveMachine } from '../shared/financeLookups';
import { optionId } from '../shared/lookups';
import {
  resolveFieldMachine,
  searchAllJobs,
  searchFieldContracts,
  searchAllMachines,
  searchFieldMachines,
  searchMyJobs,
  useSeesAllJobs,
} from './fieldLookups';
import { fieldContractLabel } from './requestJob';

interface IdPickerProps<T> {
  name: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  onOptionChange?: (option: T | null) => void;
}

/** Job picker: the caller's own jobs, or every job for job managers. */
export function FormikFieldJobIdPicker(props: IdPickerProps<JobDto>) {
  const all = useSeesAllJobs();
  return (
    <FormikAsyncIdAutocomplete<JobDto>
      {...props}
      fetchOptions={all ? searchAllJobs : searchMyJobs}
      resolveOption={resolveJob}
      getOptionId={optionId}
      getOptionLabel={jobOptionLabel}
      noOptionsText={all ? 'No matching jobs' : 'No matching jobs assigned to you'}
    />
  );
}

/** Machine picker: machines the caller works on, or the machine register for those who read it. */
export function FormikFieldMachineIdPicker(props: IdPickerProps<MachineDto>) {
  const { hasPermission } = useSession();
  const register = hasPermission(PERMISSIONS.tenantMachineRead);
  return (
    <FormikAsyncIdAutocomplete<MachineDto>
      {...props}
      fetchOptions={register ? searchAllMachines : searchFieldMachines}
      resolveOption={register ? resolveMachine : resolveFieldMachine}
      getOptionId={optionId}
      getOptionLabel={machineLabel}
      noOptionsText={register ? 'No matching machines' : 'No matching machines assigned to you'}
    />
  );
}

/** Active customer contract to request a job on ("Customer — contract"). */
export function FormikFieldContractIdPicker(props: IdPickerProps<FieldContractDto>) {
  return (
    <FormikAsyncIdAutocomplete<FieldContractDto>
      {...props}
      fetchOptions={searchFieldContracts}
      getOptionId={optionId}
      getOptionLabel={fieldContractLabel}
      noOptionsText="No matching active contracts"
    />
  );
}
