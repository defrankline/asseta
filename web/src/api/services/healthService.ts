import { mixed, object, string } from 'yup';
import { apiClient } from '../client';
import type { HealthCheck, HealthReadyResponse, HealthStatus } from '../types';
import { parseResponse } from '../validation';
import { ApiError } from '../ApiError';

const statusSchema = mixed<HealthStatus>().oneOf(['ok', 'degraded', 'down']).required();
const checkSchema = object({
  status: mixed<HealthCheck['status']>().oneOf(['ok', 'down']).required(),
  detail: string().nullable().defined(),
});
const envelopeSchema = object({ status: statusSchema, checks: object().required() });

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseHealth(data: unknown): HealthReadyResponse {
  const head = parseResponse(envelopeSchema, data, 'readiness');
  const rawChecks: unknown = isRecord(data) ? data.checks : undefined;
  if (!isRecord(rawChecks)) {
    throw new ApiError({
      status: null,
      code: 'contract_mismatch',
      message: 'Readiness checks missing.',
      correlationId: null,
    });
  }
  const checks: Record<string, HealthCheck> = {};
  for (const [name, value] of Object.entries(rawChecks)) {
    const c = parseResponse(checkSchema, value, `readiness check "${name}"`);
    checks[name] = { status: c.status, detail: c.detail ?? null };
  }
  return { status: head.status, checks };
}

export const healthService = {
  /** Readiness may answer 503 with the same body when degraded; treat it as data, not an error. */
  async getReady(signal?: AbortSignal): Promise<HealthReadyResponse> {
    const data = await apiClient.get<unknown>('/health/ready', {
      acceptStatuses: [503],
      ...(signal ? { signal } : {}),
    });
    return parseHealth(data);
  },
};
