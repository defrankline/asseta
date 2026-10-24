import type {
  BaselineDto,
  BaselineFromReadingIn,
  BaselineIn,
  ClassificationDto,
  ClassificationIn,
  CorrectionDto,
  CorrectionIn,
  EngineHourReasonDto,
  EngineHourReasonIn,
  EngineHourReasonUpdateIn,
  LifecycleChangeIn,
  MachineEngineHoursDto,
  MachineEngineHoursSummaryDto,
  MeterDecisionIn,
  Page,
  UnallocatedSegmentDto,
} from '../types';
import {
  baselineSchema,
  classificationSchema,
  correctionSchema,
  engineHourReasonSchema,
  machineEngineHoursSchema,
  machineEngineHoursSummarySchema,
  unallocatedSegmentSchema,
} from './engineHoursSchemas';
import {
  seg,
  tenantGet,
  tenantLifecycle,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const baselinePage = tenantPageSchema(baselineSchema);
const reasonPage = tenantPageSchema(engineHourReasonSchema);
const summaryPage = tenantPageSchema(machineEngineHoursSummarySchema);
const unallocatedPage = tenantPageSchema(unallocatedSegmentSchema);
const classificationPage = tenantPageSchema(classificationSchema);
const correctionPage = tenantPageSchema(correctionSchema);

const REASONS = '/tenant/engine-hour-reasons';
const reason = (id: string) => `${REASONS}/${seg(id)}`;

/** Engine-hour accountability (design B): baselines, machine ledger, classifications, corrections, tenant lists. */
export const engineHoursService = {
  // --- baselines ---
  /** GET /tenant/meter-baselines (listMeterBaselines). Filters: `machine_id`, `status`; `q` machine. */
  listBaselines(query: TenantListQuery, signal?: AbortSignal): Promise<Page<BaselineDto>> {
    return tenantPage('/tenant/meter-baselines', baselinePage, query, 'meter baselines', signal);
  },
  /** GET /tenant/meter-baselines/{id} (getMeterBaseline). */
  getBaseline(baselineId: string, signal?: AbortSignal): Promise<BaselineDto> {
    return tenantGet(
      `/tenant/meter-baselines/${seg(baselineId)}`,
      baselineSchema,
      'meter baseline',
      signal,
    );
  },
  /** POST /tenant/meter-baselines (proposeMeterBaseline): a fresh reading with evidence. */
  proposeBaseline(body: BaselineIn, idempotencyKey: string): Promise<BaselineDto> {
    return tenantSend(
      'post',
      '/tenant/meter-baselines',
      body,
      baselineSchema,
      'meter baseline',
      idempotencyKey,
    );
  },
  /** POST /tenant/meter-baselines/from-reading (proposeMeterBaselineFromReading). */
  proposeBaselineFromReading(
    body: BaselineFromReadingIn,
    idempotencyKey: string,
  ): Promise<BaselineDto> {
    return tenantSend(
      'post',
      '/tenant/meter-baselines/from-reading',
      body,
      baselineSchema,
      'meter baseline',
      idempotencyKey,
    );
  },
  /** POST /tenant/meter-baselines/{id}/decision (decideMeterBaseline). */
  decideBaseline(
    baselineId: string,
    body: MeterDecisionIn,
    idempotencyKey: string,
  ): Promise<BaselineDto> {
    return tenantSend(
      'post',
      `/tenant/meter-baselines/${seg(baselineId)}/decision`,
      body,
      baselineSchema,
      'meter baseline',
      idempotencyKey,
    );
  },

  // --- tenant lists ---
  /** GET /tenant/engine-hour-reasons (listEngineHourReasons). Filters: `kind`, `include_inactive`; `q`. */
  listReasons(query: TenantListQuery, signal?: AbortSignal): Promise<Page<EngineHourReasonDto>> {
    return tenantPage(REASONS, reasonPage, query, 'engine-hour reasons', signal);
  },
  /** GET /tenant/engine-hour-reasons/{id} (getEngineHourReason). */
  getReason(reasonId: string, signal?: AbortSignal): Promise<EngineHourReasonDto> {
    return tenantGet(reason(reasonId), engineHourReasonSchema, 'engine-hour reason', signal);
  },
  /** POST /tenant/engine-hour-reasons (createEngineHourReason). */
  createReason(body: EngineHourReasonIn, idempotencyKey: string): Promise<EngineHourReasonDto> {
    return tenantSend(
      'post',
      REASONS,
      body,
      engineHourReasonSchema,
      'engine-hour reason',
      idempotencyKey,
    );
  },
  /** PUT /tenant/engine-hour-reasons/{id} (updateEngineHourReason); `version` required. */
  updateReason(
    reasonId: string,
    body: EngineHourReasonUpdateIn,
    idempotencyKey: string,
  ): Promise<EngineHourReasonDto> {
    return tenantSend(
      'put',
      reason(reasonId),
      body,
      engineHourReasonSchema,
      'engine-hour reason',
      idempotencyKey,
    );
  },
  /** POST /tenant/engine-hour-reasons/{id}/deactivate (deactivateEngineHourReason). */
  deactivateReason(
    reasonId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<EngineHourReasonDto> {
    return tenantLifecycle(
      `${reason(reasonId)}/deactivate`,
      body,
      engineHourReasonSchema,
      'engine-hour reason',
      idempotencyKey,
    );
  },
  /** POST /tenant/engine-hour-reasons/{id}/reactivate (reactivateEngineHourReason). */
  reactivateReason(
    reasonId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<EngineHourReasonDto> {
    return tenantLifecycle(
      `${reason(reasonId)}/reactivate`,
      body,
      engineHourReasonSchema,
      'engine-hour reason',
      idempotencyKey,
    );
  },

  // --- reconciliation ---
  /** GET /tenant/engine-hours/machines (listMachineEngineHours). Filters: `status`; `q` machine. */
  listMachines(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<MachineEngineHoursSummaryDto>> {
    return tenantPage(
      '/tenant/engine-hours/machines',
      summaryPage,
      query,
      'machine engine hours',
      signal,
    );
  },
  /** GET /tenant/engine-hours/machines/{id} (getMachineEngineHours); optional `from` / `to` instants. */
  machine(
    machineId: string,
    range: { from?: string | undefined; to?: string | undefined },
    signal?: AbortSignal,
  ): Promise<MachineEngineHoursDto> {
    return tenantGet(
      `/tenant/engine-hours/machines/${seg(machineId)}`,
      machineEngineHoursSchema,
      'machine engine hours',
      signal,
      { from: range.from, to: range.to },
    );
  },
  /**
   * GET /tenant/engine-hours/unallocated (listUnallocatedEngineHours), oldest first. Filters:
   * `machine_id`, `classification` (default: open items), `min_age_days`.
   */
  listUnallocated(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<UnallocatedSegmentDto>> {
    return tenantPage(
      '/tenant/engine-hours/unallocated',
      unallocatedPage,
      query,
      'unallocated engine hours',
      signal,
    );
  },

  // --- classifications ---
  /** GET /tenant/engine-hours/classifications (listEngineHourClassifications). Filters: `machine_id`, `status`. */
  listClassifications(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<ClassificationDto>> {
    return tenantPage(
      '/tenant/engine-hours/classifications',
      classificationPage,
      query,
      'classifications',
      signal,
    );
  },
  /** POST /tenant/engine-hours/classifications (proposeEngineHourClassification). */
  proposeClassification(
    body: ClassificationIn,
    idempotencyKey: string,
  ): Promise<ClassificationDto> {
    return tenantSend(
      'post',
      '/tenant/engine-hours/classifications',
      body,
      classificationSchema,
      'classification',
      idempotencyKey,
    );
  },
  /** POST /tenant/engine-hours/classifications/{id}/decision (decideEngineHourClassification). */
  decideClassification(
    classificationId: string,
    body: MeterDecisionIn,
    idempotencyKey: string,
  ): Promise<ClassificationDto> {
    return tenantSend(
      'post',
      `/tenant/engine-hours/classifications/${seg(classificationId)}/decision`,
      body,
      classificationSchema,
      'classification',
      idempotencyKey,
    );
  },

  // --- corrections ---
  /** GET /tenant/meter-corrections (listMeterCorrections). Filters: `machine_id`, `status`; `q`. */
  listCorrections(query: TenantListQuery, signal?: AbortSignal): Promise<Page<CorrectionDto>> {
    return tenantPage('/tenant/meter-corrections', correctionPage, query, 'corrections', signal);
  },
  /** POST /tenant/meter-corrections (proposeMeterCorrection): supersede a reading (reason >= 10 chars). */
  proposeCorrection(body: CorrectionIn, idempotencyKey: string): Promise<CorrectionDto> {
    return tenantSend(
      'post',
      '/tenant/meter-corrections',
      body,
      correctionSchema,
      'correction',
      idempotencyKey,
    );
  },
  /** POST /tenant/meter-corrections/{id}/decision (decideMeterCorrection). */
  decideCorrection(
    correctionId: string,
    body: MeterDecisionIn,
    idempotencyKey: string,
  ): Promise<CorrectionDto> {
    return tenantSend(
      'post',
      `/tenant/meter-corrections/${seg(correctionId)}/decision`,
      body,
      correctionSchema,
      'correction',
      idempotencyKey,
    );
  },
};
