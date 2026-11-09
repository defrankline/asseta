import type { AlertActionIn, AlertDto, Page } from '../types';
import { alertSchema } from './geoSchemas';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const alertPageSchema = tenantPageSchema(alertSchema);

export const alertService = {
  /** GET /tenant/alerts (listTrackingAlerts). Filters: `status`, `alert_type`, `machine_id`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<AlertDto>> {
    return tenantPage('/tenant/alerts', alertPageSchema, query, 'alert page', signal);
  },
  /** GET /tenant/alerts/{id} (getTrackingAlert). */
  get(alertId: string, signal?: AbortSignal): Promise<AlertDto> {
    return tenantGet(`/tenant/alerts/${seg(alertId)}`, alertSchema, 'alert', signal);
  },
  /** POST /tenant/alerts/{id}/action (actOnTrackingAlert): ACKNOWLEDGE or RESOLVE (note). */
  act(alertId: string, body: AlertActionIn, idempotencyKey: string): Promise<AlertDto> {
    return tenantSend(
      'post',
      `/tenant/alerts/${seg(alertId)}/action`,
      body,
      alertSchema,
      'alert',
      idempotencyKey,
    );
  },
};
