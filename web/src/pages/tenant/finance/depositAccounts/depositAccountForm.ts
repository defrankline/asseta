import { mixed, object, string, type ObjectSchema } from 'yup';
import type {
  DepositAccountDto,
  DepositAccountIn,
  DepositAccountType,
  DepositAccountUpdateIn,
} from '../../../../api/custodyTypes';
import { DEPOSIT_ACCOUNT_TYPES } from '../../../../api/services/depositAccountService';
import type { Option } from '../../shared/display';
import { optionalText, orNull } from '../../shared/formRules';

export const DEPOSIT_ACCOUNT_TYPE_OPTIONS: readonly Option<DepositAccountType>[] = [
  { value: 'BANK', label: 'Bank account' },
  { value: 'MOBILE_MONEY', label: 'Mobile-money wallet' },
  { value: 'CASH_OFFICE', label: 'Cash office' },
];

export const DEPOSIT_ACCOUNT_TYPE_LABELS: Readonly<Record<DepositAccountType, string>> = {
  BANK: 'Bank account',
  MOBILE_MONEY: 'Mobile-money wallet',
  CASH_OFFICE: 'Cash office',
};

/** "CRDB main · •••• 4821 · TZS": what a picker and a remittance show for an account. */
export function depositAccountLabel(a: {
  name: string;
  account_number_masked: string | null;
  currency: string;
}): string {
  return [a.name, a.account_number_masked, a.currency].filter((p) => p !== null).join(' · ');
}

export interface DepositAccountValues {
  name: string;
  account_type: DepositAccountType;
  institution: string;
  /** Create: the full number (stored masked). Edit: '' keeps the stored masked number. */
  account_number: string;
  currency: string;
  note: string;
}

export const depositAccountSchema: ObjectSchema<DepositAccountValues> = object({
  name: string()
    .trim()
    .required('Name is required')
    .min(2, 'At least 2 characters')
    .max(120, 'At most 120 characters'),
  account_type: mixed<DepositAccountType>()
    .oneOf(DEPOSIT_ACCOUNT_TYPES, 'Choose the account type')
    .required('Choose the account type'),
  institution: optionalText('Bank or operator', 120),
  account_number: optionalText('Account number', 60),
  currency: string().ensure(),
  note: optionalText('Note', 1000),
});

export const EMPTY_DEPOSIT_ACCOUNT: DepositAccountValues = {
  name: '',
  account_type: 'BANK',
  institution: '',
  account_number: '',
  currency: '',
  note: '',
};

export function valuesFromDepositAccount(a: DepositAccountDto): DepositAccountValues {
  return {
    name: a.name,
    account_type: a.account_type,
    institution: a.institution ?? '',
    account_number: '',
    currency: a.currency,
    note: a.note ?? '',
  };
}

export function toDepositAccountPayload(v: DepositAccountValues): DepositAccountIn {
  return {
    name: v.name.trim(),
    account_type: v.account_type,
    institution: orNull(v.institution),
    account_number: orNull(v.account_number),
    currency: orNull(v.currency),
    note: orNull(v.note),
  };
}

/**
 * PATCH body (null = unchanged): '' clears the institution or note; the number is sent only when a
 * new one was typed (the stored one is masked).
 */
export function toDepositAccountUpdate(
  v: DepositAccountValues,
  version: number,
): DepositAccountUpdateIn {
  return {
    name: v.name.trim(),
    account_type: v.account_type,
    institution: v.institution.trim(),
    account_number: orNull(v.account_number),
    currency: orNull(v.currency),
    note: v.note.trim(),
    version,
  };
}

export const DEPOSIT_ACCOUNT_ERROR_HINTS: Readonly<Record<string, string>> = {
  DUPLICATE_DEPOSIT_ACCOUNT: 'Another deposit account already has this name.',
  DEPOSIT_ACCOUNT_NOT_FOUND: 'This deposit account no longer exists. Reload the list.',
  CURRENCY_NOT_CONFIGURED: 'Choose a configured currency.',
};

export const DEPOSIT_ACCOUNT_DEACTIVATE_CONSEQUENCES =
  'New remittances can no longer name this account. Remittances already recorded keep it.';
