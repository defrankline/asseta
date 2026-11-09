import { object, type Schema } from 'yup';
import type { components } from '../generated/schema';
import type { Page } from '../types';
import { id, nullableId, nullableNum, nullableText, text } from './schemaKit';
import {
  seg,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

export type TenantDeviceDto = components['schemas']['TenantDeviceDto'];

const deviceSchema: Schema<TenantDeviceDto> = object({
  id: id(),
  device_id: text(),
  platform: text(),
  app_version: text(),
  status: text(),
  registered_at: text(),
  last_sync_at: nullableText(),
  offline_grant_until: text(),
  last_clock_offset_s: nullableNum(),
  revoked_at: nullableText(),
  revoke_reason: nullableText(),
  user_id: id(),
  user_name: nullableText(),
  device_model: nullableText(),
  revoked_by: nullableId(),
  revoked_by_name: nullableText(),
});

const devicePage = tenantPageSchema(deviceSchema);
const DEVICES = '/tenant/devices';

/** Administration → Devices: registered phones, and revoking a lost one. */
export const deviceService = {
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<TenantDeviceDto>> {
    return tenantPage(DEVICES, devicePage, query, 'devices', signal);
  },
  revoke(deviceId: string, reason: string, idempotencyKey: string): Promise<TenantDeviceDto> {
    return tenantSend(
      'post',
      `${DEVICES}/${seg(deviceId)}/revoke`,
      { reason },
      deviceSchema,
      'device',
      idempotencyKey,
    );
  },
};
