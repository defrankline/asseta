import { Autocomplete, CircularProgress, TextField } from '@mui/material';
import { useEffect, useState } from 'react';
import { isCancelled } from '../../api/ApiError';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';

/** Default number of options requested per lookup (one server page). */
export const LOOKUP_PAGE_SIZE = 20;

export interface AsyncAutocompleteProps<T> {
  label: string;
  value: T | null;
  onChange: (value: T | null) => void;
  /**
   * Server lookup; receives the debounced, trimmed input text. Pass it to the API as the search
   * parameter (never fetch everything and filter in the browser).
   */
  fetchOptions: (query: string, signal: AbortSignal) => Promise<T[]>;
  getOptionLabel: (option: T) => string;
  isOptionEqualToValue: (option: T, value: T) => boolean;
  debounceMs?: number;
  /** Minimum characters before querying (0 queries on open). */
  minChars?: number;
  name?: string;
  error?: string | undefined;
  helperText?: string;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  size?: 'small' | 'medium';
  /** Shown when the server returned no match. */
  noOptionsText?: string;
  onBlur?: () => void;
}

interface LookupResult<T> {
  query: string | null;
  options: readonly T[];
  error: string | null;
}

/**
 * Debounced, typed, server-backed single-select autocomplete. Use it (or a Formik wrapper) for
 * every option list that comes from the backend; static enums may use a select.
 */
export function AsyncAutocomplete<T>({
  label,
  value,
  onChange,
  fetchOptions,
  getOptionLabel,
  isOptionEqualToValue,
  debounceMs = 300,
  minChars = 0,
  name,
  error,
  helperText,
  placeholder,
  disabled = false,
  required = false,
  size,
  noOptionsText = 'No matches',
  onBlur,
}: AsyncAutocompleteProps<T>) {
  const [open, setOpen] = useState(false);
  /** Text typed by the user; the selected option's label (a "reset") is not a search. */
  const [input, setInput] = useState('');
  const [result, setResult] = useState<LookupResult<T>>({ query: null, options: [], error: null });
  const query = useDebouncedValue(input.trim(), debounceMs);
  const shouldFetch = open && query.length >= minChars;

  useEffect(() => {
    if (!shouldFetch) return undefined;
    const controller = new AbortController();
    fetchOptions(query, controller.signal)
      .then((options) => {
        if (!controller.signal.aborted) setResult({ query, options, error: null });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isCancelled(err)) return;
        const message = err instanceof Error ? err.message : 'Could not load options.';
        setResult({ query, options: [], error: message });
      });
    return () => {
      controller.abort();
    };
  }, [shouldFetch, query, fetchOptions]);

  const loading = shouldFetch && result.query !== query;
  const options = result.options;
  const shownError = error ?? result.error ?? undefined;
  const emptyText =
    query.length < minChars
      ? `Type at least ${String(minChars)} characters to search`
      : result.error !== null
        ? 'Could not load options'
        : noOptionsText;
  return (
    <Autocomplete<T>
      open={open}
      onOpen={() => {
        setOpen(true);
      }}
      onClose={() => {
        setOpen(false);
      }}
      value={value}
      onChange={(_e, next) => {
        onChange(next);
      }}
      onInputChange={(_e, text, reason) => {
        setInput(reason === 'input' ? text : '');
      }}
      options={options}
      loading={loading}
      loadingText="Searching…"
      noOptionsText={emptyText}
      disabled={disabled}
      size={size}
      filterOptions={(x) => x}
      getOptionLabel={getOptionLabel}
      isOptionEqualToValue={isOptionEqualToValue}
      renderInput={(params) => (
        <TextField
          {...params}
          name={name}
          label={label}
          placeholder={placeholder}
          required={required}
          onBlur={onBlur}
          error={shownError !== undefined}
          helperText={shownError ?? helperText}
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps.input,
              endAdornment: (
                <>
                  {loading ? <CircularProgress color="inherit" size={18} /> : null}
                  {params.slotProps.input.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
    />
  );
}
