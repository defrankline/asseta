import { vi } from 'vitest';
import { ApiError } from '../api/ApiError';
import type { NotificationService } from '../api/services/notificationService';
import type {
  NotificationDto,
  NotificationPreferenceDto,
  NotificationProfileDto,
  SmsDeliveryDto,
} from '../api/types';

let seq = 0;

export function makeNotification(overrides: Partial<NotificationDto> = {}): NotificationDto {
  seq += 1;
  return {
    id: `n-${String(seq)}`,
    type: 'ALERT_RAISED',
    category: 'ANOMALY',
    severity: 'INFO',
    priority: 'NORMAL',
    title: `Notification ${String(seq)}`,
    body: '',
    created_at: new Date(Date.UTC(2026, 9, 21, 8, 0, seq)).toISOString(),
    read_at: null,
    target: null,
    tenant_id: null,
    data: {},
    ...overrides,
  };
}

export function makePreference(
  overrides: Partial<NotificationPreferenceDto> = {},
): NotificationPreferenceDto {
  return {
    type: 'ALERT_RAISED',
    label: 'Tracking alerts',
    description: 'Geofence exits, tamper and power loss',
    category: 'ANOMALY',
    in_app: true,
    sms: false,
    mandatory: false,
    mandatory_channels: [],
    low_priority: false,
    sms_available: true,
    ...overrides,
  };
}

export function makeDelivery(overrides: Partial<SmsDeliveryDto> = {}): SmsDeliveryDto {
  return {
    id: 'd-1',
    tenant_id: null,
    notification_id: 'n-1',
    notification_type: 'PLATFORM_INVOICE_OVERDUE',
    msisdn: '+255712345678',
    status: 'SENT',
    segments: 1,
    attempts: 1,
    billable: true,
    provider: 'console',
    last_error: null,
    created_at: '2026-10-21T08:00:00Z',
    sent_at: '2026-10-21T08:00:05Z',
    next_attempt_at: '2026-10-21T08:00:00Z',
    ...overrides,
  };
}

/**
 * In-memory NotificationService: newest first, server-side filters and paging, read state,
 * per-channel mandatory refusal (422 MANDATORY_CHANNEL), profile and delivery log.
 * Every method is a `vi.fn` so tests can assert calls or make one fail.
 */
export function fakeNotificationService(
  initial: NotificationDto[] = [],
  preferences: NotificationPreferenceDto[] = [],
  console: 'platform' | 'tenant' = 'platform',
) {
  const store = {
    items: [...initial],
    preferences: [...preferences],
    tenantDefaults: [...preferences],
    profile: { user_id: 'u-1', msisdn: null } as NotificationProfileDto,
    deliveries: [makeDelivery()],
  };
  const unread = () => store.items.filter((n) => n.read_at === null).length;
  const service = {
    store,
    console,
    list: vi.fn<NotificationService['list']>((query) => {
      const q = query.q?.toLowerCase();
      const filtered = [...store.items]
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .filter((n) => query.unread_only !== true || n.read_at === null)
        .filter((n) => query.severity === undefined || n.severity === query.severity)
        .filter((n) => q === undefined || n.title.toLowerCase().includes(q));
      const start = (query.page - 1) * query.page_size;
      return Promise.resolve({
        items: filtered.slice(start, start + query.page_size),
        total: filtered.length,
        page: query.page,
        page_size: query.page_size,
      });
    }),
    unreadCount: vi.fn<NotificationService['unreadCount']>(() => Promise.resolve(unread())),
    markRead: vi.fn<NotificationService['markRead']>((ids) => {
      const now = new Date().toISOString();
      store.items = store.items.map((n) => (ids.includes(n.id) ? { ...n, read_at: now } : n));
      return Promise.resolve({ updated: ids.length, unread: unread() });
    }),
    markAllRead: vi.fn<NotificationService['markAllRead']>(() => {
      const before = unread();
      const now = new Date().toISOString();
      store.items = store.items.map((n) => (n.read_at === null ? { ...n, read_at: now } : n));
      return Promise.resolve({ updated: before, unread: 0 });
    }),
    getPreferences: vi.fn<NotificationService['getPreferences']>((tenantDefault) =>
      Promise.resolve(
        (tenantDefault ? store.tenantDefaults : store.preferences).map((p) => ({ ...p })),
      ),
    ),
    updatePreferences: vi.fn<NotificationService['updatePreferences']>((body) => {
      const list = body.tenant_default ? store.tenantDefaults : store.preferences;
      for (const c of body.changes) {
        const p = list.find((x) => x.type === c.type);
        if (
          p !== undefined &&
          ((!c.in_app && p.mandatory_channels.includes('IN_APP')) ||
            (!c.sms && p.mandatory_channels.includes('SMS')))
        ) {
          return Promise.reject(
            new ApiError({
              status: 422,
              code: 'MANDATORY_CHANNEL',
              message: `${p.label}: mandatory channels cannot be disabled`,
              correlationId: 'mc',
            }),
          );
        }
      }
      const next = list.map((p) => {
        const c = body.changes.find((x) => x.type === p.type);
        return c === undefined ? p : { ...p, in_app: c.in_app, sms: c.sms };
      });
      if (body.tenant_default) store.tenantDefaults = next;
      else store.preferences = next;
      return Promise.resolve(next.map((p) => ({ ...p })));
    }),
    getProfile: vi.fn<NotificationService['getProfile']>(() =>
      Promise.resolve({ ...store.profile }),
    ),
    updateProfile: vi.fn<NotificationService['updateProfile']>((body) => {
      const raw = body.msisdn ?? null;
      if (raw !== null && !/^\+?[\d ]{9,15}$/.test(raw)) {
        return Promise.reject(
          new ApiError({
            status: 422,
            code: 'INVALID_MSISDN',
            message: 'Not a valid mobile number',
            correlationId: 'im',
          }),
        );
      }
      store.profile = { ...store.profile, msisdn: raw === null ? null : raw.replace(/ /g, '') };
      return Promise.resolve({ ...store.profile });
    }),
    listDeliveries: vi.fn<NotificationService['listDeliveries']>((query) => {
      const items = store.deliveries.filter(
        (d) => query.status === undefined || d.status === query.status,
      );
      return Promise.resolve({
        items,
        total: items.length,
        page: query.page,
        page_size: query.page_size,
      });
    }),
    testSend: vi.fn<NonNullable<NotificationService['testSend']>>((body) =>
      Promise.resolve({
        notification: makeNotification({ title: body.title }),
        delivery: body.msisdn == null ? null : makeDelivery({ msisdn: body.msisdn }),
      }),
    ),
  } satisfies NotificationService & { store: typeof store };
  return service;
}

export type FakeNotificationService = ReturnType<typeof fakeNotificationService>;
