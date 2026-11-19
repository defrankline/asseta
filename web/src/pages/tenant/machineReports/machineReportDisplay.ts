import type {
  MachineReportStatus,
  ReportLineKind,
  StartSource,
} from '../../../api/machineReportTypes';
import type { StatusTone } from '../../../components/display/StatusChip';
import { MACHINE_REPORT_STATUSES } from '../../../api/services/machineReportSchemas';
import { parseDecimal, sumDecimals } from '../../../utils/money';

export const REPORT_STATUS_LABELS: Readonly<Record<MachineReportStatus, string>> = {
  SUBMITTED: 'Waiting for a decision',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
};
export const REPORT_STATUS_TONES: Readonly<Record<MachineReportStatus, StatusTone>> = {
  SUBMITTED: 'warning',
  APPROVED: 'success',
  REJECTED: 'error',
};
export const REPORT_STATUS_OPTIONS = MACHINE_REPORT_STATUSES.map((s) => ({
  value: s,
  label: REPORT_STATUS_LABELS[s],
}));
export const REPORT_QUEUE_OPTIONS = [
  { value: 'PENDING', label: 'Waiting for a decision' },
] as const;

export const START_SOURCE_LABELS: Readonly<Record<StartSource, string>> = {
  REPORT: 'last approved report',
  BASELINE: 'meter baseline',
  RESET: 'meter reset',
  OPENING: 'opening report',
};

export const LINE_KIND_LABELS: Readonly<Record<ReportLineKind, string>> = {
  CUSTOMER: 'Customer',
  NON_PRODUCTIVE: 'Non-productive',
};

/** Hours as "1,210.5 h" (trailing zero decimals dropped). */
export function hoursLabel(value: string): string {
  const [whole = '0', fraction = ''] = value.split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const frac = fraction.replace(/0+$/, '');
  return `${frac === '' ? grouped : `${grouped}.${frac}`} h`;
}

/** A decimal without trailing zero decimals ("300.0" → "300"), for prefilled inputs. */
export function plainHours(value: string): string {
  return value.includes('.') ? value.replace(/\.?0+$/, '') : value;
}

/** a − b, exactly (decimal strings). */
export function minus(a: string, b: string): string {
  return sumDecimals([a, b.startsWith('-') ? b.slice(1) : `-${b}`]);
}

/** Whether `hours` uses at most `decimals` places (the meter's precision). */
export function inMeterSteps(hours: string, decimals: number): boolean {
  if (parseDecimal(hours) === null) return false;
  const frac = hours.trim().split('.')[1] ?? '';
  return frac.replace(/0+$/, '').length <= decimals;
}

/** Submit / decide refusals in plain words (the server decides; these say what to do next). */
export const REPORT_ERROR_HINTS: Readonly<Record<string, string>> = {
  MACHINE_NOT_FOUND: 'This machine no longer exists. Reload the page.',
  MACHINE_NOT_ASSIGNED:
    'This machine is not assigned to you. Ask the office to assign it, or report on your own machines.',
  REPORT_PENDING:
    'A report on this machine is waiting for a decision; the next one can be sent after it is decided.',
  OPENING_REPORT_REQUIRED:
    'This machine has no starting reading yet: its first report gives the reading only. Close and start the report again.',
  OPENING_NOT_ALLOWED:
    'This machine already has a starting reading, so this is a normal report. Close and start the report again to split its hours.',
  READING_NOT_HIGHER: 'The new reading is lower than the last one. Check the number on the meter.',
  NOTHING_TO_REPORT: 'The reading is the same as the last one: there is nothing to report.',
  REPORT_SUM_MISMATCH: 'The lines must add up exactly to the hours shown by the meter.',
  HOURS_PRECISION: 'Hours have at most 2 decimals (steps of 0.01).',
  DUPLICATE_CUSTOMER_LINE: 'Put each customer on one line only.',
  HOURS_NOT_AVAILABLE:
    'A customer does not have that many usable hours. Lower their hours or record the rest as non-productive. When approving: reject the report; the supervisor sends a new one.',
  CUSTOMER_NOT_FOUND: 'A customer on the report no longer exists. Choose another.',
  REASON_NOT_FOUND: 'A reason on the report no longer exists. Choose another.',
  REASON_INVALID: 'A reason on the report is switched off. Choose another.',
  CAPTURE_NOT_FOUND: 'The reading was not found. Take the reading again.',
  CAPTURE_MACHINE_MISMATCH: 'The reading belongs to another machine.',
  CAPTURE_REJECTED: 'The reading was refused by the company’s reading rules. Take it again.',
  CAPTURE_ALREADY_USED: 'This reading was already used in another report. Take a new reading.',
  CORRECTION_NOT_ALLOWED:
    'A rejected report can’t be corrected; send a new report with a new reading.',
  // No longer sent by the server (kept for older responses).
  CAPTURE_ALREADY_REPORTED: 'This reading was already used in another report. Take a new reading.',
  CORRECTS_INVALID: 'A rejected report can’t be corrected; send a new report with a new reading.',
  REPORT_ID_CONFLICT: 'This report was already sent with other details. Close and start again.',
  HOURS_DISABLED:
    'Customer hours are switched off for your company: use non-productive lines only.',
  SEGREGATION_OF_DUTIES:
    'The person who submitted a report cannot decide it. Ask another authorised colleague.',
  REPORT_NOT_PENDING: 'This report was already decided. Reload to see the decision.',
  REPORT_READINGS_CHANGED:
    'The machine’s starting reading changed since this report was sent (a baseline, a meter reset, or another opening report was approved). Reject it; the supervisor then sends a new report with a new reading.',
};

/** Reason list refusals in plain words. */
export const REASON_ERROR_HINTS: Readonly<Record<string, string>> = {
  DUPLICATE_CODE: 'Another reason already uses this code. Choose a different code.',
  REASON_CODE_TAKEN: 'Another reason already uses this code. Choose a different code.',
};

export type MachineReportState = 'AWAITING' | 'DUE' | 'UP_TO_DATE';

/**
 * The report state of one of my machines, as the Supervisor apps show it. A rejected report is final,
 * so after a rejection the machine is due again (a new report with a new reading).
 */
export function machineReportState(
  s: {
    pending_report_id: string | null;
    rejected_report_id: string | null;
    previous_reading?: string | null;
    opening_required?: boolean;
    days_since_report: number | null;
  },
  reminderDays: number | null,
): MachineReportState {
  if (s.pending_report_id !== null) return 'AWAITING';
  if (s.rejected_report_id !== null) return 'DUE';
  // Never reported, no starting reading yet, or no report for the company's reminder days.
  if (s.opening_required === true || s.previous_reading == null || s.days_since_report === null) {
    return 'DUE';
  }
  if (reminderDays !== null && s.days_since_report >= reminderDays) return 'DUE';
  return 'UP_TO_DATE';
}

export const MACHINE_STATE_LABELS: Readonly<Record<MachineReportState, string>> = {
  AWAITING: 'Awaiting approval',
  DUE: 'Report due',
  UP_TO_DATE: 'Up to date',
};
export const MACHINE_STATE_TONES: Readonly<Record<MachineReportState, StatusTone>> = {
  AWAITING: 'info',
  DUE: 'warning',
  UP_TO_DATE: 'success',
};
