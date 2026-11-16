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
