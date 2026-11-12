import { array, object, string, type Schema } from 'yup';
import { apiClient, toListParams } from '../client';
import type { components } from '../generated/schema';
import type { Page } from '../types';
import { parseResponse } from '../validation';
import { id, int, nullableId, nullableText, oneOf, text } from './schemaKit';
import {
  seg,
  tenantGet,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

type Schemas = components['schemas'];
export type CompanyDeletionRequestDto = Schemas['CompanyDeletionRequestDto'];
export type CompanyDeletionStatusDto = Schemas['CompanyDeletionStatusDto'];
export type DeletionStatus = Schemas['DeletionStatus'];

export const DELETION_STATUSES: readonly DeletionStatus[] = [
  'REQUESTED',
  'CANCELLED',
  'IN_PROGRESS',
  'COMPLETED',
];

const requestFields = {
  id: id(),
  tenant_id: id(),
  tenant_name: text(),
  status: oneOf<DeletionStatus>(DELETION_STATUSES),
  reason: text(),
  requested_by: nullableId(),
  requested_by_name: nullableText(),
  requested_at: text(),
  waiting_days: int(),
  scheduled_for: text(),
  policy_version: text(),
  cancelled_by: nullableId(),
  cancelled_by_name: nullableText(),
  cancelled_at: nullableText(),
  cancel_reason: nullableText(),
  execute_now_by: nullableId(),
  execute_now_at: nullableText(),
  execute_now_reason: nullableText(),
  started_at: nullableText(),
  completed_at: nullableText(),
  attempts: int(),
  last_error: nullableText(),
  steps_done: array(string().required()).required(),
};

const requestSchema: Schema<CompanyDeletionRequestDto> = object(requestFields);

const statusSchema: Schema<CompanyDeletionStatusDto> = object({
  tenant_id: id(),
  company_name: text(),
  waiting_days: int(),
  request: object(requestFields).nullable().defined(),
});

const requestPage = tenantPageSchema(requestSchema);

const TENANT = '/tenant/company/deletion-request';
const PLATFORM = '/platform/deletion-requests';

/** Administration -> Close company (tenant) and Tenants -> Deletion requests (platform). */
export const companyClosureService = {
  /** The company name to type, the waiting period and the active (else latest) request. */
  getStatus(signal?: AbortSignal): Promise<CompanyDeletionStatusDto> {
    return tenantGet(TENANT, statusSchema, 'company closure', signal);
  },
  /** Read-only at once; all of the company's data is deleted after the waiting period. */
  request(
    body: { confirm_name: string; reason: string },
    idempotencyKey: string,
  ): Promise<CompanyDeletionRequestDto> {
    return tenantSend('post', TENANT, body, requestSchema, 'closure request', idempotencyKey);
  },
  cancel(reason: string, idempotencyKey: string): Promise<CompanyDeletionRequestDto> {
    return tenantSend(
      'post',
      `${TENANT}/cancel`,
      { reason },
      requestSchema,
      'closure request',
      idempotencyKey,
    );
  },
  /** Paged; `filters.status` narrows to one status. */
  async list(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<CompanyDeletionRequestDto>> {
    const data = await apiClient.get<unknown>(PLATFORM, {
      params: toListParams(query),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(requestPage, data, 'deletion requests');
  },
  async get(requestId: string, signal?: AbortSignal): Promise<CompanyDeletionRequestDto> {
    const data = await apiClient.get<unknown>(
      `${PLATFORM}/${seg(requestId)}`,
      signal ? { signal } : undefined,
    );
    return parseResponse(requestSchema, data, 'deletion request');
  },
  /** Run before the waiting period ends: only when the owner asked for it in writing. */
  async executeNow(
    requestId: string,
    reason: string,
    idempotencyKey: string,
  ): Promise<CompanyDeletionRequestDto> {
    const data = await apiClient.post<unknown>(
      `${PLATFORM}/${seg(requestId)}/execute`,
      { reason },
      { idempotencyKey },
    );
    return parseResponse(requestSchema, data, 'deletion request');
  },
};
