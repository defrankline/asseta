import { useField } from 'formik';
import { AsyncAutocomplete } from '../data/AsyncAutocomplete';

interface FormikAsyncAutocompleteProps<T> {
  /** Formik field holding the selected option object (or null). */
  name: string;
  label: string;
  fetchOptions: (query: string, signal: AbortSignal) => Promise<T[]>;
  getOptionLabel: (option: T) => string;
  isOptionEqualToValue: (option: T, value: T) => boolean;
  required?: boolean;
  helperText?: string;
}

/** Server-backed async autocomplete bound to a Formik object field. */
export function FormikAsyncAutocomplete<T>({ name, ...rest }: FormikAsyncAutocompleteProps<T>) {
  const [field, meta, helpers] = useField<T | null>(name);
  const showError = meta.touched && typeof meta.error === 'string';
  return (
    <AsyncAutocomplete<T>
      {...rest}
      name={name}
      value={field.value}
      onChange={(v) => {
        void helpers.setValue(v);
      }}
      onBlur={() => {
        void helpers.setTouched(true);
      }}
      error={showError ? meta.error : undefined}
    />
  );
}
