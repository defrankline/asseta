import { useField } from 'formik';
import { DateTimeField } from './DateTimeField';

interface FormikDateTimeFieldProps {
  name: string;
  label: string;
  /** IANA zone for display/entry; the Formik value is always a UTC ISO instant ('' when empty). */
  timeZone: string;
  required?: boolean;
  helperText?: string;
  disabled?: boolean;
}

/** MUI X DateTimePicker bound to a Formik UTC ISO instant string. */
export function FormikDateTimeField({
  name,
  label,
  timeZone,
  required = false,
  helperText,
  disabled = false,
}: FormikDateTimeFieldProps) {
  const [field, meta, helpers] = useField<string>(name);
  const showError = meta.touched && meta.error !== undefined;
  return (
    <DateTimeField
      name={name}
      label={label}
      value={field.value === '' ? null : field.value}
      onChange={(v) => {
        void helpers.setValue(v ?? '');
      }}
      onBlur={() => {
        void helpers.setTouched(true);
      }}
      timezone={timeZone}
      required={required}
      disabled={disabled}
      error={showError ? meta.error : undefined}
      {...(helperText !== undefined ? { helperText } : {})}
    />
  );
}
