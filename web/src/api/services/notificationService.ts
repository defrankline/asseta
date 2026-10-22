import { apiClient, toListParams, type QueryParams } from '../client';
import type {
  NotificationMarkReadResultDto,
  NotificationPage,
  NotificationPreferenceDto,
  NotificationPreferencesIn,
  NotificationProfileDto,
  NotificationProfileIn,
  NotificationSeverity,
  NotificationTestSendIn,
  NotificationTestSendResultDto,
  SmsDeliveryPage,
  SmsDeliveryStatus,
} from '../types';
import { parseResponse } from '../validation';
import {
  markReadResultSchema,
  notificationPageSchema,
  notificationPreferencesSchema,
  notificationProfileSchema,
  smsDeliveryPageSchema,
  testSendResultSchema,
  unreadCountSchema,
} from './notificationSchemas';

export type NotificationConsole = 'platform' | 'tenant';

export interface NotificationListQuery {
  page: number;
  page_size: number;
  unread_only?: boolean;
  severity?: NotificationSeverity;
  q?: string;
}

export interface DeliveryListQuery {
  page: number;
  page_size: number;
  status?: SmsDeliveryStatus;
  q?: string;
}

/**
 * Notification inbox, preferences, SMS profile and SMS delivery log of the signed-in user in one
 * console (DEC-022, ADR-005). Screens get the implementation for the current console from the
 * notification center; tests use `src/test/fakeNotificationService.ts`.
 */
export interface NotificationService {
  console: NotificationConsole;
  /** Newest first. */
  list: (query: NotificationListQuery, signal?: AbortSignal) => Promise<NotificationPage>;
  unreadCount: (signal?: AbortSignal) => Promise<number>;
  markRead: (
    ids: readonly string[],
    idempotencyKey: string,
  ) => Promise<NotificationMarkReadResultDto>;
  markAllRead: (idempotencyKey: string) => Promise<NotificationMarkReadResultDto>;
  /** `tenantDefault`: the tenant-wide defaults (tenant console, `tenant.notification.manage`). */
  getPreferences: (
    tenantDefault: boolean,
    signal?: AbortSignal,
  ) => Promise<NotificationPreferenceDto[]>;
  /** Mandatory channels are refused with `422 MANDATORY_CHANNEL`. */
  updatePreferences: (
    body: NotificationPreferencesIn,
    idempotencyKey: string,
  ) => Promise<NotificationPreferenceDto[]>;
  getProfile: (signal?: AbortSignal) => Promise<NotificationProfileDto>;
  /** Invalid numbers are refused with `422 INVALID_MSISDN`. */
  updateProfile: (
    body: NotificationProfileIn,
    idempotencyKey: string,
  ) => Promise<NotificationProfileDto>;
  /** SMS delivery log (`*.notification.manage`). */
  listDeliveries: (query: DeliveryListQuery, signal?: AbortSignal) => Promise<SmsDeliveryPage>;
  /** Platform console only (`platform.notification.manage`). */
  testSend?: (
    body: NotificationTestSendIn,
    idempotencyKey: string,
  ) => Promise<NotificationTestSendResultDto>;
}

function params(record: QueryParams): QueryParams {
  const out: QueryParams = {};
  for (const [k, v] of Object.entries(record)) if (v !== undefined && v !== '') out[k] = v;
  return out;
}

/** HTTP implementation for `/platform/notifications` or `/tenant/notifications` (X-Tenant-ID). */
export function createHttpNotificationService(console: NotificationConsole): NotificationService {
  const base = `/${console}/notifications`;
  const tenantScoped = console === 'tenant';
  const read = async <T>(
    path: string,
    schema: Parameters<typeof parseResponse<T>>[0],
    what: string,
    signal?: AbortSignal,
    query?: QueryParams,
  ): Promise<T> => {
    const data = await apiClient.get<unknown>(`${base}${path}`, {
      tenantScoped,
      ...(signal ? { signal } : {}),
      ...(query !== undefined ? { params: query } : {}),
    });
    return parseResponse(schema, data, what);
  };
  const write = async <T>(
    method: 'post' | 'put',
    path: string,
    body: unknown,
    schema: Parameters<typeof parseResponse<T>>[0],
    what: string,
    idempotencyKey: string,
  ): Promise<T> => {
    const data = await apiClient[method]<unknown>(`${base}${path}`, body, {
      tenantScoped,
      idempotencyKey,
    });
    return parseResponse(schema, data, what);
  };

  const service: NotificationService = {
    console,
    list: ({ page, page_size, q, unread_only, severity }, signal) =>
      read('', notificationPageSchema, 'notification page', signal, {
        ...toListParams({ page, page_size, q }),
        ...params({ unread_only, severity }),
      }),
    unreadCount: async (signal) =>
      (await read('/unread-count', unreadCountSchema, 'unread count', signal)).count,
    markRead: (ids, key) =>
      write('post', '/read', { ids }, markReadResultSchema, 'read result', key),
    markAllRead: (key) => write('post', '/read-all', {}, markReadResultSchema, 'read result', key),
    getPreferences: (tenantDefault, signal) =>
      read(
        '/preferences',
        notificationPreferencesSchema,
        'notification preferences',
        signal,
        tenantDefault ? { tenant_default: true } : {},
      ),
    updatePreferences: (body, key) =>
      write('put', '/preferences', body, notificationPreferencesSchema, 'preferences', key),
    getProfile: (signal) =>
      read('/profile', notificationProfileSchema, 'notification profile', signal),
    updateProfile: (body, key) =>
      write('put', '/profile', body, notificationProfileSchema, 'notification profile', key),
    listDeliveries: ({ page, page_size, q, status }, signal) =>
      read('/deliveries', smsDeliveryPageSchema, 'SMS delivery page', signal, {
        ...toListParams({ page, page_size, q }),
        ...params({ status }),
      }),
  };
  if (console === 'platform') {
    service.testSend = (body, key) =>
      write('post', '/test-send', body, testSendResultSchema, 'test send result', key);
  }
  return service;
}

export const platformNotificationService = createHttpNotificationService('platform');
export const tenantNotificationService = createHttpNotificationService('tenant');
