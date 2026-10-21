import { isAxiosError } from 'axios';
import type { ErrorDetail, ErrorEnvelope } from './types';

/** Typed error raised by the API layer for every failed request. */
export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string;
  readonly correlationId: string | null;
  readonly details: readonly ErrorDetail[];

  constructor(params: {
    status: number | null;
    code: string;
    message: string;
    correlationId: string | null;
    details?: readonly ErrorDetail[];
  }) {
    super(params.message);
    this.name = 'ApiError';
    this.status = params.status;
    this.code = params.code;
    this.correlationId = params.correlationId;
    this.details = params.details ?? [];
  }

  /** Map of field -> issue for server-side validation errors, suitable for Formik setErrors. */
  fieldErrors(): Record<string, string> {
    const result: Record<string, string> = {};
    for (const d of this.details) {
      const field = d.field ?? null;
      if (field !== null && !(field in result)) result[field] = d.issue;
    }
    return result;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isErrorDetail(value: unknown): value is ErrorDetail {
  return (
    isRecord(value) &&
    (typeof value.field === 'string' || value.field === null) &&
    typeof value.issue === 'string'
  );
}

/** Runtime guard for the backend error envelope. */
export function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!isRecord(value) || !isRecord(value.error)) return false;
  const e = value.error;
  return (
    typeof e.code === 'string' &&
    typeof e.message === 'string' &&
    typeof e.correlation_id === 'string' &&
    Array.isArray(e.details) &&
    e.details.every(isErrorDetail)
  );
}

function headerValue(headers: unknown, name: string): string | null {
  if (!isRecord(headers)) return null;
  const v = headers[name] ?? headers[name.toLowerCase()];
  return typeof v === 'string' ? v : null;
}

/** Convert anything thrown by Axios (or otherwise) into an ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (isAxiosError(error)) {
    const requestCorrelation = headerValue(error.config?.headers, 'X-Correlation-ID');
    const response = error.response;
    if (response === undefined) {
      return new ApiError({
        status: null,
        code: error.code === 'ERR_CANCELED' ? 'request_cancelled' : 'network_error',
        message:
          error.code === 'ERR_CANCELED'
            ? 'Request cancelled.'
            : 'Network error. Check your connection and try again.',
        correlationId: requestCorrelation,
      });
    }
    const data: unknown = response.data;
    if (isErrorEnvelope(data)) {
      return new ApiError({
        status: response.status,
        code: data.error.code,
        message: data.error.message,
        correlationId: data.error.correlation_id,
        details: data.error.details,
      });
    }
    return new ApiError({
      status: response.status,
      code: 'unexpected_response',
      message: `Unexpected response from server (HTTP ${String(response.status)}).`,
      correlationId: headerValue(response.headers, 'x-correlation-id') ?? requestCorrelation,
    });
  }
  return new ApiError({
    status: null,
    code: 'client_error',
    message: error instanceof Error ? error.message : 'Unknown error.',
    correlationId: null,
  });
}

export function isCancelled(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'request_cancelled';
}
