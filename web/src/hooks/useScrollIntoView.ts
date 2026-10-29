import { useEffect, useRef } from 'react';

/**
 * Scrolls the returned element into view once, when `active` (e.g. a `?section=` deep link) and
 * `ready` (its content has loaded, so the layout above it is settled).
 */
export function useScrollIntoView<T extends HTMLElement>(active: boolean, ready = true) {
  const ref = useRef<T | null>(null);
  const done = useRef(false);
  useEffect(() => {
    if (!active || !ready || done.current) return;
    const el = ref.current;
    if (el === null) return;
    done.current = true;
    // Not every environment implements it (e.g. jsdom).
    if (typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'start' });
  }, [active, ready]);
  return ref;
}
