import { useCallback, useEffect, useState } from 'react';
import { isCancelled, toApiError, type ApiError } from '../api/ApiError';

interface State<T> {
  key: string;
  data: T | null;
  error: ApiError | null;
}

export interface AsyncResource<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Loads data whenever `deps` (serialised) change or `reload()` is called; aborts stale requests.
 * Keep `load` stable (useCallback) or pass changing inputs through `deps`.
 */
export function useAsyncResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[] = [],
  enabled = true,
): AsyncResource<T> {
  const [tick, setTick] = useState(0);
  const [state, setState] = useState<State<T>>({ key: '', data: null, error: null });
  const key = `${JSON.stringify(deps)}#${String(tick)}`;

  useEffect(() => {
    if (!enabled) return undefined;
    const controller = new AbortController();
    load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ key, data, error: null });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isCancelled(err)) return;
        setState((s) => ({ key, data: s.data, error: toApiError(err) }));
      });
    return () => {
      controller.abort();
    };
  }, [load, key, enabled]);

  const reload = useCallback(() => {
    setTick((t) => t + 1);
  }, []);
  const loading = enabled && state.key !== key;
  return { data: state.data, error: loading ? null : state.error, loading, reload };
}
