import type {
  AvailableHoursDto,
  MachineReportContextDto,
  MachineReportDecisionIn,
  MachineReportDto,
  MachineReportIn,
  MachineReportReasonDto,
  MachineReportReasonIn,
  MachineReportReasonUpdateIn,
  MachineReportRejectIn,
  MachineReportStatusDto,
} from '../machineReportTypes';
import type { LifecycleChangeIn, Page } from '../types';
import {
  availableHoursSchema,
  machineReportContextSchema,
  machineReportReasonSchema,
  machineReportSchema,
  machineReportStatusSchema,
} from './machineReportSchemas';
import {
  inactiveParam,
  seg,
  tenantGet,
  tenantLifecycle,
  tenantList,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const R = '/tenant/machine-reports';
const REASONS = '/tenant/machine-report-reasons';
const reportPage = tenantPageSchema(machineReportSchema);

/** Machine reports (ADR-008): submit, read, approve / reject (never your own), status, context. */
export const machineReportService = {
  /**
   * GET /tenant/machine-reports (listMachineReports). Filters: `machine_id`, `status`,
   * `queue=PENDING`, `customer_id`, `mine=true`, `date_from`, `date_to`.
   */
  list(query: TenantListQuery, signal?: AbortSignal): Promise<Page<MachineReportDto>> {
    return tenantPage(R, reportPage, query, 'machine reports', signal);
  },
  /** GET /tenant/machine-reports/{id} (getMachineReport): findings and the tracker cross-check. */
  get(reportId: string, signal?: AbortSignal): Promise<MachineReportDto> {
    return tenantGet(`${R}/${seg(reportId)}`, machineReportSchema, 'machine report', signal);
  },
  /** POST /tenant/machine-reports (submitMachineReport). */
  submit(body: MachineReportIn, idempotencyKey: string): Promise<MachineReportDto> {
    return tenantSend('post', R, body, machineReportSchema, 'machine report', idempotencyKey);
  },
  /** POST /tenant/machine-reports/{id}/approve (approveMachineReport). */
  approve(
    reportId: string,
    body: MachineReportDecisionIn,
    idempotencyKey: string,
  ): Promise<MachineReportDto> {
    return tenantSend(
      'post',
      `${R}/${seg(reportId)}/approve`,
      body,
      machineReportSchema,
      'machine report',
      idempotencyKey,
    );
  },
  /** POST /tenant/machine-reports/{id}/reject (rejectMachineReport): the reason is required. */
  reject(
    reportId: string,
    body: MachineReportRejectIn,
    idempotencyKey: string,
  ): Promise<MachineReportDto> {
    return tenantSend(
      'post',
      `${R}/${seg(reportId)}/reject`,
      body,
      machineReportSchema,
      'machine report',
      idempotencyKey,
    );
  },
  /** GET /tenant/machine-reports/status (listMachineReportStatus): field users see their machines. */
  status(machineId?: string, signal?: AbortSignal): Promise<MachineReportStatusDto[]> {
    return tenantList(`${R}/status`, machineReportStatusSchema, 'machine report status', signal, {
      machine_id: machineId,
    });
  },
  /** GET /tenant/machine-reports/context/{machine_id} (getMachineReportContext): the form's first step. */
  context(machineId: string, signal?: AbortSignal): Promise<MachineReportContextDto> {
    return tenantGet(
      `${R}/context/${seg(machineId)}`,
      machineReportContextSchema,
      'machine report context',
      signal,
    );
  },
  /** GET /tenant/machine-reports/available-hours (listReportHours). */
  availableHours(
    query: { machine_id?: string | undefined; customer_id?: string | undefined },
    signal?: AbortSignal,
  ): Promise<AvailableHoursDto[]> {
    return tenantList(`${R}/available-hours`, availableHoursSchema, 'available hours', signal, {
      machine_id: query.machine_id,
      customer_id: query.customer_id,
    });
  },
};

/** The machine-report reason list (non-productive hours): list, add, edit, deactivate, reactivate. */
export const machineReportReasonService = {
  /** GET /tenant/machine-report-reasons (listMachineReportReasons). */
  list(includeInactive: boolean, signal?: AbortSignal): Promise<MachineReportReasonDto[]> {
    return tenantList(
      REASONS,
      machineReportReasonSchema,
      'machine report reasons',
      signal,
      inactiveParam(includeInactive),
    );
  },
  create(body: MachineReportReasonIn, idempotencyKey: string): Promise<MachineReportReasonDto> {
    return tenantSend('post', REASONS, body, machineReportReasonSchema, 'reason', idempotencyKey);
  },
  update(
    reasonId: string,
    body: MachineReportReasonUpdateIn,
    idempotencyKey: string,
  ): Promise<MachineReportReasonDto> {
    return tenantSend(
      'put',
      `${REASONS}/${seg(reasonId)}`,
      body,
      machineReportReasonSchema,
      'reason',
      idempotencyKey,
    );
  },
  deactivate(
    reasonId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<MachineReportReasonDto> {
    return tenantLifecycle(
      `${REASONS}/${seg(reasonId)}/deactivate`,
      body,
      machineReportReasonSchema,
      'reason',
      idempotencyKey,
    );
  },
  reactivate(
    reasonId: string,
    body: LifecycleChangeIn,
    idempotencyKey: string,
  ): Promise<MachineReportReasonDto> {
    return tenantLifecycle(
      `${REASONS}/${seg(reasonId)}/reactivate`,
      body,
      machineReportReasonSchema,
      'reason',
      idempotencyKey,
    );
  },
};
