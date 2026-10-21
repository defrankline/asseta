import { Autocomplete, CircularProgress, TextField } from '@mui/material';
import { useEffect, useState } from 'react';
import { isCancelled } from '../../api/ApiError';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';

export interface AsyncAutocompleteProps<T> {
  label: string;
  value: T | null;
  onChange: (value: T | null) => void;
  /** Server lookup; receives the debounced input text. */
  fetchOptions: (query: string, signal: AbortSignal) => Promise<T[]>;
  getOptionLabel: (option: T) => string;
  isOptionEqualToValue: (option: T, value: T) => boolean;
  debounceMs?: number;
  /** Minimum characters before querying (0 queries on open). */
  minChars?: number;
  name?: string;
  error?: string | undefined;
  helperText?: string;
  disabled?: boolean;
  required?: boolean;
  onBlur?: () => void;
}

interface LookupResult<T> {
  query: string | null;
  options: readonly T[];
  error: string | null;
}

/** Debounced, typed, server-backed single-select autocomplete. */
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
  disabled = false,
  required = false,
  onBlur,
}: AsyncAutocompleteProps<T>) {
  const [open, setOpen] = useState(false);
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
      onInputChange={(_e, text) => {
        setInput(text);
      }}
      options={options}
      loading={loading}
      disabled={disabled}
      filterOptions={(x) => x}
      getOptionLabel={getOptionLabel}
      isOptionEqualToValue={isOptionEqualToValue}
      renderInput={(params) => (
        <TextField
          {...params}
          name={name}
          label={label}
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
