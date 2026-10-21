import { Box, Button, Stack } from '@mui/material';
import type { FormikProps } from 'formik';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { OWNERSHIP_OPTIONS } from '../shared/display';
import { FormikAreaPicker, FormikCategoryPicker } from '../shared/lookupPickers';
import type { MachineFormValues } from './machineForm';
import { METER_DP_OPTIONS } from './machineForm';
import { EDIT_STATUS_OPTIONS } from './machineLifecycle';
import type { MachineLookups } from './useMachineLookups';

const grid = 'grid grid-cols-1 gap-4 sm:grid-cols-2';

export function IdentityFields({ mode }: { mode: 'create' | 'edit' }) {
  return (
    <Box className={grid}>
      {mode === 'create' && <FormikTextField name="asset_code" label="Asset code" required />}
      <FormikTextField name="name" label="Name" required />
      <FormikTextField name="manufacturer" label="Manufacturer" />
      <FormikTextField name="model" label="Model" />
      <FormikTextField name="serial_number" label="Serial number" />
      <FormikTextField
        name="year_of_manufacture"
        label="Year of manufacture"
        slotProps={{ htmlInput: { inputMode: 'numeric' } }}
      />
      {mode === 'edit' && (
        <FormikSelectField name="status" label="Status" options={EDIT_STATUS_OPTIONS} required />
      )}
    </Box>
  );
}

interface ClassificationFieldsProps {
  formik: FormikProps<MachineFormValues>;
  lookups: MachineLookups;
  canCreateLookups: boolean;
}

export function ClassificationFields({
  formik,
  lookups,
  canCreateLookups,
}: ClassificationFieldsProps) {
  return (
    <Stack spacing={2}>
      <Box className="flex items-start gap-2">
        <Box className="grow">
          <FormikCategoryPicker
            name="category_id"
            label="Category"
            onOptionChange={lookups.setCategory}
          />
        </Box>
        {canCreateLookups && (
          <Button
            className="mt-2 shrink-0"
            onClick={() => {
              lookups.requestNew('category', (id) => {
                void formik.setFieldValue('category_id', id);
              });
            }}
          >
            New category
          </Button>
        )}
      </Box>
      <Box className="flex items-start gap-2">
        <Box className="grow">
          <FormikAreaPicker
            name="operating_area_id"
            label="Operating area"
            onOptionChange={lookups.setArea}
          />
        </Box>
        {canCreateLookups && (
          <Button
            className="mt-2 shrink-0"
            onClick={() => {
              lookups.requestNew('area', (id) => {
                void formik.setFieldValue('operating_area_id', id);
              });
            }}
          >
            New area
          </Button>
        )}
      </Box>
      <FormikSelectField name="ownership" label="Ownership" options={OWNERSHIP_OPTIONS} required />
    </Stack>
  );
}

export function MeteringFields() {
  return (
    <Box className={grid}>
      <FormikSelectField
        name="meter_decimal_places"
        label="Hour-meter decimal places"
        options={METER_DP_OPTIONS}
        required
        helperText="Precision used when supervisors capture meter readings"
      />
      <span />
      <FormikTextField
        name="capacity_value"
        label="Capacity"
        slotProps={{ htmlInput: { inputMode: 'decimal' } }}
      />
      <FormikTextField name="capacity_unit" label="Capacity unit" helperText="e.g. t, m³, kW" />
    </Box>
  );
}
