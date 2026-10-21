import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import dayjs, { type Dayjs } from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);
dayjs.extend(timezone);

interface DateTimeFieldProps {
  label: string;
  /** UTC ISO-8601 instant, or null. */
  value: string | null;
  /** Emits a UTC ISO-8601 instant, or null when cleared/invalid. */
  onChange: (value: string | null) => void;
  /** IANA zone used for display/entry (tenant timezone). Defaults to the browser zone. */
  timezone?: string;
  name?: string;
  error?: string | undefined;
  helperText?: string;
  disabled?: boolean;
  required?: boolean;
  minDateTime?: string;
  maxDateTime?: string;
  onBlur?: () => void;
}

function toDayjs(value: string | undefined | null, tz: string): Dayjs | null {
  if (value === undefined || value === null || value === '') return null;
  const d = dayjs.utc(value);
  return d.isValid() ? (tz === 'system' ? d.local() : d.tz(tz)) : null;
}

/** MUI X DateTimePicker that stores UTC instants and displays in the given zone. */
export function DateTimeField({
  label,
  value,
  onChange,
  timezone: tz = 'system',
  name,
  error,
  helperText,
  disabled,
  required,
  minDateTime,
  maxDateTime,
  onBlur,
}: DateTimeFieldProps) {
  const min = toDayjs(minDateTime, tz);
  const max = toDayjs(maxDateTime, tz);
  return (
    <DateTimePicker
      label={label}
      value={toDayjs(value, tz)}
      timezone={tz}
      disabled={disabled ?? false}
      {...(min !== null ? { minDateTime: min } : {})}
      {...(max !== null ? { maxDateTime: max } : {})}
      onChange={(next) => {
        onChange(next !== null && next.isValid() ? next.utc().toISOString() : null);
      }}
      slotProps={{
        textField: {
          name,
          required: required ?? false,
          fullWidth: true,
          error: error !== undefined,
          helperText: error ?? helperText,
          onBlur,
        },
      }}
    />
  );
}
