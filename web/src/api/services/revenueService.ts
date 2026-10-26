import { http, type QueryParams } from '../client';
import { requestContext } from '../requestContext';
import type {
  DailyMachineSheetDetailDto,
  DailyMachineSheetRowDto,
  LifecycleChangeIn,
  NonRevenueActivityDto,
  NonRevenueApprovalDto,
  NonRevenueApprovalIn,
  NonRevenueDecisionIn,
  Page,
  RevenueDecisionIn,
  RevenueDifferenceDto,
  RevenueExplanationIn,
  RevenueReasonDto,
  RevenueReasonIn,
  RevenueReasonUpdateIn,
} from '../types';
import { exportError, filenameFromDisposition } from './reportService';
import {
  nonRevenueActivitySchema,
  nonRevenueApprovalSchema,
  revenueDifferenceSchema,
  revenueReasonSchema,
  sheetDetailSchema,
  sheetRowSchema,
} from './revenueSchemas';
import {
  seg,
  tenantGet,
  tenantLifecycle,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const sheetPage = tenantPageSchema(sheetRowSchema);
const differencePage = tenantPageSchema(revenueDifferenceSchema);
const reasonPage = tenantPageSchema(revenueReasonSchema);
const activityPage = tenantPageSchema(nonRevenueActivitySchema);
const approvalPage = tenantPageSchema(nonRevenueApprovalSchema);

const SHEET = '/tenant/daily-machine-sheet';
const DIFFERENCES = '/tenant/revenue-differences';
const REASONS = '/tenant/revenue-reasons';
const APPROVALS = '/tenant/non-revenue-approvals';
const difference = (id: string) => `${DIFFERENCES}/${seg(id)}`;
const reason = (id: string) => `${REASONS}/${seg(id)}`;
const approval = (id: string) => `${APPROVALS}/${seg(id)}`;

/** A downloaded CSV file. */
export interface CsvFile {
  blob: Blob;
  filename: string;
}

/**
 * Revenue reconciliation (DEC-031 R1–R3), all gated by the REVENUE_RECONCILIATION capability: the daily
 * machine sheet, revenue differences (explain / decide), the tenant's revenue reasons and the
 * explanation + approval of non-revenue time inside jobs.
 */
export const revenueService = {
  // --- daily machine sheet ---
  /** GET /tenant/daily-machine-sheet (listDailyMachineSheet). Filters: machine_id, site_id, day_from, day_to (≤ 93 days). */
  listSheet(query: TenantListQuery, signal?: AbortSignal): Promise<Page<DailyMachineSheetRowDto>> {
    return tenantPage(SHEET, sheetPage, query, 'daily machine sheet', signal);
  },
  /** GET /tenant/daily-machine-sheet/{machine_id}/{day} (getDailyMachineSheetDay). */
  sheetDay(
    machineId: string,
    day: string,
    signal?: AbortSignal,
  ): Promise<DailyMachineSheetDetailDto> {
    return tenantGet(
      `${SHEET}/${seg(machineId)}/${seg(day)}`,
      sheetDetailSchema,
      'daily machine sheet day',
      signal,
    );
  },
  /** GET /tenant/daily-machine-sheet/export.csv (exportDailyMachineSheetCsv) with the list's filters. */
  async exportSheetCsv(params: QueryParams): Promise<CsvFile> {
    const response = await http.get<Blob>(`${SHEET}/export.csv`, {
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
    const headers = response.headers as Record<string, unknown>;
    const disposition = headers['content-disposition'];
    return {
      blob: response.data,
      filename: filenameFromDisposition(
        typeof disposition === 'string' ? disposition : null,
        'daily-machine-sheet.csv',
      ),
    };
  },

  // --- revenue differences ---
  /** GET /tenant/revenue-differences (listRevenueDifferences). Filters: status, machine_id, day_from, day_to; q. */
  listDifferences(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<RevenueDifferenceDto>> {
    return tenantPage(DIFFERENCES, differencePage, query, 'revenue differences', signal);
  },
  /** GET /tenant/revenue-differences/{id} (getRevenueDifference). */
  getDifference(differenceId: string, signal?: AbortSignal): Promise<RevenueDifferenceDto> {
    return tenantGet(
      difference(differenceId),
      revenueDifferenceSchema,
      'revenue difference',
      signal,
    );
  },
  /** POST /tenant/revenue-differences/{id}/explanation (explainRevenueDifference): OPEN → EXPLANATION_PROPOSED. */
  explainDifference(
    differenceId: string,
    body: RevenueExplanationIn,
    idempotencyKey: string,
  ): Promise<RevenueDifferenceDto> {
    return tenantSend(
      'post',
      `${difference(differenceId)}/explanation`,
      body,
      revenueDifferenceSchema,
      'revenue difference',
      idempotencyKey,
    );
  },
  /** POST /tenant/revenue-differences/{id}/decision (decideRevenueDifference): APPROVE | REJECT | CONFIRM. */
  decideDifference(
    differenceId: string,
    body: RevenueDecisionIn,
    idempotencyKey: string,
  ): Promise<RevenueDifferenceDto> {
    return tenantSend(
      'post',
      `${difference(differenceId)}/decision`,
      body,
      revenueDifferenceSchema,
      'revenue difference',
      idempotencyKey,
    );
  },

  // --- revenue reasons (tenant list) ---
  /** GET /tenant/revenue-reasons (listRevenueReasons). Filters: include_inactive; q. */
  listReasons(query: TenantListQuery, signal?: AbortSignal): Promise<Page<RevenueReasonDto>> {
    return tenantPage(REASONS, reasonPage, query, 'revenue reasons', signal);
  },
  /** GET /tenant/revenue-reasons/{id} (getRevenueReason). */
  getReason(reasonId: string, signal?: AbortSignal): Promise<RevenueReasonDto> {
    return tenantGet(reason(reasonId), revenueReasonSchema, 'revenue reason', signal);
  },
  /** POST /tenant/revenue-reasons (createRevenueReason). */
  createReason(body: RevenueReasonIn, idempotencyKey: string): Promise<RevenueReasonDto> {
    return tenantSend('post', REASONS, body, revenueReasonSchema, 'revenue reason', idempotencyKey);
  },
  /** PUT /tenant/revenue-reasons/{id} (updateRevenueReason); `version` required. */
  updateReason(
    reasonId: string,
    body: RevenueReasonUpdateIn,
    idempotencyKey: string,
  ): Promise<RevenueReasonDto> {
    return tenantSend(
      'put',
      reason(reasonId),
      body,
      revenueReasonSchema,
      'revenue reason',
      idempotencyKey,
    );
  },
  /** POST /tenant/revenue-reasons/{id}/deactivate (deactivateRevenueReason). */
  deactivateReason(
    reasonId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<RevenueReasonDto> {
    return tenantLifecycle(
      `${reason(reasonId)}/deactivate`,
      body,
      revenueReasonSchema,
      'revenue reason',
      idempotencyKey,
    );
  },
  /** POST /tenant/revenue-reasons/{id}/reactivate (reactivateRevenueReason). */
  reactivateReason(
    reasonId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<RevenueReasonDto> {
    return tenantLifecycle(
      `${reason(reasonId)}/reactivate`,
      body,
      revenueReasonSchema,
      'revenue reason',
      idempotencyKey,
    );
  },

  // --- non-revenue time inside jobs ---
  /** GET /tenant/non-revenue-activities (listNonRevenueActivities). Filters: machine_id, job_id, status NONE|PROPOSED|APPROVED|REJECTED. */
  listActivities(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<NonRevenueActivityDto>> {
    return tenantPage(
      '/tenant/non-revenue-activities',
      activityPage,
      query,
      'non-revenue activities',
      signal,
    );
  },
  /** GET /tenant/non-revenue-approvals (listNonRevenueApprovals). Filters: status, machine_id, job_id; q. */
  listApprovals(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<NonRevenueApprovalDto>> {
    return tenantPage(APPROVALS, approvalPage, query, 'non-revenue approvals', signal);
  },
  /** GET /tenant/non-revenue-approvals/{id} (getNonRevenueApproval). */
  getApproval(approvalId: string, signal?: AbortSignal): Promise<NonRevenueApprovalDto> {
    return tenantGet(
      approval(approvalId),
      nonRevenueApprovalSchema,
      'non-revenue approval',
      signal,
    );
  },
  /** POST /tenant/non-revenue-approvals (proposeNonRevenueApproval): explain one work-log entry. */
  proposeApproval(
    body: NonRevenueApprovalIn,
    idempotencyKey: string,
  ): Promise<NonRevenueApprovalDto> {
    return tenantSend(
      'post',
      APPROVALS,
      body,
      nonRevenueApprovalSchema,
      'non-revenue approval',
      idempotencyKey,
    );
  },
  /** POST /tenant/non-revenue-approvals/{id}/decision (decideNonRevenueApproval). */
  decideApproval(
    approvalId: string,
    body: NonRevenueDecisionIn,
    idempotencyKey: string,
  ): Promise<NonRevenueApprovalDto> {
    return tenantSend(
      'post',
      `${approval(approvalId)}/decision`,
      body,
      nonRevenueApprovalSchema,
      'non-revenue approval',
      idempotencyKey,
    );
  },
};
