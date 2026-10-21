import { useState } from 'react';
import { isStaleVersion } from '../../api/lifecycle';

/**
 * Tracks whether an edit submission hit STALE_VERSION: wrap the service call with `guard`
 * (it re-throws so the form still shows the server message) and render `<StaleVersionAlert>`
 * while `stale` is true.
 */
export function useStaleVersion(): {
  stale: boolean;
  guard: <T>(call: () => Promise<T>) => Promise<T>;
} {
  const [stale, setStale] = useState(false);
  return {
    stale,
    guard: async (call) => {
      try {
        return await call();
      } catch (err) {
        if (isStaleVersion(err)) setStale(true);
        throw err;
      }
    },
  };
}
