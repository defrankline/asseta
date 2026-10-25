import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { isCancelled } from '../../api/ApiError';
import { newIdempotencyKey } from '../../api/ids';
import type { NotificationService } from '../../api/services/notificationService';
import { useRealtimeEvent } from '../../realtime/hooks';
import { useNotify } from '../useNotify';
import { isHighPriority, notificationTargetPath, SEVERITY_META } from './display';
import {
  NotificationCenterContext,
  type NotificationCenterValue,
} from './NotificationCenterContext';

interface NotificationCenterProviderProps {
  service: NotificationService;
  /** Console key (`platform` / `tenant:<id>`): the inbox is per console, reloaded on switch. */
  scopeKey: string;
  /**
   * The current console grants `tenant.notification.read` / `platform.notification.read`; when
   * false nothing is loaded and the bell hides itself.
   */
  enabled?: boolean;
  children: ReactNode;
}

interface CountState {
  key: string;
  count: number | null;
}

/**
 * Unread badge state and real-time notification handling: a pushed notification raises the badge
 * and, when high priority, shows a toast with a link to the screen it concerns.
 */
export function NotificationCenterProvider({
  service,
  scopeKey,
  enabled = true,
  children,
}: NotificationCenterProviderProps) {
  const notify = useNotify();
  const navigate = useNavigate();
  const [tick, setTick] = useState(0);
  const [state, setState] = useState<CountState>({ key: '', count: null });
  const [allRead, setAllRead] = useState<{ key: string; at: string } | null>(null);
  const requestKey = `${scopeKey}#${String(tick)}`;

  useEffect(() => {
    if (!enabled) return undefined;
    const controller = new AbortController();
    service
      .unreadCount(controller.signal)
      .then((count) => {
        if (!controller.signal.aborted) setState({ key: scopeKey, count });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isCancelled(err)) return;
        setState((s) => (s.key === scopeKey ? s : { key: scopeKey, count: null }));
      });
    return () => {
      controller.abort();
    };
    // requestKey covers scopeKey and explicit refreshes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [service, requestKey, enabled]);

  const refreshUnread = useCallback(() => {
    setTick((t) => t + 1);
  }, []);
  // A (re)connect's `auth_ok` carries the server count, so the badge re-syncs after a drop.

  const unreadCount = enabled && state.key === scopeKey ? state.count : null;
  const adjust = useCallback(
    (delta: number) => {
      setState((s) =>
        s.key === scopeKey && s.count !== null ? { ...s, count: Math.max(0, s.count + delta) } : s,
      );
    },
    [scopeKey],
  );
  const setCount = useCallback(
    (count: number) => {
      setState({ key: scopeKey, count });
    },
    [scopeKey],
  );

  useRealtimeEvent('unread_count', ({ count }) => {
    if (enabled) setCount(count);
  });
  useRealtimeEvent('notification', (n) => {
    if (!enabled || n.read_at !== null) return;
    adjust(1);
    if (!isHighPriority(n)) return;
    const path = notificationTargetPath(n.target, n.data);
    notify.notify(
      n.title,
      SEVERITY_META[n.severity].toast,
      path === null
        ? {}
        : {
            action: {
              label: 'View',
              onClick: () => {
                void navigate(path);
                service.markRead([n.id], newIdempotencyKey()).then(
                  (r) => {
                    setCount(r.unread);
                  },
                  () => undefined,
                );
              },
            },
          },
    );
  });

  const markRead = useCallback(
    async (ids: readonly string[]) => {
      if (ids.length === 0) return;
      const result = await service.markRead(ids, newIdempotencyKey());
      setCount(result.unread);
    },
    [service, setCount],
  );

  const markAllRead = useCallback(async () => {
    const result = await service.markAllRead(newIdempotencyKey());
    setState({ key: scopeKey, count: result.unread });
    setAllRead({ key: scopeKey, at: new Date().toISOString() });
  }, [service, scopeKey]);

  const allReadAt = allRead?.key === scopeKey ? allRead.at : null;
  const value = useMemo<NotificationCenterValue>(
    () => ({ service, enabled, unreadCount, refreshUnread, markRead, markAllRead, allReadAt }),
    [service, enabled, unreadCount, refreshUnread, markRead, markAllRead, allReadAt],
  );
  return (
    <NotificationCenterContext.Provider value={value}>
      {children}
    </NotificationCenterContext.Provider>
  );
}
