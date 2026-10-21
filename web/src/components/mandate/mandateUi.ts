import { object, string } from 'yup';
import type { StatusTone } from '../display/StatusChip';

export const MANDATE_TONES: Readonly<Record<string, StatusTone>> = {
  IN_FORCE: 'success',
  SCHEDULED: 'info',
  EXPIRED: 'default',
  REVOKED: 'error',
  ENDED: 'default',
};

/** A mandate that can still be ended (platform) or revoked (client). */
export function isOpenMandate(status: string): boolean {
  return status === 'IN_FORCE' || status === 'SCHEDULED';
}

export interface CloseValues {
  reason: string;
}

/** Reason for ending / revoking a mandate: 3..1000 chars, as enforced by the API. */
export const closeSchema = object({
  reason: string()
    .trim()
    .required('A reason is required')
    .min(3, 'The reason must be at least 3 characters')
    .max(1000, 'The reason must be at most 1000 characters'),
});
