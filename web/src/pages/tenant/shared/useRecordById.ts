import { useCallback } from 'react';
import { useAsyncResource, type AsyncResource } from '../../../hooks/useAsyncResource';

/** Loads one record by its id (route `:id`); `reload()` after an action refreshes the page. */
export function useRecordById<T>(
  load: (id: string, signal: AbortSignal) => Promise<T>,
  id: string | undefined,
): AsyncResource<T> {
  const fetcher = useCallback((signal: AbortSignal) => load(id ?? '', signal), [load, id]);
  return useAsyncResource(fetcher, [id], id !== undefined && id !== '');
}
