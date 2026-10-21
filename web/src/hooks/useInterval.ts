import { useEffect, useRef } from 'react';

/** Calls `callback` every `delayMs` while `enabled`; the latest callback is always used. */
export function useInterval(callback: () => void, delayMs: number, enabled = true): void {
  const saved = useRef(callback);
  useEffect(() => {
    saved.current = callback;
  }, [callback]);
  useEffect(() => {
    if (!enabled) return undefined;
    const id = window.setInterval(() => {
      saved.current();
    }, delayMs);
    return () => {
      window.clearInterval(id);
    };
  }, [delayMs, enabled]);
}
