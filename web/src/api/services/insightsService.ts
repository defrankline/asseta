import { toListParams } from '../client';
import type {
  ManualOverrideReportDto,
  Page,
  TenantInsightsDto,
  TenantMlStatusDto,
  TenantPredictionDto,
} from '../types';
import {
  manualOverrideReportSchema,
  tenantInsightsSchema,
  tenantMlStatusSchema,
  tenantPredictionSchema,
} from './mlSchemas';
import { tenantGet, tenantPage, tenantPageSchema, type TenantListQuery } from './tenantRequest';

const predictionPageSchema = tenantPageSchema(tenantPredictionSchema);

/**
 * Tenant baseline insights and the plain-language model status (ADR-007). Nothing here carries a
 * model score: insights compare a machine with its own history and observations are neutral text.
 */
export const insightsService = {
  /**
   * GET /tenant/insights (getTenantInsights): fuel efficiency and utilisation per machine; cash flow
   * only with `tenant.finance.report` (null otherwise). Items are READY or INSUFFICIENT_DATA.
   */
  get(signal?: AbortSignal): Promise<TenantInsightsDto> {
    return tenantGet('/tenant/insights', tenantInsightsSchema, 'insights', signal);
  },
  /**
   * GET /tenant/insights/manual-overrides (listManualOverrides, `tenant.meter.read`): OCR value vs
   * entered value. Filters: `captured_from` (inclusive), `captured_to` (exclusive), `machine_id`,
   * `user_id`.
   */
  manualOverrides(query: TenantListQuery, signal?: AbortSignal): Promise<ManualOverrideReportDto> {
    return tenantGet(
      '/tenant/insights/manual-overrides',
      manualOverrideReportSchema,
      'manual overrides',
      signal,
      toListParams(query),
    );
  },
};

export const tenantMlService = {
  /** GET /tenant/ml/status (getTenantMlStatus, `tenant.signal.read`): state, label and reasons. */
  status(signal?: AbortSignal): Promise<TenantMlStatusDto> {
    return tenantGet('/tenant/ml/status', tenantMlStatusSchema, 'model status', signal);
  },
  /**
   * GET /tenant/ml/predictions (listTenantPredictions, `tenant.case.read`): surfaced observations
   * only, as neutral text with the case to review. Filter: `machine_id`.
   */
  observations(query: TenantListQuery, signal?: AbortSignal): Promise<Page<TenantPredictionDto>> {
    return tenantPage(
      '/tenant/ml/predictions',
      predictionPageSchema,
      query,
      'observations',
      signal,
    );
  },
};
