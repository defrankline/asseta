import { array, object, type Schema } from 'yup';
import { apiClient, toListParams } from '../client';
import type { components } from '../generated/schema';
import type { ListQuery, Page, TenantDto } from '../types';
import { parseResponse } from '../validation';
import { tenantSchema } from './billingSchemas';
import {
  bool,
  id,
  int,
  nullableId,
  nullableInt,
  nullableText,
  oneOf,
  record,
  text,
} from './schemaKit';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';
import { newUuid } from '../ids';

type Schemas = components['schemas'];
export type DataExportDto = Schemas['DataExportDto'];
export type DownloadLinkDto = Schemas['DownloadLinkDto'];
export type VerificationRunSummaryDto = Schemas['VerificationRunSummaryDto'];
export type VerificationRunDto = Schemas['VerificationRunDto'];
export type VerificationFindingDto = Schemas['VerificationFindingDto'];
export type TenantVerificationDto = Schemas['TenantVerificationDto'];
export type ExportStatus = Schemas['ExportStatus'];
export type ExportFormat = Schemas['ExportFormat'];

const exportStatus = oneOf<ExportStatus>(['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'EXPIRED']);

const exportSchema: Schema<DataExportDto> = object({
  id: id(),
  format: oneOf<ExportFormat>(['CSV', 'JSON']),
  status: exportStatus,
  requested_by: nullableId(),
  requested_at: text(),
  started_at: nullableText(),
  finished_at: nullableText(),
  expires_at: nullableText(),
  sha256: nullableText(),
  size_bytes: nullableInt(),
  table_count: nullableInt(),
  row_count: nullableInt(),
  evidence_count: nullableInt(),
  error_code: nullableText(),
});

const linkSchema: Schema<DownloadLinkDto> = object({ url: text(), expires_in_seconds: int() });

const checkSchema = object({ check: text(), checked: int(), mismatches: int() });

const summaryFields = {
  id: id(),
  tenant_id: id(),
  trigger: oneOf<Schemas['VerificationTrigger']>(['MANUAL', 'SCHEDULED', 'PLATFORM']),
  requested_by: nullableId(),
  started_at: text(),
  finished_at: text(),
  outcome: oneOf<Schemas['VerificationOutcome']>(['MATCHED', 'MISMATCHES']),
  checked_count: int(),
  mismatch_count: int(),
  summary: array(checkSchema).required(),
};

const summarySchema: Schema<VerificationRunSummaryDto> = object(summaryFields);

const findingSchema: Schema<VerificationFindingDto> = object({
  check: text(),
  subject_type: text(),
  subject_id: text(),
  label: text(),
  currency: nullableText(),
  ledger_value: text(),
  stored_value: text(),
  difference: text(),
  source: text(),
  details: record(),
});

const runSchema: Schema<VerificationRunDto> = object({
  ...summaryFields,
  findings: array(findingSchema).required(),
  findings_truncated: bool(),
});

const tenantLineSchema: Schema<TenantVerificationDto> = object({
  tenant_id: id(),
  tenant_name: text(),
  registration_number: nullableText(),
  live_at: nullableText(),
  latest: object(summaryFields).nullable().defined(),
});

const exportPage = tenantPageSchema(exportSchema);
const runPage = tenantPageSchema(summarySchema);
const tenantLinePage = tenantPageSchema(tenantLineSchema);
const EXPORTS = '/tenant/data-exports';
const RUNS = '/tenant/balance-verification/runs';

export const dataProtectionService = {
  listExports(query: TenantListQuery, signal?: AbortSignal): Promise<Page<DataExportDto>> {
    return tenantPage(EXPORTS, exportPage, query, 'data exports', signal);
  },
  requestExport(format: ExportFormat): Promise<DataExportDto> {
    return tenantSend('post', EXPORTS, { format }, exportSchema, 'data export', newUuid());
  },
  /** A short-lived link to the finished ZIP; every request is audited. */
  downloadLink(exportId: string): Promise<DownloadLinkDto> {
    return tenantSend(
      'post',
      `${EXPORTS}/${seg(exportId)}/download`,
      {},
      linkSchema,
      'download link',
      newUuid(),
    );
  },
  listRuns(query: TenantListQuery, signal?: AbortSignal): Promise<Page<VerificationRunSummaryDto>> {
    return tenantPage(RUNS, runPage, query, 'verification runs', signal);
  },
  getRun(runId: string, signal?: AbortSignal): Promise<VerificationRunDto> {
    return tenantGet(`${RUNS}/${seg(runId)}`, runSchema, 'verification run', signal);
  },
  runNow(): Promise<VerificationRunDto> {
    return tenantSend('post', RUNS, {}, runSchema, 'verification run', newUuid());
  },
  /** GET /platform/balance-verification: one line per tenant, counts only. */
  async platformOverview(
    query: ListQuery,
    signal?: AbortSignal,
  ): Promise<Page<TenantVerificationDto>> {
    const data = await apiClient.get<unknown>('/platform/balance-verification', {
      params: toListParams(query),
      ...(signal ? { signal } : {}),
    });
    return parseResponse(tenantLinePage, data, 'tenant verification page');
  },
  async platformRun(tenantId: string, idempotencyKey: string): Promise<VerificationRunSummaryDto> {
    const data = await apiClient.post<unknown>(
      `/platform/tenants/${encodeURIComponent(tenantId)}/balance-verification`,
      {},
      { idempotencyKey },
    );
    return parseResponse(summarySchema, data, 'verification run');
  },
  /** POST /platform/tenants/{id}/go-live (markTenantLive): the reset tool then refuses this tenant. */
  async markLive(
    tenantId: string,
    body: { confirm_name: string; note: string | null },
    idempotencyKey: string,
  ): Promise<TenantDto> {
    const data = await apiClient.post<unknown>(
      `/platform/tenants/${encodeURIComponent(tenantId)}/go-live`,
      body,
      { idempotencyKey },
    );
    return parseResponse(tenantSchema, data, 'tenant');
  },
};
