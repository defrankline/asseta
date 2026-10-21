import { ApiError, toApiError } from '../../../api/ApiError';

const HINTS: Readonly<Record<string, string>> = {
  POLICY_BACKDATED: 'Policy changes cannot be backdated; choose now or a future time.',
  POLICY_FIELD_NOT_OVERRIDABLE: 'One or more fields cannot be overridden at this scope.',
  POLICY_UNKNOWN_FIELD: 'The policy does not know one of the fields sent.',
  POLICY_INVALID: 'The resulting policy is invalid (check ranges and live ≤ stale ≤ offline).',
  POLICY_SCOPE: 'The scope or its target is not valid for a tenant policy.',
  POLICY_NOT_CONFIGURED: 'No base policy is configured yet; ask the platform operator.',
};

/** Re-throw an API failure with its stable error code (and a hint) visible to the user. */
export function withPolicyErrorCode(error: unknown): ApiError {
  const e = toApiError(error);
  if (e.status === null) return e;
  const hint = HINTS[e.code];
  return new ApiError({
    status: e.status,
    code: e.code,
    message: `${e.code}: ${e.message}${hint !== undefined ? ` — ${hint}` : ''}`,
    correlationId: e.correlationId,
    details: e.details,
  });
}
