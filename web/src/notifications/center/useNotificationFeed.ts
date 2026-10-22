import { useCallback, useEffect, useState } from 'react';
import { isCancelled, toApiError, type ApiError } from '../../api/ApiError';
import type { NotificationListQuery } from '../../api/services/notificationService';
import type { NotificationDto, NotificationSeverity } from '../../api/types';
import { useRealtimeEvent, useRealtimeResync } from '../../realtime/hooks';
import { useNotificationCenter } from './NotificationCenterContext';

export interface FeedFilters {
  unreadOnly?: boolean;
  severity?: NotificationSeverity;
  q?: string;
}

export interface NotificationFeed {
  items: readonly NotificationDto[];
  total: number;
  /** The first page is loading (or reloading). */
  loading: boolean;
  loadingMore: boolean;
  error: ApiError | null;
  hasMore: boolean;
  loadMore: () => void;
  reload: () => void;
  /** Optimistic: shown read at once, restored if the server refuses. */
  markRead: (item: NotificationDto) => Promise<void>;
  markAllRead: () => Promise<void>;
}

interface Cursor {
  filtersKey: string;
  page: number;
  tick: number;
}

interface Data {
  key: string;
  filtersKey: string;
  items: NotificationDto[];
  total: number;
  error: ApiError | null;
}

const EMPTY: Data = { key: '', filtersKey: '', items: [], total: 0, error: null };

function matches(n: NotificationDto, f: FeedFilters): boolean {
  if (f.severity !== undefined && n.severity !== f.severity) return false;
  // A text search is server-side; pushed items are only merged into unsearched lists.
  return f.q === undefined || f.q === '';
}

function mergeById(a: readonly NotificationDto[], b: readonly NotificationDto[]) {
  const seen = new Set(a.map((n) => n.id));
  return [...a, ...b.filter((n) => !seen.has(n.id))];
}

/**
 * Paged notification list ("load more") that merges real-time pushes at the top and keeps read
 * state in sync with the badge.
 */
export function useNotificationFeed(filters: FeedFilters, pageSize = 20): NotificationFeed {
  const center = useNotificationCenter();
  const { service } = center;
  const filtersKey = JSON.stringify([filters.unreadOnly === true, filters.severity, filters.q]);
  const [cursor, setCursor] = useState<Cursor>({ filtersKey, page: 1, tick: 0 });
  const page = cursor.filtersKey === filtersKey ? cursor.page : 1;
  const tick = cursor.filtersKey === filtersKey ? cursor.tick : 0;
  const key = `${filtersKey}#${String(page)}#${String(tick)}`;
  const [data, setData] = useState<Data>(EMPTY);

  useEffect(() => {
    const controller = new AbortController();
    const [unreadOnly, severity, q] = JSON.parse(filtersKey) as [
      boolean,
      NotificationSeverity | null,
      string | null,
    ];
    const query: NotificationListQuery = { page, page_size: pageSize };
    if (unreadOnly) query.unread_only = true;
    if (severity !== null) query.severity = severity;
    if (q !== null && q !== '') query.q = q;
    service
      .list(query, controller.signal)
      .then((res) => {
        if (controller.signal.aborted) return;
        setData((prev) => ({
          key,
          filtersKey,
          items:
            page === 1 || prev.filtersKey !== filtersKey
              ? res.items
              : mergeById(prev.items, res.items),
          total: res.total,
          error: null,
        }));
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isCancelled(err)) return;
        setData((prev) => ({ ...prev, key, error: toApiError(err) }));
      });
    return () => {
      controller.abort();
    };
    // `key` encodes filters, page and the reload tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [service, key, pageSize]);

  useRealtimeEvent('notification', (n) => {
    if (!matches(n, filters)) return;
    setData((prev) =>
      prev.filtersKey !== filtersKey || prev.items.some((i) => i.id === n.id)
        ? prev
        : { ...prev, items: [n, ...prev.items], total: prev.total + 1 },
    );
  });

  // The inbox is the durable record: re-read it after a reconnect.
  useRealtimeResync(() => {
    setCursor({ filtersKey, page: 1, tick: tick + 1 });
  });

  const setReadAt = useCallback((id: string, readAt: string | null) => {
    setData((prev) => ({
      ...prev,
      items: prev.items.map((i) => (i.id === id ? { ...i, read_at: readAt } : i)),
    }));
  }, []);

  const pending = data.key !== key;
  const current = data.filtersKey === filtersKey;
  const { allReadAt } = center;
  const loaded = current ? data.items : [];
  // After "mark all read", items created up to then are read (and leave an unread-only list).
  const cutoff = allReadAt === null ? null : Date.parse(allReadAt);
  const items =
    cutoff === null || allReadAt === null
      ? loaded
      : loaded
          .map((i) =>
            i.read_at === null && Date.parse(i.created_at) <= cutoff
              ? { ...i, read_at: allReadAt }
              : i,
          )
          .filter((i) => filters.unreadOnly !== true || i.read_at === null);
  return {
    items,
    total: current ? data.total : 0,
    loading: pending && page === 1,
    loadingMore: pending && page > 1,
    error: pending ? null : data.error,
    hasMore: current && loaded.length < data.total,
    loadMore: () => {
      setCursor({ filtersKey, page: page + 1, tick });
    },
    reload: () => {
      setCursor({ filtersKey, page: 1, tick: tick + 1 });
    },
    markRead: async (item) => {
      if (item.read_at !== null) return;
      setReadAt(item.id, new Date().toISOString());
      try {
        await center.markRead([item.id]);
      } catch (err) {
        setReadAt(item.id, null);
        throw err;
      }
    },
    markAllRead: () => center.markAllRead(),
  };
}
