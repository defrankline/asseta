import { useEffect, useRef, useState } from 'react';
import type { Page } from '../../../api/types';

const PAGE_SIZE = 200;
const MAX_PAGES = 5;

type FetchList<T> = (
  query: { page: number; page_size: number; filters: Readonly<Record<string, string | undefined>> },
  signal: AbortSignal,
) => Promise<Page<T>>;

/**
 * A record opened by id on a list whose API has no GET-by-id: scans the most recent pages (up to
 * 1000 records). `missing` when it is not among them.
 */
export function useFocusedRecord<T extends { id: string }>(
  fetchList: FetchList<T>,
  id: string | undefined,
  onFound?: (record: T) => void,
): { record: T | null; missing: boolean } {
  const [found, setFound] = useState<{ id: string; record: T | null } | null>(null);
  const notify = useRef(onFound);
  useEffect(() => {
    notify.current = onFound;
  });
  useEffect(() => {
    if (id === undefined) return undefined;
    const controller = new AbortController();
    const scan = async () => {
      for (let page = 1; page <= MAX_PAGES; page += 1) {
        const result = await fetchList(
          { page, page_size: PAGE_SIZE, filters: {} },
          controller.signal,
        );
        const hit = result.items.find((r) => r.id === id);
        if (hit !== undefined) return hit;
        if (page * PAGE_SIZE >= result.total) return null;
      }
      return null;
    };
    scan().then(
      (record) => {
        setFound({ id, record });
        if (record !== null) notify.current?.(record);
      },
      () => {
        if (!controller.signal.aborted) setFound({ id, record: null });
      },
    );
    return () => {
      controller.abort();
    };
  }, [fetchList, id]);
  if (id === undefined || found === null || found.id !== id)
    return { record: null, missing: false };
  return { record: found.record, missing: found.record === null };
}
