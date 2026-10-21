import { array, type Schema } from 'yup';
import { apiClient } from '../client';
import type {
  GatewayCreatedDto,
  GatewayDto,
  GatewayIn,
  LifecycleChangeIn,
  TrackerModelDto,
  TrackerModelIn,
  TrackerModelUpdateIn,
} from '../types';
import { parseResponse } from '../validation';
import { gatewayCreatedSchema, gatewaySchema } from './expenseSchemas';
import { trackerModelSchema } from './trackerSchemas';

const MODELS = '/platform/tracker-models';
const GATEWAYS = '/platform/telemetry-gateways';
const seg = (v: string) => encodeURIComponent(v);

async function get<T>(
  url: string,
  schema: Schema<T>,
  what: string,
  signal?: AbortSignal,
  params?: Record<string, string>,
): Promise<T> {
  const data = await apiClient.get<unknown>(url, {
    ...(signal ? { signal } : {}),
    ...(params !== undefined ? { params } : {}),
  });
  return parseResponse(schema, data, what);
}

async function send<T>(
  method: 'post' | 'put',
  url: string,
  body: unknown,
  schema: Schema<T>,
  what: string,
  idempotencyKey: string,
): Promise<T> {
  const data = await apiClient[method]<unknown>(url, body, { idempotencyKey });
  return parseResponse(schema, data, what);
}

function listParams(q: string | undefined, includeInactive: boolean | undefined) {
  const params: Record<string, string> = {};
  if (q !== undefined && q.trim() !== '') params.q = q.trim();
  if (includeInactive === true) params.include_inactive = 'true';
  return params;
}

/** Platform catalog: approved tracker drivers/models (withdrawn = inactive). */
export const trackerModelService = {
  /** GET /platform/tracker-models (listTrackerModels); withdrawn models only when asked for. */
  list(signal?: AbortSignal, q?: string, includeInactive?: boolean): Promise<TrackerModelDto[]> {
    return get(
      MODELS,
      array(trackerModelSchema).required(),
      'tracker models',
      signal,
      listParams(q, includeInactive),
    );
  },
  /** GET /platform/tracker-models/{id} (getTrackerModel). */
  get(modelId: string, signal?: AbortSignal): Promise<TrackerModelDto> {
    return get(`${MODELS}/${seg(modelId)}`, trackerModelSchema, 'tracker model', signal);
  },
  /** POST /platform/tracker-models (createTrackerModel). */
  create(body: TrackerModelIn, idempotencyKey: string): Promise<TrackerModelDto> {
    return send('post', MODELS, body, trackerModelSchema, 'tracker model', idempotencyKey);
  },
  /** PUT /platform/tracker-models/{id} (updateTrackerModel); the adapter is not editable. */
  update(
    modelId: string,
    body: TrackerModelUpdateIn,
    idempotencyKey: string,
  ): Promise<TrackerModelDto> {
    return send(
      'put',
      `${MODELS}/${seg(modelId)}`,
      body,
      trackerModelSchema,
      'tracker model',
      idempotencyKey,
    );
  },
  /** POST /platform/tracker-models/{id}/deactivate (withdraw: no longer offered to tenants). */
  deactivate(
    modelId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<TrackerModelDto> {
    return send(
      'post',
      `${MODELS}/${seg(modelId)}/deactivate`,
      body,
      trackerModelSchema,
      'tracker model',
      idempotencyKey,
    );
  },
  /** POST /platform/tracker-models/{id}/reactivate (restore to the approved catalog). */
  reactivate(
    modelId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<TrackerModelDto> {
    return send(
      'post',
      `${MODELS}/${seg(modelId)}/reactivate`,
      body,
      trackerModelSchema,
      'tracker model',
      idempotencyKey,
    );
  },
};

/** Platform telemetry gateways (keys are shown once at creation, never listed). */
export const gatewayService = {
  /** GET /platform/telemetry-gateways (listTelemetryGateways). */
  list(signal?: AbortSignal, includeInactive?: boolean): Promise<GatewayDto[]> {
    return get(
      GATEWAYS,
      array(gatewaySchema).required(),
      'telemetry gateways',
      signal,
      listParams(undefined, includeInactive),
    );
  },
  /** GET /platform/telemetry-gateways/{id} (getTelemetryGateway). */
  get(gatewayId: string, signal?: AbortSignal): Promise<GatewayDto> {
    return get(`${GATEWAYS}/${seg(gatewayId)}`, gatewaySchema, 'telemetry gateway', signal);
  },
  /** POST /platform/telemetry-gateways (createTelemetryGateway): returns the key once. */
  create(body: GatewayIn, idempotencyKey: string): Promise<GatewayCreatedDto> {
    return send('post', GATEWAYS, body, gatewayCreatedSchema, 'telemetry gateway', idempotencyKey);
  },
  /** POST /platform/telemetry-gateways/{id}/deactivate: its key stops being accepted. */
  deactivate(
    gatewayId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<GatewayDto> {
    return send(
      'post',
      `${GATEWAYS}/${seg(gatewayId)}/deactivate`,
      body,
      gatewaySchema,
      'telemetry gateway',
      idempotencyKey,
    );
  },
  /** POST /platform/telemetry-gateways/{id}/reactivate. */
  reactivate(
    gatewayId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<GatewayDto> {
    return send(
      'post',
      `${GATEWAYS}/${seg(gatewayId)}/reactivate`,
      body,
      gatewaySchema,
      'telemetry gateway',
      idempotencyKey,
    );
  },
};
