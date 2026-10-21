import { useCallback } from 'react';
import { machineService } from '../../../api/services/machineService';
import type { MachineDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { machineLabel } from './display';

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

/** Server-backed machine search (asset code / name), debounced. */
export function MachinePicker({ label = 'Machine', ...rest }: MachinePickerProps) {
  const fetchOptions = useCallback(
    async (q: string, signal: AbortSignal) =>
      (await machineService.list({ page: 1, page_size: 20, q }, signal)).items,
    [],
  );
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
