import { CAPABILITY, useCapabilityEnabled } from '../../../../access/capabilities';
import { FormikSelectField } from '../../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { FormikDepositAccountIdPicker } from '../depositAccounts/depositAccountPickers';
import { PETTY_METHOD_OPTIONS } from './pettyCashForms';

/** Company account and method of a money movement (the account only while deposit accounts are on). */
export function AccountFields({
  currency,
  accountLabel,
}: {
  currency: string;
  accountLabel: string;
}) {
  const accountsOn = useCapabilityEnabled(CAPABILITY.depositAccounts);
  return (
    <>
      {accountsOn && (
        <FormikDepositAccountIdPicker
          name="deposit_account_id"
          label={accountLabel}
          currency={currency}
          helperText={`Only active ${currency} accounts are listed.`}
        />
      )}
      <FormikSelectField name="method" label="How (optional)" options={PETTY_METHOD_OPTIONS} />
      <FormikTextField name="reference" label="Reference (optional)" />
    </>
  );
}
