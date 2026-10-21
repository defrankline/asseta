import { ApiError, toApiError } from '../../../api/ApiError';

/**
 * Re-throw an API failure with its stable error code (and an optional hint) visible to the user,
 * e.g. `OPENING_REQUIRED: An opening meter reading is required to start — Record the opening …`.
 */
export function withErrorCode(error: unknown, hints: Readonly<Record<string, string>>): ApiError {
  const e = toApiError(error);
  if (e.status === null) return e;
  const hint = hints[e.code];
  return new ApiError({
    status: e.status,
    code: e.code,
    message: `${e.code}: ${e.message}${hint !== undefined ? ` — ${hint}` : ''}`,
    correlationId: e.correlationId,
    details: e.details,
  });
}
