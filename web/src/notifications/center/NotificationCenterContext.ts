import { createContext, useContext } from 'react';
import type { NotificationService } from '../../api/services/notificationService';

export interface NotificationCenterValue {
  /** Implementation for the current console (platform or tenant). */
  service: NotificationService;
  /** The current console grants notification read; the bell and inbox hide otherwise. */
  enabled: boolean;
  /** Unread notifications in the current console; null until known (or unavailable). */
  unreadCount: number | null;
  /** Re-read the unread count from the server. */
  refreshUnread: () => void;
  /** Marks notifications read on the server and lowers the badge. Rejects on failure. */
  markRead: (ids: readonly string[]) => Promise<void>;
  /** Marks everything read on the server and clears the badge. Rejects on failure. */
  markAllRead: () => Promise<void>;
  /**
   * When "mark all read" last succeeded in this console: open lists show items created up to then
   * as read without refetching.
   */
  allReadAt: string | null;
}

export const NotificationCenterContext = createContext<NotificationCenterValue | null>(null);

export function useNotificationCenter(): NotificationCenterValue {
  const ctx = useContext(NotificationCenterContext);
  if (ctx === null) {
    throw new Error('useNotificationCenter must be used inside <NotificationCenterProvider>.');
  }
  return ctx;
}

/** Null outside a provider (e.g. header rendered in isolation): the bell then hides itself. */
export function useOptionalNotificationCenter(): NotificationCenterValue | null {
  return useContext(NotificationCenterContext);
}
