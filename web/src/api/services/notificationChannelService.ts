import { array, mixed, object, string, type Schema } from 'yup';
import { apiClient, toListParams, type QueryParams } from '../client';
import type {
  ChannelDeliveryStatus,
  DeviceApp,
  DeviceDeactivation,
  DevicePlatform,
  NotificationCategory,
  NotificationChannel,
  NotificationChannelDeliveryDto,
  NotificationRoutingDto,
  NotificationRoutingIn,
  NotificationSeverity,
  Page,
  PushDeviceDto,
} from '../types';
import { parseResponse } from '../validation';
import { pageSchema } from './billingSchemas';
import { bool, int, nullableOneOf, nullableText, oneOf, text } from './schemaKit';

export type ChannelConsole = 'tenant' | 'platform';

export const NOTIFICATION_CATEGORIES: readonly NotificationCategory[] = [
  'ACTION',
  'REMINDER',
  'ANOMALY',
  'BILLING',
  'INFO',
];
export const ROUTING_SEVERITIES: readonly NotificationSeverity[] = ['INFO', 'WARNING', 'CRITICAL'];
export const CHANNELS: readonly NotificationChannel[] = ['IN_APP', 'SMS', 'PUSH', 'EMAIL'];
export const CHANNEL_DELIVERY_STATUSES: readonly ChannelDeliveryStatus[] = [
  'PENDING',
  'SENT',
  'FAILED',
  'UNDELIVERABLE',
];
const PLATFORMS: readonly DevicePlatform[] = ['ANDROID', 'IOS'];
const APPS: readonly DeviceApp[] = ['OWNER', 'SUPERVISOR'];
const DEACTIVATIONS: readonly DeviceDeactivation[] = ['USER', 'PROVIDER_UNREGISTERED'];

const routingSchema: Schema<NotificationRoutingDto> = object({
  category: oneOf(NOTIFICATION_CATEGORIES),
  severity: oneOf(ROUTING_SEVERITIES),
  in_app: bool(),
  push: bool(),
  email: bool(),
  mandatory_channels: array(mixed<NotificationChannel>().oneOf(CHANNELS).required()).required(),
  source: text(),
});
const routingListSchema = array(routingSchema).required();

const deviceSchema: Schema<PushDeviceDto> = object({
  id: string().required(),
  tenant_id: nullableText(),
  platform: oneOf(PLATFORMS),
  app: oneOf(APPS),
  token_hint: text(),
  app_version: nullableText(),
  device_label: nullableText(),
  active: bool(),
  created_at: string().required(),
  last_registered_at: string().required(),
  deactivated_at: nullableText(),
  deactivation_reason: nullableOneOf(DEACTIVATIONS),
});

const deliverySchema: Schema<NotificationChannelDeliveryDto> = object({
  id: string().required(),
  notification_id: string().required(),
  tenant_id: nullableText(),
  recipient_user_id: string().required(),
  channel: oneOf(CHANNELS),
  push_device_id: nullableText(),
  notification_type: text(),
  severity: oneOf(ROUTING_SEVERITIES),
  status: oneOf(CHANNEL_DELIVERY_STATUSES),
  attempts: int(),
  next_attempt_at: string().required(),
  last_error: nullableText(),
  provider: nullableText(),
  created_at: string().required(),
  sent_at: nullableText(),
});

const devicePageSchema = pageSchema(deviceSchema);
const deliveryPageSchema = pageSchema(deliverySchema);

export interface ChannelDeliveryQuery {
  page: number;
  page_size: number;
  channel?: string | undefined;
  status?: string | undefined;
}

function clean(params: QueryParams): QueryParams {
  const out: QueryParams = {};
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') out[k] = v;
  return out;
}

/**
 * PUSH / EMAIL channels (ADR-005 Gate 7): category x severity routing, the signed-in user's push
 * devices and the channel delivery log of the current console.
 */
export const notificationChannelService = {
  /** GET /{console}/notification-routing (`tenant_default`: the tenant-wide defaults). */
  async getRouting(
    console: ChannelConsole,
    tenantDefault: boolean,
    signal?: AbortSignal,
  ): Promise<NotificationRoutingDto[]> {
    const data = await apiClient.get<unknown>(`/${console}/notification-routing`, {
      tenantScoped: console === 'tenant',
      ...(tenantDefault ? { params: { tenant_default: true } } : {}),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(routingListSchema, data, 'notification routing');
  },
  /** PUT /{console}/notification-routing; a mandatory channel is refused (422 MANDATORY_CHANNEL). */
  async updateRouting(
    console: ChannelConsole,
    body: NotificationRoutingIn,
    idempotencyKey: string,
  ): Promise<NotificationRoutingDto[]> {
    const data = await apiClient.put<unknown>(`/${console}/notification-routing`, body, {
      tenantScoped: console === 'tenant',
      idempotencyKey,
    });
    return parseResponse(routingListSchema, data, 'notification routing');
  },
  /** GET /me/push-devices (no tenant header: every device of the signed-in user). */
  async listDevices(includeInactive: boolean, signal?: AbortSignal): Promise<Page<PushDeviceDto>> {
    const data = await apiClient.get<unknown>('/me/push-devices', {
      params: { page: 1, page_size: 100, ...(includeInactive ? { include_inactive: true } : {}) },
      ...(signal ? { signal } : {}),
    });
    return parseResponse(devicePageSchema, data, 'push devices');
  },
  /** DELETE /me/push-devices/{id}: stops pushes to that device (kept, deactivated). */
  async deactivateDevice(deviceId: string, idempotencyKey: string): Promise<PushDeviceDto> {
    const data = await apiClient.delete<unknown>(
      `/me/push-devices/${encodeURIComponent(deviceId)}`,
      { idempotencyKey },
    );
    return parseResponse(deviceSchema, data, 'push device');
  },
  /** GET /{console}/notification-deliveries (manage permission): PUSH and EMAIL log. */
  async listDeliveries(
    console: ChannelConsole,
    query: ChannelDeliveryQuery,
    signal?: AbortSignal,
  ): Promise<Page<NotificationChannelDeliveryDto>> {
    const data = await apiClient.get<unknown>(`/${console}/notification-deliveries`, {
      tenantScoped: console === 'tenant',
      params: {
        ...toListParams({ page: query.page, page_size: query.page_size }),
        ...clean({ channel: query.channel, status: query.status }),
      },
      ...(signal ? { signal } : {}),
    });
    return parseResponse(deliveryPageSchema, data, 'notification delivery page');
  },
};
