import type { Page } from '../types';
import type {
  AccountabilitySummaryDto,
  SecurityEventDto,
  SyncConflictDto,
  SyncResolutionIn,
} from '../custodyTypes';
import {
  accountabilitySummarySchema,
  securityEventSchema,
  syncConflictSchema,
} from './custodySchemas';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const eventPage = tenantPageSchema(securityEventSchema);
const conflictPage = tenantPageSchema(syncConflictSchema);

/** Oversight (accountability design D): dashboard summary, refused attempts, sync-conflict review. */
export const accountabilityService = {
  /** GET /tenant/accountability/summary (getAccountabilitySummary); hidden tiles are null. */
  summary(signal?: AbortSignal): Promise<AccountabilitySummaryDto> {
    return tenantGet(
      '/tenant/accountability/summary',
      accountabilitySummarySchema,
      'accountability summary',
      signal,
    );
  },
  /**
   * GET /tenant/security-events (listSecurityEvents). Filters: `kind`, `actor_user_id`,
   * `occurred_from`, `occurred_to`; `q` searches permission, action, record type and path.
   */
  securityEvents(query: TenantListQuery, signal?: AbortSignal): Promise<Page<SecurityEventDto>> {
    return tenantPage('/tenant/security-events', eventPage, query, 'security events', signal);
  },
  /** GET /tenant/sync/conflicts (listSyncConflicts). Filters: `status`, `op_type`, `resolved`. */
  syncConflicts(query: TenantListQuery, signal?: AbortSignal): Promise<Page<SyncConflictDto>> {
    return tenantPage('/tenant/sync/conflicts', conflictPage, query, 'sync conflicts', signal);
  },
  /** GET /tenant/sync/conflicts/{id} (getSyncConflict). */
  syncConflict(operationId: string, signal?: AbortSignal): Promise<SyncConflictDto> {
    return tenantGet(
      `/tenant/sync/conflicts/${seg(operationId)}`,
      syncConflictSchema,
      'sync conflict',
      signal,
    );
  },
  /** POST /tenant/sync/conflicts/{id}/resolution (resolveSyncConflict); never the submitter. */
  resolveSyncConflict(
    operationId: string,
    body: SyncResolutionIn,
    idempotencyKey: string,
  ): Promise<SyncConflictDto> {
    return tenantSend(
      'post',
      `/tenant/sync/conflicts/${seg(operationId)}/resolution`,
      body,
      syncConflictSchema,
      'sync conflict',
      idempotencyKey,
    );
  },
};
