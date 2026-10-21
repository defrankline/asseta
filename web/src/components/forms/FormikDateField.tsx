import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs from 'dayjs';
import { useField } from 'formik';

interface FormikDateFieldProps {
  name: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  /** ISO date (YYYY-MM-DD) lower bound. */
  minDate?: string;
  maxDate?: string;
}

/** MUI X DatePicker bound to a Formik ISO calendar-date string (YYYY-MM-DD, '' when empty). */
export function FormikDateField({
  name,
  label,
  required = false,
  disabled = false,
  helperText,
  minDate,
  maxDate,
}: FormikDateFieldProps) {
  const [field, meta, helpers] = useField<string>(name);
  const showError = meta.touched && meta.error !== undefined;
  const value = field.value === '' ? null : dayjs(field.value);
  return (
    <DatePicker
      label={label}
      value={value !== null && value.isValid() ? value : null}
      format="YYYY-MM-DD"
      disabled={disabled}
      {...(minDate !== undefined ? { minDate: dayjs(minDate) } : {})}
      {...(maxDate !== undefined ? { maxDate: dayjs(maxDate) } : {})}
      onChange={(next) => {
        void helpers.setValue(next !== null && next.isValid() ? next.format('YYYY-MM-DD') : '');
      }}
      slotProps={{
        textField: {
          name,
          id: name,
          required,
          fullWidth: true,
          error: showError,
          helperText: showError ? meta.error : helperText,
          onBlur: () => {
            void helpers.setTouched(true);
          },
        },
      }}
    />
  );
}
