import { useCallback, useRef } from 'react';
import { newIdempotencyKey } from '../api/ids';

interface KeyState {
  key: string | null;
  fingerprint: string | null;
}

/**
 * One Idempotency-Key per user intent. Mount the owning dialog only while it is open, so each open
 * starts a new intent. Retrying the same payload reuses the key (the server replays instead of
 * duplicating); a changed payload is a new submission and gets a fresh key, because the server
 * rejects a reused key with a different body (IDEMPOTENCY_MISMATCH).
 */
export function useIdempotencyKey(): (payload: unknown) => string {
  const state = useRef<KeyState>({ key: null, fingerprint: null });
  return useCallback((payload: unknown) => {
    const fingerprint = JSON.stringify(payload ?? null);
    const current = state.current;
    if (current.key !== null && current.fingerprint === fingerprint) return current.key;
    const key = newIdempotencyKey();
    state.current = { key, fingerprint };
    return key;
  }, []);
}
