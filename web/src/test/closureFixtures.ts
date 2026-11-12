import { ApiError } from '../api/ApiError';
import type { CompanyDeletionRequestDto } from '../api/services/companyClosureService';
import { TENANT_A } from './fixtures';

export const REQUEST_ID = '44444444-4444-4444-8444-444444444444';

export function makeDeletionRequest(
  overrides: Partial<CompanyDeletionRequestDto> = {},
): CompanyDeletionRequestDto {
  return {
    id: REQUEST_ID,
    tenant_id: TENANT_A,
    tenant_name: 'Tenant A',
    status: 'REQUESTED',
    reason: 'Selling the business',
    requested_by: '33333333-3333-4333-8333-333333333333',
    requested_by_name: 'Ops User',
    requested_at: '2026-11-01T08:00:00Z',
    waiting_days: 30,
    scheduled_for: '2099-12-01T08:00:00Z',
    policy_version: 'v1',
    cancelled_by: null,
    cancelled_by_name: null,
    cancelled_at: null,
    cancel_reason: null,
    execute_now_by: null,
    execute_now_at: null,
    execute_now_reason: null,
    started_at: null,
    completed_at: null,
    attempts: 0,
    last_error: null,
    steps_done: [],
    ...overrides,
  };
}

export function apiError(code: string, message: string, status = 409): ApiError {
  return new ApiError({ status, code, message, correlationId: null });
}
