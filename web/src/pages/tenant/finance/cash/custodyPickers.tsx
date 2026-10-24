import { useCallback } from 'react';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashReasonDto, CashReasonKind, CustodianDto } from '../../../../api/custodyTypes';
import { AsyncAutocomplete } from '../../../../components/data/AsyncAutocomplete';
import { FormikAsyncIdAutocomplete } from '../../../../components/forms/FormikAsyncIdAutocomplete';
import { custodianId, custodianLabel, resolveCustodian, searchCustodians } from './custodyHooks';

interface IdPickerProps<T> {
  name: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  onOptionChange?: (option: T | null) => void;
}

/** Custodian search (any staff member who can hold cash; no login needed) bound to a Formik id. */
export function FormikCustodianIdPicker(props: IdPickerProps<CustodianDto>) {
  return (
    <FormikAsyncIdAutocomplete<CustodianDto>
      {...props}
      fetchOptions={searchCustodians}
      resolveOption={resolveCustodian}
      getOptionId={custodianId}
      getOptionLabel={custodianLabel}
    />
  );
}

/** List filter / selector: custodian (server search). */
export function CustodianFilter({
  label = 'Custodian',
  value,
  onChange,
  placeholder = 'All custodians',
}: {
  label?: string;
  value: CustodianDto | null;
  onChange: (value: CustodianDto | null) => void;
  placeholder?: string;
}) {
  return (
    <AsyncAutocomplete<CustodianDto>
      label={label}
      size="small"
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      fetchOptions={searchCustodians}
      getOptionLabel={custodianLabel}
      isOptionEqualToValue={(a, b) => a.staff_member_id === b.staff_member_id}
    />
  );
}

/** Active reasons of one kind from the tenant's list (server search), bound to a Formik id. */
export function FormikCashReasonIdPicker({
  kind,
  ...props
}: IdPickerProps<CashReasonDto> & { kind: CashReasonKind }) {
  const fetchOptions = useCallback(
    async (q: string, signal: AbortSignal) =>
      (await custodyService.reasons({ page: 1, page_size: 20, q, filters: { kind } }, signal))
        .items,
    [kind],
  );
  const resolveOption = useCallback(
    (id: string, signal: AbortSignal) => custodyService.reason(id, signal),
    [],
  );
  return (
    <FormikAsyncIdAutocomplete<CashReasonDto>
      {...props}
      fetchOptions={fetchOptions}
      resolveOption={resolveOption}
      getOptionId={(r) => r.id}
      getOptionLabel={(r) => r.label}
    />
  );
}
