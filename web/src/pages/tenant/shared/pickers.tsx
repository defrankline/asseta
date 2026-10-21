import { useCallback } from 'react';
import { customerService } from '../../../api/services/customerService';
import { machineService } from '../../../api/services/machineService';
import { staffService } from '../../../api/services/staffService';
import type { ContractDto, MachineDto, StaffDto } from '../../../api/types';
import { FormikAsyncAutocomplete } from '../../../components/forms/FormikAsyncAutocomplete';
import { machineLabel } from './display';
import { contractLabel } from './jobDisplay';

interface PickerProps {
  name: string;
  label: string;
  required?: boolean;
  helperText?: string;
}

const sameId = (a: { id: string }, b: { id: string }) => a.id === b.id;

/** Contract search (by number) bound to a Formik field. */
export function FormikContractPicker(props: PickerProps) {
  const fetchOptions = useCallback(
    async (q: string, signal: AbortSignal) =>
      (await customerService.listContracts({ page: 1, page_size: 20, q }, signal)).items,
    [],
  );
  return (
    <FormikAsyncAutocomplete<ContractDto>
      {...props}
      fetchOptions={fetchOptions}
      getOptionLabel={contractLabel}
      isOptionEqualToValue={sameId}
    />
  );
}

/** Machine search (asset code / name) bound to a Formik field. */
export function FormikMachinePicker(props: PickerProps) {
  const fetchOptions = useCallback(
    async (q: string, signal: AbortSignal) =>
      (await machineService.list({ page: 1, page_size: 20, q }, signal)).items,
    [],
  );
  return (
    <FormikAsyncAutocomplete<MachineDto>
      {...props}
      fetchOptions={fetchOptions}
      getOptionLabel={machineLabel}
      isOptionEqualToValue={sameId}
    />
  );
}

/** Supervisor search among staff bound to a Formik field. */
export function FormikSupervisorPicker(props: PickerProps) {
  const fetchOptions = useCallback(
    async (q: string, signal: AbortSignal) =>
      (
        await staffService.list(
          { page: 1, page_size: 20, q, filters: { kind: 'SUPERVISOR' } },
          signal,
        )
      ).items,
    [],
  );
  return (
    <FormikAsyncAutocomplete<StaffDto>
      {...props}
      fetchOptions={fetchOptions}
      getOptionLabel={(s) => s.full_name}
      isOptionEqualToValue={sameId}
    />
  );
}
