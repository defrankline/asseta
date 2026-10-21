import { Autocomplete, TextField } from '@mui/material';
import { useField } from 'formik';

interface FormikAutocompleteFieldProps {
  name: string;
  label: string;
  /** Static (client-side) option list; use AsyncAutocomplete for server lookups. */
  options: readonly string[];
  required?: boolean;
  helperText?: string;
}

/** Single-select autocomplete over a static string list, bound to a Formik string field. */
export function FormikAutocompleteField({
  name,
  label,
  options,
  required = false,
  helperText,
}: FormikAutocompleteFieldProps) {
  const [field, meta, helpers] = useField<string>(name);
  const showError = meta.touched && meta.error !== undefined;
  return (
    <Autocomplete<string>
      options={options}
      value={field.value === '' ? null : field.value}
      onChange={(_e, next) => {
        void helpers.setValue(next ?? '');
      }}
      onBlur={() => {
        void helpers.setTouched(true);
      }}
      autoHighlight
      renderInput={(params) => (
        <TextField
          {...params}
          name={name}
          label={label}
          required={required}
          error={showError}
          helperText={showError ? meta.error : helperText}
        />
      )}
    />
  );
}
