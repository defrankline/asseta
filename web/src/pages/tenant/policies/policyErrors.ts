import type { ApiError } from '../../../api/ApiError';
import { withErrorCode } from '../shared/errorHints';

const HINTS: Readonly<Record<string, string>> = {
  POLICY_BACKDATED: 'Policy changes cannot be backdated; choose now or a future time.',
  POLICY_FIELD_NOT_OVERRIDABLE: 'One or more fields cannot be overridden at this scope.',
  POLICY_UNKNOWN_FIELD: 'The policy does not know one of the fields sent.',
  POLICY_INVALID: 'The resulting policy is invalid (check ranges and ordering rules).',
  POLICY_SCOPE: 'The scope or its target is not valid for a tenant policy.',
  POLICY_NOT_CONFIGURED: 'No base policy is configured yet; ask the platform operator.',
  MANAGED_SERVICE_MANDATE_ACTIVE:
    'The managed service page cannot be switched off while a managed-service mandate is open. End the mandate first.',
  MANAGED_SERVICE_SWITCH_LOCKED:
    'People working under a managed-service mandate cannot change this switch. Someone from your own company must change it.',
};

/** Re-throw an API failure with its stable error code (and a hint) visible to the user. */
export function withPolicyErrorCode(error: unknown): ApiError {
  return withErrorCode(error, HINTS);
}
