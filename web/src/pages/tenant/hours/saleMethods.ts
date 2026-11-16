import type { SalePaymentMethod } from '../../../api/hoursTypes';
import { HOURS_ERROR_HINTS } from './hoursDisplay';

/** Order payment line methods in plain words (Credit is paid later on its invoice). */
export const SALE_METHOD_LABELS: Readonly<Record<SalePaymentMethod, string>> = {
  CASH: 'Cash',
  BANK: 'Bank transfer',
  MOBILE_MONEY: 'Mobile money',
  CREDIT: 'Credit',
};

type Choice = 'CASH' | 'CASH_CREDIT' | 'ALL' | 'ALL_CREDIT';

const options = (methods: readonly SalePaymentMethod[]) =>
  methods.map((value) => ({ value, label: SALE_METHOD_LABELS[value] }));

/** The methods one line may use: cash always; bank/mobile when allowed; credit when offered. */
export const SALE_METHOD_CHOICES: Readonly<
  Record<Choice, readonly { value: SalePaymentMethod; label: string }[]>
> = {
  CASH: options(['CASH']),
  CASH_CREDIT: options(['CASH', 'CREDIT']),
  ALL: options(['CASH', 'BANK', 'MOBILE_MONEY']),
  ALL_CREDIT: options(['CASH', 'BANK', 'MOBILE_MONEY', 'CREDIT']),
};

export function saleMethodChoice(nonCashAllowed: boolean, creditOffered: boolean): Choice {
  if (nonCashAllowed) return creditOffered ? 'ALL_CREDIT' : 'ALL';
  return creditOffered ? 'CASH_CREDIT' : 'CASH';
}

/** Refusals of a sale in plain words. */
export const SALE_ERROR_HINTS: Readonly<Record<string, string>> = {
  ...HOURS_ERROR_HINTS,
  CREDIT_SALES_NOT_ALLOWED:
    'Your company does not let field staff sell on credit. Take the money now, or ask the office.',
  CREDIT_NOT_ALLOWED: 'Your company has switched credit off. Take the money now.',
  WALK_IN_NO_CREDIT: 'Walk-in customers pay now; credit is for registered customers.',
  PAYMENTS_EXCEED_TOTAL: 'The payments add up to more than the total. Lower an amount.',
};
