import { array, object, string, type Schema } from 'yup';
import { ApiError, isErrorEnvelope } from '../ApiError';
import { apiClient, http, MANDATE_LOST_CODES, type QueryParams } from '../client';
import { requestContext } from '../requestContext';
import type { ReportColumnDto, ReportDefinitionDto } from '../types';
import { parseResponse } from '../validation';
import { int, text } from './schemaKit';

export type ReportConsole = 'tenant' | 'platform';
export type ReportFormat = 'csv' | 'pdf';

const columnSchema: Schema<ReportColumnDto> = object({ key: text(), label: text(), kind: text() });

const definitionSchema: Schema<ReportDefinitionDto> = object({
  code: text(),
  title: text(),
  description: text(),
  formats: array(string().required()).required(),
  csv_path: text(),
  pdf_path: text(),
  list_operation: text(),
  filters: array(string().required()).required(),
  columns: array(columnSchema).required(),
  csv_row_cap: int(),
  pdf_row_cap: int(),
});

const definitionsSchema = array(definitionSchema).required();

/** A downloaded export: the file plus the server's row count and truncation flag. */
export interface ReportFile {
  blob: Blob;
  filename: string;
  rows: number | null;
  truncated: boolean;
}

/** `attachment; filename="asseta-jobs-2026-10-22.csv"` (or RFC 5987 `filename*=`) → the file name. */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (header === null || header === '') return fallback;
  const star = /filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i.exec(header);
  if (star?.[1] !== undefined) {
    try {
      return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ''));
    } catch {
      // fall through to the plain parameter
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(header);
  return plain?.[1]?.trim() ?? fallback;
}

function header(headers: unknown, name: string): string | null {
  if (typeof headers !== 'object' || headers === null) return null;
  const record = headers as Record<string, unknown>;
  const value = record[name.toLowerCase()] ?? record[name];
  return typeof value === 'string' ? value : null;
}

/** Turns an error body that arrived as a Blob (responseType blob) into an ApiError. */
export async function exportError(status: number, data: unknown): Promise<ApiError> {
  let parsed: unknown;
  try {
    const raw = data instanceof Blob ? await data.text() : data;
    parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch {
    parsed = null;
  }
  if (isErrorEnvelope(parsed)) {
    return new ApiError({
      status,
      code: parsed.error.code,
      message: parsed.error.message,
      correlationId: parsed.error.correlation_id,
      details: parsed.error.details,
    });
  }
  return new ApiError({
    status,
    code: 'export_failed',
    message: `The export could not be produced (HTTP ${String(status)}).`,
    correlationId: null,
  });
}

/** Report definitions per console + tenant, fetched once per page session. */
const definitionCache = new Map<string, Promise<ReportDefinitionDto[]>>();

export function resetReportDefinitionCache(): void {
  definitionCache.clear();
}

export const reportService = {
  /** GET /{console}/reports: only the reports the caller may export. Cached per `cacheKey`. */
  listDefinitions(console: ReportConsole, cacheKey: string): Promise<ReportDefinitionDto[]> {
    const key = `${console}:${cacheKey}`;
    const known = definitionCache.get(key);
    if (known !== undefined) return known;
    const request = apiClient
      .get<unknown>(`/${console}/reports`, { tenantScoped: console === 'tenant' })
      .then((data) => parseResponse(definitionsSchema, data, 'report definitions'));
    definitionCache.set(key, request);
    request.catch(() => definitionCache.delete(key));
    return request;
  },

  /**
   * GET /{console}/reports/{code}.{format} with the page's filters, through the authenticated
   * client (bearer token, tenant header); the body is returned as a Blob.
   */
  async download(
    console: ReportConsole,
    code: string,
    format: ReportFormat,
    params: QueryParams,
  ): Promise<ReportFile> {
    const response = await http.get<Blob>(
      `/${console}/reports/${encodeURIComponent(code)}.${format}`,
      {
        params,
        responseType: 'blob',
        tenantScoped: console === 'tenant',
        validateStatus: () => true,
      },
    );
    if (response.status < 200 || response.status >= 300) {
      const error = await exportError(response.status, response.data);
      // Statuses are read here (blob body), so give the session the same signals the interceptor would:
      // an expired session goes to sign-in, a lost mandate leaves the client's console.
      if (error.status === 401) requestContext.onUnauthorized();
      if (MANDATE_LOST_CODES.has(error.code)) {
        requestContext.onMandateLost(
          console === 'tenant' ? requestContext.getActiveTenantId() : null,
          error.code,
        );
      }
      throw error;
    }
    const rows = header(response.headers, 'X-Report-Rows');
    return {
      blob: response.data,
      filename: filenameFromDisposition(
        header(response.headers, 'Content-Disposition'),
        `asseta-${code}.${format}`,
      ),
      rows: rows === null || Number.isNaN(Number(rows)) ? null : Number(rows),
      truncated: header(response.headers, 'X-Report-Truncated') === 'true',
    };
  },
};
