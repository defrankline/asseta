import { Autocomplete, CircularProgress, TextField } from '@mui/material';
import { useEffect, useState } from 'react';
import { isCancelled } from '../../api/ApiError';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';

export interface AsyncMultiAutocompleteProps<T> {
  label: string;
  value: readonly T[];
  onChange: (value: T[]) => void;
  /** Server lookup; receives the debounced input text. */
  fetchOptions: (query: string, signal: AbortSignal) => Promise<T[]>;
  getOptionLabel: (option: T) => string;
  isOptionEqualToValue: (option: T, value: T) => boolean;
  debounceMs?: number;
  error?: string | undefined;
  helperText?: string;
  disabled?: boolean;
  onBlur?: () => void;
}

interface LookupResult<T> {
  query: string | null;
  options: readonly T[];
  error: string | null;
}

/** Debounced, typed, server-backed multi-select autocomplete (chips). */
export function AsyncMultiAutocomplete<T>({
  label,
  value,
  onChange,
  fetchOptions,
  getOptionLabel,
  isOptionEqualToValue,
  debounceMs = 300,
  error,
  helperText,
  disabled = false,
  onBlur,
}: AsyncMultiAutocompleteProps<T>) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [result, setResult] = useState<LookupResult<T>>({ query: null, options: [], error: null });
  const query = useDebouncedValue(input.trim(), debounceMs);

  useEffect(() => {
    if (!open) return undefined;
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
  }, [open, query, fetchOptions]);

  const loading = open && result.query !== query;
  const shownError = error ?? result.error ?? undefined;
  return (
    <Autocomplete<T, true>
      multiple
      open={open}
      onOpen={() => {
        setOpen(true);
      }}
      onClose={() => {
        setOpen(false);
      }}
      value={[...value]}
      onChange={(_e, next) => {
        onChange(next);
      }}
      onInputChange={(_e, text, reason) => {
        if (reason !== 'reset') setInput(text);
      }}
      options={[...result.options]}
      loading={loading}
      disabled={disabled}
      filterOptions={(x) => x}
      filterSelectedOptions
      getOptionLabel={getOptionLabel}
      isOptionEqualToValue={isOptionEqualToValue}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
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
