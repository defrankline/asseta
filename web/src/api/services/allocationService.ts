import type {
  AllocationCorrectionDto,
  AllocationCorrectionIn,
  AllocationDayDto,
  DailyReportDto,
  DailyReportIn,
  DailyReportPrefillDto,
  DailyReportReviewIn,
  WorkAllocationDto,
} from '../allocationTypes';
import type { MeterDecisionIn, Page } from '../types';
import {
  allocationCorrectionSchema,
  allocationDaySchema,
  dailyReportPrefillSchema,
  dailyReportSchema,
  workAllocationSchema,
} from './allocationSchemas';
import {
  seg,
  tenantGet,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const ALLOCATIONS = '/tenant/work-allocations';
const REPORTS = '/tenant/daily-reports';
const allocationPage = tenantPageSchema(workAllocationSchema);
const reportPage = tenantPageSchema(dailyReportSchema);

/** The work allocation ledger ("Ledger 3") and daily operational reports (DEC-032 A1, A4). */
export const allocationService = {
  /** GET /tenant/work-allocations; filters `machine_id`, `from`, `to`, `customer_id`, `kind`, `status`, `job_id`. */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<WorkAllocationDto>> {
    return tenantPage(ALLOCATIONS, allocationPage, query, 'work allocations', signal);
  },
  /** GET /tenant/work-allocations/{id}. */
  get(id: string, signal?: AbortSignal): Promise<WorkAllocationDto> {
    return tenantGet(`${ALLOCATIONS}/${seg(id)}`, workAllocationSchema, 'work allocation', signal);
  },
  /** GET /tenant/work-allocations/reconciliation: per machine and day (at most 93 days). */
  reconciliation(
    params: { from: string; to: string; machine_id?: string | undefined },
    signal?: AbortSignal,
  ): Promise<AllocationDayDto[]> {
    return tenantList(
      `${ALLOCATIONS}/reconciliation`,
      allocationDaySchema,
      'allocation reconciliation',
      signal,
      params,
    );
  },
  /** POST /tenant/work-allocations/{id}/corrections: parts must total the entry's hours. */
  proposeCorrection(
    id: string,
    body: AllocationCorrectionIn,
    idempotencyKey: string,
  ): Promise<AllocationCorrectionDto> {
    return tenantSend(
      'post',
      `${ALLOCATIONS}/${seg(id)}/corrections`,
      body,
      allocationCorrectionSchema,
      'allocation correction',
      idempotencyKey,
    );
  },
  /** GET /tenant/work-allocations/corrections/{group_id}. */
  getCorrection(groupId: string, signal?: AbortSignal): Promise<AllocationCorrectionDto> {
    return tenantGet(
      `${ALLOCATIONS}/corrections/${seg(groupId)}`,
      allocationCorrectionSchema,
      'allocation correction',
      signal,
    );
  },
  /** POST /tenant/work-allocations/corrections/{group_id}/decision. */
  decideCorrection(
    groupId: string,
    body: MeterDecisionIn,
    idempotencyKey: string,
  ): Promise<AllocationCorrectionDto> {
    return tenantSend(
      'post',
      `${ALLOCATIONS}/corrections/${seg(groupId)}/decision`,
      body,
      allocationCorrectionSchema,
      'allocation correction',
      idempotencyKey,
    );
  },

  /** GET /tenant/daily-reports; filters `machine_id`, `from`, `to`, `status`; `q` machine. */
  listReports(query: TenantListQuery, signal?: AbortSignal): Promise<Page<DailyReportDto>> {
    return tenantPage(REPORTS, reportPage, query, 'daily reports', signal);
  },
  /** GET /tenant/daily-reports/{id}. */
  getReport(id: string, signal?: AbortSignal): Promise<DailyReportDto> {
    return tenantGet(`${REPORTS}/${seg(id)}`, dailyReportSchema, 'daily report', signal);
  },
  /** GET /tenant/daily-reports/prefill: the day's readings and allocations. */
  prefillReport(
    machineId: string,
    reportDate: string,
    signal?: AbortSignal,
  ): Promise<DailyReportPrefillDto> {
    return tenantGet(
      `${REPORTS}/prefill`,
      dailyReportPrefillSchema,
      'daily report prefill',
      signal,
      { machine_id: machineId, report_date: reportDate },
    );
  },
  /** POST /tenant/daily-reports (`id` is the report's own id; a retry is the same report). */
  submitReport(body: DailyReportIn, idempotencyKey: string): Promise<DailyReportDto> {
    return tenantSend('post', REPORTS, body, dailyReportSchema, 'daily report', idempotencyKey);
  },
  /** POST /tenant/daily-reports/{id}/review. */
  reviewReport(
    id: string,
    body: DailyReportReviewIn,
    idempotencyKey: string,
  ): Promise<DailyReportDto> {
    return tenantSend(
      'post',
      `${REPORTS}/${seg(id)}/review`,
      body,
      dailyReportSchema,
      'daily report',
      idempotencyKey,
    );
  },
};
