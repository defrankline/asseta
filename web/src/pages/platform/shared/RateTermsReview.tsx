import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { formatMoney, formatPercent, isDecimalString } from '../../../utils/money';
import {
  ADD_POLICY_OPTIONS,
  CADENCE_OPTIONS,
  optionLabel,
  REMOVE_POLICY_OPTIONS,
  ROUNDING_OPTIONS,
} from './billingDisplay';
import type { RateTermsValues } from './rateTerms';

/** Read-only summary of rate terms for Review steps. */
export function RateTermsReview({ values }: { values: RateTermsValues }) {
  const price = isDecimalString(values.unit_price)
    ? formatMoney(values.unit_price, values.currency)
    : values.unit_price;
  return (
    <KeyValueGrid
      items={[
        { label: 'Currency', value: values.currency },
        { label: 'Cadence', value: optionLabel(CADENCE_OPTIONS, values.cadence) },
        { label: 'Unit price per asset per period', value: price },
        { label: 'Minimum billable assets', value: values.minimum_billable_assets },
        { label: 'Discount', value: formatPercent(values.discount_percent) },
        {
          label: 'Tax',
          value:
            values.tax_name.trim() === ''
              ? formatPercent(values.tax_rate_percent)
              : `${values.tax_name.trim()} ${formatPercent(values.tax_rate_percent)}`,
        },
        { label: 'Mid-cycle add', value: optionLabel(ADD_POLICY_OPTIONS, values.mid_cycle_add) },
        {
          label: 'Mid-cycle removal',
          value: optionLabel(REMOVE_POLICY_OPTIONS, values.mid_cycle_remove),
        },
        { label: 'Rounding', value: optionLabel(ROUNDING_OPTIONS, values.rounding_mode) },
      ]}
    />
  );
}
