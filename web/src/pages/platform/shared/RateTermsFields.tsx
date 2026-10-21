import { Box } from '@mui/material';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import {
  ADD_POLICY_OPTIONS,
  CADENCE_OPTIONS,
  CURRENCY_OPTIONS,
  REMOVE_POLICY_OPTIONS,
  ROUNDING_OPTIONS,
} from './billingDisplay';

const grid = 'grid grid-cols-1 gap-4 sm:grid-cols-2';

export function RatePriceFields({ prefix = '' }: { prefix?: string }) {
  return (
    <Box className={grid}>
      <FormikSelectField
        name={`${prefix}currency`}
        label="Currency"
        options={CURRENCY_OPTIONS}
        required
      />
      <FormikSelectField
        name={`${prefix}cadence`}
        label="Billing cadence"
        options={CADENCE_OPTIONS}
        required
      />
      <FormikTextField
        name={`${prefix}unit_price`}
        label="Unit price per asset per period"
        required
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
      />
      <FormikTextField
        name={`${prefix}minimum_billable_assets`}
        label="Minimum billable assets"
        required
        slotProps={{ htmlInput: { inputMode: 'numeric' } }}
        helperText="At least 1"
      />
    </Box>
  );
}

export function RatePolicyFields({ prefix = '' }: { prefix?: string }) {
  return (
    <Box className={grid}>
      <FormikTextField
        name={`${prefix}discount_percent`}
        label="Discount %"
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
      />
      <FormikSelectField
        name={`${prefix}rounding_mode`}
        label="Rounding"
        options={ROUNDING_OPTIONS}
      />
      <FormikTextField
        name={`${prefix}tax_name`}
        label="Tax name"
        helperText="e.g. VAT; optional"
      />
      <FormikTextField
        name={`${prefix}tax_rate_percent`}
        label="Tax %"
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
      />
      <FormikSelectField
        name={`${prefix}mid_cycle_add`}
        label="Mid-cycle asset add"
        options={ADD_POLICY_OPTIONS}
      />
      <FormikSelectField
        name={`${prefix}mid_cycle_remove`}
        label="Mid-cycle asset removal"
        options={REMOVE_POLICY_OPTIONS}
      />
    </Box>
  );
}
