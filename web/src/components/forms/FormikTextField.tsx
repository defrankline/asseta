import { TextField, type TextFieldProps } from '@mui/material';
import { useField } from 'formik';

type FormikTextFieldProps = Omit<
  TextFieldProps,
  'name' | 'value' | 'onChange' | 'onBlur' | 'error'
> & {
  name: string;
};

/** MUI TextField bound to a Formik field; shows the error once touched. */
export function FormikTextField({ name, helperText, ...rest }: FormikTextFieldProps) {
  const [field, meta] = useField<string>(name);
  const showError = meta.touched && meta.error !== undefined;
  return (
    <TextField
      {...rest}
      {...field}
      id={rest.id ?? name}
      value={field.value}
      error={showError}
      helperText={showError ? meta.error : helperText}
      fullWidth={rest.fullWidth ?? true}
    />
  );
}
