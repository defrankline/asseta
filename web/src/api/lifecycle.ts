import { ApiError, toApiError } from './ApiError';
import type { LifecycleChangeIn } from './types';

/**
 * Record lifecycle conventions shared by every managed entity. Records with history are never
 * hard-deleted: "Delete" in the UI is a deactivation (or the domain equivalent: retire, close,
 * cancel, decommission) that records a reason and can be undone by a reactivation.
 */

/**
 * Body of a lifecycle action (`…/{id}/deactivate`, `…/reactivate`, `…/close`, `…/reopen`):
 * `reason` (3–500 characters) and the optional `version` that was read.
 */
export type LifecycleReasonIn = LifecycleChangeIn;

/** Reason length accepted by every lifecycle endpoint. */
export const REASON_MIN = 3;
export const REASON_MAX = 500;

/** Signature of a service call that performs one lifecycle action on a record. */
export type LifecycleCall<T> = (
  id: string,
  body: LifecycleReasonIn,
  idempotencyKey: string,
) => Promise<T>;

/** The record was changed by someone else since it was read; nothing was overwritten. */
export const STALE_VERSION = 'STALE_VERSION';

export function isStaleVersion(error: unknown): boolean {
  return error instanceof ApiError && error.code === STALE_VERSION;
}

/** List query parameter that includes deactivated records (hidden by default). */
export const INCLUDE_INACTIVE_PARAM = 'include_inactive';

/** Server filter for a "Show inactive" toggle: sends `include_inactive=true` only when on. */
export function inactiveFilter(showInactive: boolean): Record<string, string | undefined> {
  return { [INCLUDE_INACTIVE_PARAM]: showInactive ? 'true' : undefined };
}

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
