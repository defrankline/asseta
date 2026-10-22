import type { SelectOption } from '../../../components/forms/FormikSelectField';
import { SUPPORTED_CURRENCIES } from '../../../utils/money';

/** Invoice currency; empty = the tenant's subscription currency (server default). */
export const INVOICE_CURRENCY_OPTIONS: readonly SelectOption[] = [
  { value: '', label: "Tenant's currency (default)" },
  ...SUPPORTED_CURRENCIES.map((c) => ({ value: c, label: c })),
];
