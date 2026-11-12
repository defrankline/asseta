import type { DeletionStatus } from '../../../api/services/companyClosureService';
import type { StatusTone } from '../../../components/display/StatusChip';

export const DELETION_STATUS_LABELS: Readonly<Record<DeletionStatus, string>> = {
  REQUESTED: 'Closure requested',
  CANCELLED: 'Cancelled',
  IN_PROGRESS: 'Deletion in progress',
  COMPLETED: 'Deleted',
};

export const DELETION_STATUS_TONES: Readonly<Record<DeletionStatus, StatusTone>> = {
  REQUESTED: 'warning',
  CANCELLED: 'default',
  IN_PROGRESS: 'info',
  COMPLETED: 'error',
};

export const CLOSE_ERROR_HINTS: Readonly<Record<string, string>> = {
  CONFIRMATION_MISMATCH: "The name typed does not match the company's name.",
  DELETION_ALREADY_REQUESTED: 'A closure has already been requested for this company.',
  TENANT_CLOSED: 'This company is already closed.',
  MANDATE_NOT_ALLOWED:
    "Only the company's own owners can close it; access under a managed-service mandate cannot.",
};

export const CANCEL_ERROR_HINTS: Readonly<Record<string, string>> = {
  NO_DELETION_REQUEST: 'There is no closure request to cancel. Reload to see the latest state.',
  DELETION_IN_PROGRESS: 'The deletion has already started and can no longer be cancelled.',
};

/** Case-insensitive, surrounding spaces ignored (the server compares the same way). */
export function nameMatches(typed: string, companyName: string): boolean {
  const a = typed.trim().toLocaleLowerCase();
  return a !== '' && a === companyName.trim().toLocaleLowerCase();
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** Whole days until `scheduledFor` (0 once it is due), or null for an unreadable date. */
export function daysLeft(scheduledFor: string, nowMs: number): number | null {
  const t = Date.parse(scheduledFor);
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.ceil((t - nowMs) / DAY_MS));
}

export function daysLeftText(days: number | null): string {
  if (days === null) return '';
  if (days === 0) return 'due now';
  return days === 1 ? '1 day left' : `${String(days)} days left`;
}

/** The deletion steps in the order the worker runs them (backend STEP_ORDER). */
export const DELETION_STEPS: readonly { code: string; label: string }[] = [
  { code: 'snapshot', label: 'Record what is deleted' },
  { code: 'subscription', label: 'Cancel the subscription' },
  { code: 'identity', label: 'Remove sign-in groups and accounts' },
  { code: 'objects', label: 'Delete stored files' },
  { code: 'traccar', label: 'Remove tracker devices' },
  { code: 'database', label: 'Delete company records' },
];

/** A deletion step code as plain words (unknown codes are humanised). */
export function stepLabel(step: string): string {
  const known = DELETION_STEPS.find((s) => s.code === step);
  if (known !== undefined) return known.label;
  const words = step.replace(/[_.:-]+/g, ' ').trim();
  return words === '' ? step : words.charAt(0).toUpperCase() + words.slice(1);
}
