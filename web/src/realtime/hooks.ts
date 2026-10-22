import { useContext, useEffect, useRef, useSyncExternalStore } from 'react';
import { matchesEntityKeys } from './entities';
import type { ConnectionStatus, RealtimeEventMap, RealtimeEventType } from './protocol';
import { RealtimeContext } from './RealtimeContext';

const NO_SUBSCRIBE = () => () => undefined;
const IDLE = (): ConnectionStatus => 'idle';

/** Connection state of the session's realtime link (`idle` outside a provider / signed out). */
export function useRealtimeStatus(): ConnectionStatus {
  const client = useContext(RealtimeContext);
  return useSyncExternalStore(client?.onStatus ?? NO_SUBSCRIBE, client?.getStatus ?? IDLE);
}

/**
 * Calls `handler` for every server event of `type`. The handler may change identity freely; the
 * subscription stays put. A no-op outside a `RealtimeProvider`.
 */
export function useRealtimeEvent<K extends RealtimeEventType>(
  type: K,
  handler: (payload: RealtimeEventMap[K]) => void,
): void {
  const client = useContext(RealtimeContext);
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => {
    if (client === null) return undefined;
    return client.subscribe(type, (payload) => {
      ref.current(payload);
    });
  }, [client, type]);
}

export interface LiveRefreshOptions {
  /** Bursts of changes within this window cause one reload (default 400 ms). */
  debounceMs?: number;
  enabled?: boolean;
}

/**
 * Reloads an open screen when the server announces a change to any of `entityKeys`
 * (`kind` or `kind:id`, see `entityKey`) and after a reconnect, when changes may have been missed.
 */
export function useLiveRefresh(
  entityKeys: readonly string[],
  reload: () => void,
  { debounceMs = 400, enabled = true }: LiveRefreshOptions = {},
): void {
  const client = useContext(RealtimeContext);
  const reloadRef = useRef(reload);
  useEffect(() => {
    reloadRef.current = reload;
  });
  const keysId = entityKeys.join('|');

  useEffect(() => {
    if (client === null || !enabled || keysId === '') return undefined;
    const keys = keysId.split('|');
    let timer: ReturnType<typeof setTimeout> | null = null;
    const trigger = () => {
      if (timer !== null) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = null;
        reloadRef.current();
      }, debounceMs);
    };
    const offChange = client.subscribe('entity.changed', (change) => {
      if (matchesEntityKeys(change, keys)) trigger();
    });
    const offResync = client.onResync(trigger);
    return () => {
      offChange();
      offResync();
      if (timer !== null) clearTimeout(timer);
    };
  }, [client, enabled, keysId, debounceMs]);
}

/**
 * Calls `handler` after the connection came back from a drop. Pushes are best effort: screens
 * holding pushed state (e.g. the inbox) re-read it then.
 */
export function useRealtimeResync(handler: () => void): void {
  const client = useContext(RealtimeContext);
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => {
    if (client === null) return undefined;
    return client.onResync(() => {
      ref.current();
    });
  }, [client]);
}
