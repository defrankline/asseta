import { MenuItem, TextField, type TextFieldProps } from '@mui/material';
import { useField } from 'formik';

export interface SelectOption {
  value: string;
  label: string;
}

type FormikSelectFieldProps = Omit<
  TextFieldProps,
  'name' | 'value' | 'onChange' | 'onBlur' | 'error' | 'select'
> & {
  name: string;
  options: readonly SelectOption[];
};

/** MUI select bound to a Formik string field. */
export function FormikSelectField({ name, options, helperText, ...rest }: FormikSelectFieldProps) {
  const [field, meta] = useField<string>(name);
  const showError = meta.touched && meta.error !== undefined;
  return (
    <TextField
      {...rest}
      {...field}
      select
      id={rest.id ?? name}
      value={field.value}
      error={showError}
      helperText={showError ? meta.error : helperText}
      fullWidth={rest.fullWidth ?? true}
    >
      {options.map((o) => (
        <MenuItem key={o.value} value={o.value}>
          {o.label}
        </MenuItem>
      ))}
    </TextField>
  );
}
