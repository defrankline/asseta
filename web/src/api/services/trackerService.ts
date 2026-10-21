import type {
  AssignTrackerIn,
  IngestionEventDto,
  Page,
  TrackerAssignmentDto,
  TrackerDto,
  TrackerIn,
  TrackerModelDto,
  TrackerStateIn,
  UnassignTrackerIn,
} from '../types';
import {
  seg,
  tenantGet,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';
import {
  ingestionEventSchema,
  trackerAssignmentSchema,
  trackerModelSchema,
  trackerSchema,
} from './trackerSchemas';

const trackerPageSchema = tenantPageSchema(trackerSchema);
const ingestionPageSchema = tenantPageSchema(ingestionEventSchema);
const t = (id: string) => `/tenant/trackers/${seg(id)}`;

export const trackerService = {
  /** GET /tenant/trackers (listTrackers). Filter: `state`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<TrackerDto>> {
    return tenantPage('/tenant/trackers', trackerPageSchema, query, 'tracker page', signal);
  },
  /** GET /tenant/trackers/{id} (getTracker). */
  get(trackerId: string, signal?: AbortSignal): Promise<TrackerDto> {
    return tenantGet(t(trackerId), trackerSchema, 'tracker', signal);
  },
  /** POST /tenant/trackers (registerTracker). */
  register(body: TrackerIn, idempotencyKey: string): Promise<TrackerDto> {
    return tenantSend('post', '/tenant/trackers', body, trackerSchema, 'tracker', idempotencyKey);
  },
  /** POST /tenant/trackers/{id}/assign (assignTracker); `replace_existing_primary` swaps. */
  assign(
    trackerId: string,
    body: AssignTrackerIn,
    idempotencyKey: string,
  ): Promise<TrackerAssignmentDto> {
    return tenantSend(
      'post',
      `${t(trackerId)}/assign`,
      body,
      trackerAssignmentSchema,
      'tracker assignment',
      idempotencyKey,
    );
  },
  /** POST /tenant/trackers/{id}/unassign (unassignTracker). */
  unassign(
    trackerId: string,
    body: UnassignTrackerIn,
    idempotencyKey: string,
  ): Promise<TrackerDto> {
    return tenantSend(
      'post',
      `${t(trackerId)}/unassign`,
      body,
      trackerSchema,
      'tracker',
      idempotencyKey,
    );
  },
  /** POST /tenant/trackers/{id}/state (changeTrackerState). */
  changeState(
    trackerId: string,
    body: TrackerStateIn,
    idempotencyKey: string,
  ): Promise<TrackerDto> {
    return tenantSend(
      'post',
      `${t(trackerId)}/state`,
      body,
      trackerSchema,
      'tracker',
      idempotencyKey,
    );
  },
  /** GET /tenant/tracker-models (listApprovedTrackerModels). */
  listModels(signal?: AbortSignal, q?: string): Promise<TrackerModelDto[]> {
    return tenantList('/tenant/tracker-models', trackerModelSchema, 'tracker models', signal, {
      q,
    });
  },
  /** GET /tenant/telemetry/ingestion-events (listIngestionEvents). Filters: `status`, `tracker_id`. */
  listIngestionEvents(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<IngestionEventDto>> {
    return tenantPage(
      '/tenant/telemetry/ingestion-events',
      ingestionPageSchema,
      query,
      'ingestion events',
      signal,
    );
  },
};
