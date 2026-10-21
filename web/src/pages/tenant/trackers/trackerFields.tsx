import { Checkbox, FormControlLabel, Switch } from '@mui/material';
import { useField } from 'formik';
import { DateTimeField } from '../../../components/forms/DateTimeField';

/** DateTimeField bound to a Formik UTC-ISO string field ('' when empty). */
export function FormikDateTimeField({
  name,
  label,
  timeZone,
  required = false,
}: {
  name: string;
  label: string;
  timeZone: string;
  required?: boolean;
}) {
  const [field, meta, helpers] = useField<string>(name);
  const showError = meta.touched && meta.error !== undefined;
  return (
    <DateTimeField
      name={name}
      label={label}
      timezone={timeZone}
      required={required}
      value={field.value === '' ? null : field.value}
      error={showError ? meta.error : undefined}
      onChange={(v) => {
        void helpers.setValue(v ?? '');
      }}
      onBlur={() => {
        void helpers.setTouched(true);
      }}
    />
  );
}

/** Boolean Formik field as a switch or checkbox. */
export function FormikToggle({
  name,
  label,
  variant = 'switch',
}: {
  name: string;
  label: string;
  variant?: 'switch' | 'checkbox';
}) {
  const [field, , helpers] = useField<boolean>(name);
  const control =
    variant === 'switch' ? (
      <Switch
        checked={field.value}
        onChange={(e) => void helpers.setValue(e.target.checked)}
        name={name}
      />
    ) : (
      <Checkbox
        checked={field.value}
        onChange={(e) => void helpers.setValue(e.target.checked)}
        name={name}
      />
    );
  return <FormControlLabel control={control} label={label} />;
}
