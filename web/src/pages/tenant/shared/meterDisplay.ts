import type { Option } from './display';

/** Non-revenue activity types (engine-hour segments, allocations, non-revenue time). */
export const ACTIVITY_TYPE_OPTIONS: readonly Option[] = [
  { value: 'WORK', label: 'Work' },
  { value: 'STANDBY', label: 'Standby' },
  { value: 'DOWNTIME', label: 'Downtime' },
  { value: 'MOBILIZATION', label: 'Mobilization' },
  { value: 'NOTE', label: 'Note' },
];

/** "Movement (mobilization)" etc.; unknown types humanised by the caller. */
export const activityTypeLabel = (type: string): string =>
  type === 'MOBILIZATION'
    ? 'Movement (mobilization)'
    : (ACTIVITY_TYPE_OPTIONS.find((o) => o.value === type)?.label ?? type);

/** Stable meter reading error codes with what the user can do about them. */
export const CAPTURE_ERROR_HINTS: Readonly<Record<string, string>> = {
  REASON_REQUIRED: 'Enter a reason.',
  CAPTURE_ID_CONFLICT:
    'This capture was already recorded with different values; close the dialog and start again.',
};

export const RESET_ERROR_HINTS: Readonly<Record<string, string>> = {
  SEGREGATION_OF_DUTIES:
    'You requested this reset, so you cannot decide it. Another approver must review it.',
  RESET_DECIDED: 'This reset has already been decided.',
};

export const RESET_TONES = { PENDING: 'info', APPROVED: 'success', REJECTED: 'default' } as const;

export const RESET_STATUS_OPTIONS = [
  { value: 'PENDING', label: 'Pending' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
] as const;
