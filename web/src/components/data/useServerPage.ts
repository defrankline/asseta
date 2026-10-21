import { useEffect, useState } from 'react';
import { isCancelled, toApiError, type ApiError } from '../../api/ApiError';
import type { Page } from '../../api/types';

export interface ServerQuery {
  /** 1-based page number as sent to the API. */
  page: number;
  page_size: number;
  sort?: string;
  q?: string;
  filters: Readonly<Record<string, string | undefined>>;
}

export type FetchPage<T> = (query: ServerQuery, signal: AbortSignal) => Promise<Page<T>>;

interface State<T> {
  /** Request signature the data/error belongs to. */
  key: string;
  data: Page<T> | null;
  error: ApiError | null;
}

/** Fetches a server page whenever the (stable-keyed) query changes; aborts stale requests. */
export function useServerPage<T>(fetchPage: FetchPage<T>, query: ServerQuery, reloadKey: number) {
  const [state, setState] = useState<State<T>>({ key: '', data: null, error: null });
  const queryKey = JSON.stringify(query);
  const key = `${queryKey}#${String(reloadKey)}`;

  useEffect(() => {
    const controller = new AbortController();
    const parsed = JSON.parse(queryKey) as ServerQuery;
    fetchPage(parsed, controller.signal)
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
  }, [fetchPage, queryKey, key]);

  const loading = state.key !== key;
  return { data: state.data, error: loading ? null : state.error, loading };
}
