import { array, object, string, type Schema } from 'yup';
import { apiClient, toListParams } from '../client';
import type { AuditEventDto, Page } from '../types';
import { parseResponse } from '../validation';
import { pageSchema } from './billingSchemas';
import { nullableRecord, nullableText, text } from './schemaKit';
import type { TenantListQuery } from './tenantRequest';

export type AuditScope = 'tenant' | 'platform';

const auditEventSchema: Schema<AuditEventDto> = object({
  id: string().required(),
  occurred_at: string().required(),
  tenant_id: nullableText(),
  actor_user_id: nullableText(),
  actor_display_name: nullableText(),
  actor_roles: array(string().required()).required(),
  source: text(),
  device_id: nullableText(),
  action: text(),
  entity_type: text(),
  entity_id: text(),
  reason: nullableText(),
  policy_version: nullableText(),
  before: nullableRecord(),
  after: nullableRecord(),
  correlation_id: text(),
  mandate_id: nullableText(),
  mandate_reference: nullableText(),
});

const auditPageSchema = pageSchema(auditEventSchema);

/**
 * Audit trail (`listTenantAuditEvents` / `listPlatformAuditEvents`), newest first. Filters:
 * `actor_user_id`, `action_prefix`, `entity_type`, `entity_id`, `occurred_from`, `occurred_to`
 * (exclusive) and, on the platform, `tenant_id`.
 */
export const auditService = {
  async list(
    scope: AuditScope,
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<AuditEventDto>> {
    const data = await apiClient.get<unknown>(`/${scope}/audit-events`, {
      tenantScoped: scope === 'tenant',
      params: toListParams(query),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(auditPageSchema, data, 'audit event page');
  },
};
