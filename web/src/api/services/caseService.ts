import type {
  AnomalyCaseDetailDto,
  AnomalyCaseDto,
  CaseAssignIn,
  CaseNoteDto,
  CaseNoteIn,
  CaseReopenIn,
  CaseResolveIn,
  Page,
  RiskSignalDto,
} from '../types';
import {
  anomalyCaseDetailSchema,
  anomalyCaseSchema,
  caseNoteSchema,
  riskSignalSchema,
} from './intelligenceSchemas';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const casePageSchema = tenantPageSchema(anomalyCaseSchema);
const signalPageSchema = tenantPageSchema(riskSignalSchema);

/**
 * Investigation cases (ADR-007): evidence from deterministic signals for human review. Commands carry the
 * case `version` read last (STALE_VERSION otherwise) and an Idempotency-Key.
 */
export const caseService = {
  /**
   * GET /tenant/cases (listAnomalyCases). Filters: `status`, `severity`, `assignee_user_id`,
   * `subject_type`, `subject_id`, `machine_id`; `q` searches number and title.
   */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<AnomalyCaseDto>> {
    return tenantPage('/tenant/cases', casePageSchema, query, 'cases', signal);
  },
  /** GET /tenant/cases/{id} (getAnomalyCase): the case with its signals, notes and outcomes. */
  get(caseId: string, signal?: AbortSignal): Promise<AnomalyCaseDetailDto> {
    return tenantGet(`/tenant/cases/${seg(caseId)}`, anomalyCaseDetailSchema, 'case', signal);
  },
  /** POST /tenant/cases/{id}/assign (assignAnomalyCase); never someone whose records are evidence. */
  assign(caseId: string, body: CaseAssignIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `/tenant/cases/${seg(caseId)}/assign`,
      body,
      anomalyCaseDetailSchema,
      'case',
      idempotencyKey,
    );
  },
  /** POST /tenant/cases/{id}/notes (addAnomalyCaseNote): append-only. */
  addNote(caseId: string, body: CaseNoteIn, idempotencyKey: string): Promise<CaseNoteDto> {
    return tenantSend(
      'post',
      `/tenant/cases/${seg(caseId)}/notes`,
      body,
      caseNoteSchema,
      'case note',
      idempotencyKey,
    );
  },
  /** POST /tenant/cases/{id}/resolve (resolveAnomalyCase): records an immutable outcome. */
  resolve(caseId: string, body: CaseResolveIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `/tenant/cases/${seg(caseId)}/resolve`,
      body,
      anomalyCaseDetailSchema,
      'case',
      idempotencyKey,
    );
  },
  /** POST /tenant/cases/{id}/reopen (reopenAnomalyCase) with a reason. */
  reopen(caseId: string, body: CaseReopenIn, idempotencyKey: string) {
    return tenantSend(
      'post',
      `/tenant/cases/${seg(caseId)}/reopen`,
      body,
      anomalyCaseDetailSchema,
      'case',
      idempotencyKey,
    );
  },
};

/** Deterministic risk-signal rule outputs (facts and thresholds only). */
export const riskSignalService = {
  /**
   * GET /tenant/risk-signals (listRiskSignals). Filters: `rule_code`, `severity`, `status`,
   * `subject_type`, `subject_id`, `machine_id`, `observed_from`, `observed_to`.
   */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<RiskSignalDto>> {
    return tenantPage('/tenant/risk-signals', signalPageSchema, query, 'risk signals', signal);
  },
};
