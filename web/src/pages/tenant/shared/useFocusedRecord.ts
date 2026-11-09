import { useEffect, useRef, useState } from 'react';

/**
 * A record a link opens on a list page (`/list/:focusId`): loaded by its own id, however old it is.
 * `missing` when it cannot be opened; `onFound` hands it to the page's details view.
 */
export function useFocusedRecord<T>(
  load: (id: string, signal: AbortSignal) => Promise<T>,
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
    load(id, controller.signal).then(
      (record) => {
        if (controller.signal.aborted) return;
        setFound({ id, record });
        notify.current?.(record);
      },
      () => {
        if (!controller.signal.aborted) setFound({ id, record: null });
      },
    );
    return () => {
      controller.abort();
    };
  }, [load, id]);
  if (id === undefined || found === null || found.id !== id)
    return { record: null, missing: false };
  return { record: found.record, missing: found.record === null };
}
