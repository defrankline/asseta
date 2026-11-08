import type {
  AdjustmentDecisionIn,
  AdjustmentEntryDto,
  AdjustmentPreviewDto,
  AdjustmentPreviewIn,
  AdjustmentRequestDto,
  AdjustmentRequestIn,
  AdjustmentWithdrawIn,
} from '../adjustmentTypes';
import { apiClient, http, type QueryParams } from '../client';
import { newUuid } from '../ids';
import { requestContext } from '../requestContext';
import type { Page } from '../types';
import { parseResponse } from '../validation';
import {
  adjustmentEntrySchema,
  adjustmentPreviewSchema,
  adjustmentRequestSchema,
} from './adjustmentSchemas';
import { exportError, filenameFromDisposition } from './reportService';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const ENTRIES = '/tenant/adjustments';
const REQUESTS = '/tenant/adjustment-requests';
const entryPage = tenantPageSchema(adjustmentEntrySchema);
const requestPage = tenantPageSchema(adjustmentRequestSchema);

/** The adjustments ledger ("Ledger 6") and the propose / decide flow behind it (DEC-032 Phase 2). */
export const adjustmentService = {
  /** GET /tenant/adjustments. Filters: type, status, person_id, date_from, date_to, machine_id, customer_id, staff_member_id, reference, original_id; `q`. */
  listEntries(query: TenantListQuery, signal?: AbortSignal): Promise<Page<AdjustmentEntryDto>> {
    return tenantPage(ENTRIES, entryPage, query, 'adjustments', signal);
  },
  /** GET /tenant/adjustments/{id}. */
  getEntry(id: string, signal?: AbortSignal): Promise<AdjustmentEntryDto> {
    return tenantGet(`${ENTRIES}/${seg(id)}`, adjustmentEntrySchema, 'adjustment', signal);
  },
  /** GET /tenant/adjustments/export.csv with the list's filters. */
  async exportCsv(params: QueryParams): Promise<{ blob: Blob; filename: string }> {
    const response = await http.get<Blob>(`${ENTRIES}/export.csv`, {
      params,
      responseType: 'blob',
      tenantScoped: true,
      validateStatus: () => true,
    });
    if (response.status < 200 || response.status >= 300) {
      const error = await exportError(response.status, response.data);
      if (error.status === 401) requestContext.onUnauthorized();
      throw error;
    }
    const disposition: unknown = response.headers['content-disposition'];
    return {
      blob: response.data,
      filename: filenameFromDisposition(
        typeof disposition === 'string' ? disposition : null,
        'adjustments.csv',
      ),
    };
  },
  /** GET /tenant/adjustment-requests. Filters: request_type, status, customer_id, machine_id, original_id; `q`. */
  listRequests(query: TenantListQuery, signal?: AbortSignal): Promise<Page<AdjustmentRequestDto>> {
    return tenantPage(REQUESTS, requestPage, query, 'adjustment requests', signal);
  },
  /** GET /tenant/adjustment-requests/{id}: `effects` is a forecast while PROPOSED, the outcome once decided. */
  getRequest(id: string, signal?: AbortSignal): Promise<AdjustmentRequestDto> {
    return tenantGet(
      `${REQUESTS}/${seg(id)}`,
      adjustmentRequestSchema,
      'adjustment request',
      signal,
    );
  },
  /** POST /tenant/adjustment-requests. */
  propose(body: AdjustmentRequestIn, idempotencyKey: string): Promise<AdjustmentRequestDto> {
    return tenantSend(
      'post',
      REQUESTS,
      body,
      adjustmentRequestSchema,
      'adjustment request',
      idempotencyKey,
    );
  },
  /** POST /tenant/adjustment-requests/preview: the forecast a decider will see; changes nothing. */
  async preview(body: AdjustmentPreviewIn, signal?: AbortSignal): Promise<AdjustmentPreviewDto> {
    const data = await apiClient.post<unknown>(`${REQUESTS}/preview`, body, {
      tenantScoped: true,
      idempotencyKey: newUuid(),
      ...(signal === undefined ? {} : { signal }),
    });
    return parseResponse(adjustmentPreviewSchema, data, 'adjustment preview');
  },
  /** POST /tenant/adjustment-requests/{id}/decision: never by the proposer. */
  decide(
    id: string,
    body: AdjustmentDecisionIn,
    idempotencyKey: string,
  ): Promise<AdjustmentRequestDto> {
    return tenantSend(
      'post',
      `${REQUESTS}/${seg(id)}/decision`,
      body,
      adjustmentRequestSchema,
      'adjustment request',
      idempotencyKey,
    );
  },
  /** POST /tenant/adjustment-requests/{id}/withdraw: proposer only. */
  withdraw(
    id: string,
    body: AdjustmentWithdrawIn,
    idempotencyKey: string,
  ): Promise<AdjustmentRequestDto> {
    return tenantSend(
      'post',
      `${REQUESTS}/${seg(id)}/withdraw`,
      body,
      adjustmentRequestSchema,
      'adjustment request',
      idempotencyKey,
    );
  },
};
