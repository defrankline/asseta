import { PERMISSIONS } from '../../../access/permissionCodes';
import type { MachineDto } from '../../../api/types';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { useSession } from '../../../session/useSession';
import { machineLabel } from '../shared/display';
import { resolveMachine } from '../shared/financeLookups';
import { optionId } from '../shared/lookups';
import { resolveFieldMachine, searchAllMachines, searchFieldMachines } from './fieldLookups';

interface IdPickerProps<T> {
  name: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  onOptionChange?: (option: T | null) => void;
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
