import type { Schema } from 'yup';
import { apiClient, toListParams } from '../client';
import type {
  MlDriftDto,
  MlInferenceAuditDto,
  MlModelActionIn,
  MlModelVersionDetailDto,
  MlModelVersionDto,
  MlPredictionDto,
  MlReadinessDto,
  MlSettingsDto,
  MlSettingsIn,
  MlSnapshotRunDto,
  MlSnapshotRunIn,
  MlTrainingRunDto,
  Page,
} from '../types';
import { parseResponse } from '../validation';
import { pageSchema } from './billingSchemas';
import {
  mlDriftSchema,
  mlInferenceAuditSchema,
  mlModelDetailSchema,
  mlModelVersionSchema,
  mlPredictionSchema,
  mlReadinessSchema,
  mlSettingsSchema,
  mlSnapshotRunSchema,
  mlTrainingRunSchema,
} from './mlSchemas';

const BASE = '/platform/ml';
const seg = (v: string) => encodeURIComponent(v);

/** Paged platform query: page, size and server filters (empty values dropped). */
export interface MlListQuery {
  page: number;
  page_size: number;
  filters?: Readonly<Record<string, string | undefined>>;
}

/** Lifecycle actions with their endpoint path (backend `_action_route`). */
export type MlLifecycleAction =
  'APPROVE' | 'REJECT' | 'DEPLOY_SHADOW' | 'DEPLOY_ACTIVE' | 'ROLLBACK' | 'DISABLE' | 'RETIRE';

const ACTION_PATHS: Readonly<Record<MlLifecycleAction, string>> = {
  APPROVE: 'approve',
  REJECT: 'reject',
  DEPLOY_SHADOW: 'deploy-shadow',
  DEPLOY_ACTIVE: 'deploy-active',
  ROLLBACK: 'rollback',
  DISABLE: 'disable',
  RETIRE: 'retire',
};

async function getPage<T>(
  url: string,
  item: Schema<T>,
  query: MlListQuery,
  what: string,
  signal?: AbortSignal,
): Promise<Page<T>> {
  const data = await apiClient.get<unknown>(url, {
    params: toListParams(query),
    ...(signal ? { signal } : {}),
  });
  return parseResponse(pageSchema(item), data, what);
}

/**
 * ML governance for platform staff (ADR-007): model versions with evaluation vs baseline, lifecycle
 * actions (reason + `lock_version` + Idempotency-Key), the inference hard switch, readiness,
 * monitoring lists and the bounded snapshot / training triggers.
 */
export const platformMlService = {
  /** GET /platform/ml/models (listMlModelVersions). Filters: `tenant_id`, `status`, `name`. */
  listModels(query: MlListQuery, signal?: AbortSignal): Promise<Page<MlModelVersionDto>> {
    return getPage(`${BASE}/models`, mlModelVersionSchema, query, 'model versions', signal);
  },
  /** GET /platform/ml/models/{id} (getMlModelVersion): evaluation, approvals, drift, monitoring. */
  async getModel(modelId: string, signal?: AbortSignal): Promise<MlModelVersionDetailDto> {
    const data = await apiClient.get<unknown>(`${BASE}/models/${seg(modelId)}`, {
      ...(signal ? { signal } : {}),
    });
    return parseResponse(mlModelDetailSchema, data, 'model version');
  },
  /** POST /platform/ml/models/{id}/{action}: one audited lifecycle decision with a reason. */
  async act(
    modelId: string,
    action: MlLifecycleAction,
    body: MlModelActionIn,
    idempotencyKey: string,
  ): Promise<MlModelVersionDetailDto> {
    const data = await apiClient.post<unknown>(
      `${BASE}/models/${seg(modelId)}/${ACTION_PATHS[action]}`,
      body,
      { idempotencyKey },
    );
    return parseResponse(mlModelDetailSchema, data, 'model version');
  },
  /** GET /platform/ml/models/{id}/drift (listMlModelDrift): PSI checks, newest first. */
  listDrift(modelId: string, query: MlListQuery, signal?: AbortSignal): Promise<Page<MlDriftDto>> {
    return getPage(`${BASE}/models/${seg(modelId)}/drift`, mlDriftSchema, query, 'drift', signal);
  },
  /**
   * GET /platform/ml/predictions (listMlPredictions). Filters: `model_version_id`, `tenant_id`,
   * `decision_state`, `subject_id`.
   */
  listPredictions(query: MlListQuery, signal?: AbortSignal): Promise<Page<MlPredictionDto>> {
    return getPage(`${BASE}/predictions`, mlPredictionSchema, query, 'predictions', signal);
  },
  /** GET /platform/ml/inference-audit. Filters: `model_version_id`, `tenant_id`, `outcome`. */
  listInferenceAudit(query: MlListQuery, signal?: AbortSignal): Promise<Page<MlInferenceAuditDto>> {
    return getPage(`${BASE}/inference-audit`, mlInferenceAuditSchema, query, 'runs', signal);
  },
  /** GET /platform/ml/readiness (listMlReadiness): latest per tenant. Filters: `status`, `tenant_id`. */
  listReadiness(query: MlListQuery, signal?: AbortSignal): Promise<Page<MlReadinessDto>> {
    return getPage(`${BASE}/readiness`, mlReadinessSchema, query, 'readiness', signal);
  },
  /** GET /platform/ml/settings (getMlSettings): the platform-wide inference switch. */
  async getSettings(signal?: AbortSignal): Promise<MlSettingsDto> {
    const data = await apiClient.get<unknown>(`${BASE}/settings`, {
      ...(signal ? { signal } : {}),
    });
    return parseResponse(mlSettingsSchema, data, 'ML settings');
  },
  /** PUT /platform/ml/settings (updateMlSettings): reason required; `lock_version` as read. */
  async updateSettings(body: MlSettingsIn, idempotencyKey: string): Promise<MlSettingsDto> {
    const data = await apiClient.put<unknown>(`${BASE}/settings`, body, { idempotencyKey });
    return parseResponse(mlSettingsSchema, data, 'ML settings');
  },
  /** POST /platform/ml/tenants/{id}/snapshots (runMlSnapshots): <= 26 week ends per call. */
  async runSnapshots(
    tenantId: string,
    body: MlSnapshotRunIn,
    idempotencyKey: string,
  ): Promise<MlSnapshotRunDto> {
    const data = await apiClient.post<unknown>(`${BASE}/tenants/${seg(tenantId)}/snapshots`, body, {
      idempotencyKey,
    });
    return parseResponse(mlSnapshotRunSchema, data, 'snapshot run');
  },
  /** POST /platform/ml/tenants/{id}/train (runMlTraining): readiness and, when ready, a new version. */
  async runTraining(tenantId: string, idempotencyKey: string): Promise<MlTrainingRunDto> {
    const data = await apiClient.post<unknown>(
      `${BASE}/tenants/${seg(tenantId)}/train`,
      {},
      { idempotencyKey },
    );
    return parseResponse(mlTrainingRunSchema, data, 'training run');
  },
};
