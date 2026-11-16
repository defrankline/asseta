import type { MachineDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { machineLabel } from './display';
import { useMachineSearch } from './useMachineSearch';

interface MachinePickerProps {
  label?: string;
  value: MachineDto | null;
  onChange: (value: MachineDto | null) => void;
  name?: string;
  error?: string | undefined;
  required?: boolean;
  disabled?: boolean;
  onBlur?: () => void;
}

/** Server-backed machine search (asset code / name), debounced; field users search their own machines. */
export function MachinePicker({ label = 'Machine', ...rest }: MachinePickerProps) {
  const fetchOptions = useMachineSearch();
  return (
    <AsyncAutocomplete<MachineDto>
      label={label}
      fetchOptions={fetchOptions}
      getOptionLabel={machineLabel}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      {...rest}
    />
  );
}
