import { useCallback } from 'react';
import type { DepositAccountDto, DepositAccountType } from '../../../../api/custodyTypes';
import { depositAccountService } from '../../../../api/services/depositAccountService';
import { FormikAsyncIdAutocomplete } from '../../../../components/forms/FormikAsyncIdAutocomplete';
import { DEPOSIT_ACCOUNT_TYPE_LABELS, depositAccountLabel } from './depositAccountForm';

interface DepositAccountPickerProps {
  name: string;
  label: string;
  /** Only accounts of this type (follows the remittance method); undefined = any type. */
  accountType?: DepositAccountType | undefined;
  /** Only accounts in this currency ('' = any). */
  currency?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  onOptionChange?: (option: DepositAccountDto | null) => void;
}

const optionLabel = (a: DepositAccountDto) =>
  `${depositAccountLabel(a)} (${DEPOSIT_ACCOUNT_TYPE_LABELS[a.account_type]})`;

/** Active company deposit accounts (server search), bound to a Formik id field. */
export function FormikDepositAccountIdPicker({
  accountType,
  currency = '',
  ...props
}: DepositAccountPickerProps) {
  const fetchOptions = useCallback(
    async (q: string, signal: AbortSignal) => {
      const page = await depositAccountService.list(
        { page: 1, page_size: 20, q, filters: { account_type: accountType } },
        signal,
      );
      return page.items.filter((a) => a.is_active && (currency === '' || a.currency === currency));
    },
    [accountType, currency],
  );
  const resolveOption = useCallback(
    (id: string, signal: AbortSignal) => depositAccountService.get(id, signal),
    [],
  );
  return (
    <FormikAsyncIdAutocomplete<DepositAccountDto>
      {...props}
      fetchOptions={fetchOptions}
      resolveOption={resolveOption}
      getOptionId={(a) => a.id}
      getOptionLabel={optionLabel}
      noOptionsText="No active deposit account matches"
    />
  );
}
