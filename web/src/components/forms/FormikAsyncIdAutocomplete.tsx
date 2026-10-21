import { useField } from 'formik';
import { useCallback, useEffect, useState } from 'react';
import { isCancelled } from '../../api/ApiError';
import { AsyncAutocomplete } from '../data/AsyncAutocomplete';

export interface FormikAsyncIdAutocompleteProps<T> {
  /** Formik field holding the selected option's id ('' = none). */
  name: string;
  label: string;
  /** Server search; pass the typed text to the API as its search parameter. */
  fetchOptions: (query: string, signal: AbortSignal) => Promise<T[]>;
  getOptionId: (option: T) => string;
  getOptionLabel: (option: T) => string;
  /**
   * Loads the option for an id already in the form (edit forms, or an id set programmatically)
   * so its label is shown. Omit when the field always starts empty.
   */
  resolveOption?: (id: string, signal: AbortSignal) => Promise<T | null>;
  /** Called with the option behind the field (picked, cleared or resolved), e.g. for a review. */
  onOptionChange?: (option: T | null) => void;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  placeholder?: string;
  noOptionsText?: string;
}

/**
 * Server-backed, debounced autocomplete bound to a Formik **id** field: the form value (and the
 * submitted payload) is the id, while the user sees and searches by label.
 */
export function FormikAsyncIdAutocomplete<T>({
  name,
  getOptionId,
  resolveOption,
  onOptionChange,
  ...rest
}: FormikAsyncIdAutocompleteProps<T>) {
  const [field, meta, helpers] = useField<string>(name);
  const id = field.value;
  const [selected, setSelected] = useState<T | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const current = selected !== null && getOptionId(selected) === id ? selected : null;
  const needsResolve = id !== '' && current === null && resolveOption !== undefined;

  useEffect(() => {
    if (!needsResolve) return undefined;
    const controller = new AbortController();
    resolveOption(id, controller.signal)
      .then((option) => {
        if (controller.signal.aborted) return;
        setSelected(option);
        setResolveError(option === null ? 'The selected record is no longer available.' : null);
        onOptionChange?.(option);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isCancelled(err)) return;
        setResolveError(err instanceof Error ? err.message : 'Could not load the selection.');
      });
    return () => {
      controller.abort();
    };
    // onOptionChange is a notification only; re-resolving when it changes identity is not needed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsResolve, id, resolveOption]);

  const isEqual = useCallback((a: T, b: T) => getOptionId(a) === getOptionId(b), [getOptionId]);
  const showError = meta.touched && typeof meta.error === 'string';
  return (
    <AsyncAutocomplete<T>
      {...rest}
      name={name}
      value={current}
      isOptionEqualToValue={isEqual}
      onChange={(next) => {
        setSelected(next);
        setResolveError(null);
        onOptionChange?.(next);
        void helpers.setValue(next === null ? '' : getOptionId(next));
      }}
      onBlur={() => {
        void helpers.setTouched(true);
      }}
      error={showError ? meta.error : (resolveError ?? undefined)}
    />
  );
}
