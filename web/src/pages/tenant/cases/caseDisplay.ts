import { peopleService } from '../../../api/services/peopleService';
import type {
  AnomalyCaseDto,
  CaseOutcomeKind,
  CaseSignalDto,
  CaseStatus,
  PersonDto,
  RuleCode,
  SignalSeverity,
  SignalStatus,
  SubjectType,
} from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';
import { RULE_LABELS } from '../../../components/intelligence/signalText';
import {
  exceptionsPath,
  financeTabPath,
  jobDetailPath,
  machineDetailPath,
  ROUTES,
  staffDetailPath,
} from '../../../navigation/routes';
import type { Option } from '../shared/display';

/** Case statuses, worded neutrally (a case collects evidence for review). */
export const CASE_STATUS_LABELS: Readonly<Record<CaseStatus, string>> = {
  OPEN: 'Needs review',
  IN_REVIEW: 'In review',
  RESOLVED: 'Resolved',
};
export const CASE_STATUS_TONES: Readonly<Record<CaseStatus, StatusTone>> = {
  OPEN: 'warning',
  IN_REVIEW: 'info',
  RESOLVED: 'success',
};
export const CASE_STATUS_OPTIONS: readonly Option<CaseStatus>[] = [
  { value: 'OPEN', label: CASE_STATUS_LABELS.OPEN },
  { value: 'IN_REVIEW', label: CASE_STATUS_LABELS.IN_REVIEW },
  { value: 'RESOLVED', label: CASE_STATUS_LABELS.RESOLVED },
];

export const SEVERITY_LABELS: Readonly<Record<SignalSeverity, string>> = {
  INFO: 'Information',
  WARNING: 'Warning',
  CRITICAL: 'Critical',
};
export const SEVERITY_TONES: Readonly<Record<SignalSeverity, StatusTone>> = {
  INFO: 'info',
  WARNING: 'warning',
  CRITICAL: 'error',
};
export const SEVERITY_FILTER_OPTIONS: readonly Option<SignalSeverity>[] = [
  { value: 'CRITICAL', label: SEVERITY_LABELS.CRITICAL },
  { value: 'WARNING', label: SEVERITY_LABELS.WARNING },
  { value: 'INFO', label: SEVERITY_LABELS.INFO },
];

export const SIGNAL_STATUS_LABELS: Readonly<Record<SignalStatus, string>> = {
  OPEN: 'Not yet on a case',
  LINKED: 'On a case',
  DISMISSED: 'Dismissed',
};
export const SIGNAL_STATUS_TONES: Readonly<Record<SignalStatus, StatusTone>> = {
  OPEN: 'warning',
  LINKED: 'info',
  DISMISSED: 'default',
};
export const SIGNAL_STATUS_OPTIONS: readonly Option<SignalStatus>[] = [
  { value: 'OPEN', label: SIGNAL_STATUS_LABELS.OPEN },
  { value: 'LINKED', label: SIGNAL_STATUS_LABELS.LINKED },
  { value: 'DISMISSED', label: SIGNAL_STATUS_LABELS.DISMISSED },
];

export const RULE_OPTIONS: readonly Option<RuleCode>[] = (
  Object.keys(RULE_LABELS) as RuleCode[]
).map((code) => ({ value: code, label: RULE_LABELS[code] }));

export const SUBJECT_TYPE_LABELS: Readonly<Record<SubjectType, string>> = {
  MACHINE: 'Machine',
  JOB: 'Job',
  STAFF: 'Staff member',
  EXPENSE: 'Expense',
  USER: 'User',
};

/** What a reviewer found; never a judgement of a person. */
export const OUTCOME_LABELS: Readonly<Record<CaseOutcomeKind, string>> = {
  CONFIRMED_ISSUE: 'Issue confirmed',
  UNCONFIRMED: 'Not confirmed',
  LEGITIMATE_EXPLANATION: 'Legitimate explanation',
};
export const OUTCOME_TONES: Readonly<Record<CaseOutcomeKind, StatusTone>> = {
  CONFIRMED_ISSUE: 'warning',
  UNCONFIRMED: 'default',
  LEGITIMATE_EXPLANATION: 'success',
};
export const OUTCOME_OPTIONS: readonly Option<CaseOutcomeKind>[] = [
  { value: 'CONFIRMED_ISSUE', label: OUTCOME_LABELS.CONFIRMED_ISSUE },
  { value: 'UNCONFIRMED', label: OUTCOME_LABELS.UNCONFIRMED },
  { value: 'LEGITIMATE_EXPLANATION', label: OUTCOME_LABELS.LEGITIMATE_EXPLANATION },
];

/** Stable error codes from the case commands → what the user can do. */
export const CASE_ERROR_HINTS: Readonly<Record<string, string>> = {
  SEGREGATION_OF_DUTIES:
    'People whose own records are part of the evidence cannot review this case; a colleague must do it.',
  ASSIGNEE_NOT_MEMBER: 'Choose a current member of this company.',
  CASE_RESOLVED: 'The case is resolved; reopen it first.',
  CASE_NOT_RESOLVED: 'Only a resolved case can be reopened; reload the case.',
};

/** Explanation / reason lengths accepted by the case commands. */
export const EXPLANATION_MIN = 10;
export const EXPLANATION_MAX = 4000;
export const REOPEN_REASON_MAX = 2000;
export const NOTE_MAX = 4000;
export const OUTCOME_REQUIRED = 'Choose an outcome';
export const EXPLANATION_TOO_SHORT = `At least ${String(EXPLANATION_MIN)} characters`;

/**
 * Policy version stamp for display. Stamps may carry the internal policy type code; it is shown with the
 * console's name for that policy ("Risk signals"), as on the Policies page.
 */
export function policyVersionLabel(stamp: string): string {
  return stamp.replace(/fraud[_ ]controls/gi, 'Risk signals');
}

/** Where the subject of a case lives in the console (expenses open in a drawer instead). */
export function subjectPath(c: Pick<AnomalyCaseDto, 'subject_type' | 'subject_id'>): string | null {
  switch (c.subject_type) {
    case 'MACHINE':
      return machineDetailPath(c.subject_id);
    case 'JOB':
      return jobDetailPath(c.subject_id);
    case 'STAFF':
      return staffDetailPath(c.subject_id);
    case 'EXPENSE':
    case 'USER':
      return null;
  }
}

/** A link from a piece of evidence to the record it came from. */
export type SourceLink =
  | { kind: 'route'; label: string; to: string }
  | { kind: 'expense'; label: string; expenseId: string };

const str = (v: unknown): string | null => (typeof v === 'string' && v !== '' ? v : null);

function riskSignalLinks(s: CaseSignalDto, c: AnomalyCaseDto): SourceLink[] {
  const e = s.evidence;
  const job = (id: string | null, label = 'Open job'): SourceLink[] =>
    id === null ? [] : [{ kind: 'route', label, to: jobDetailPath(id) }];
  switch (s.code) {
    case 'DUPLICATE_RECEIPT': {
      const others = Array.isArray(e.same_receipt_on) ? (e.same_receipt_on as unknown[]) : [];
      const ids = [
        str(e.expense_id),
        ...others.map((o) => str((o as Record<string, unknown>).expense_id)),
      ];
      return ids
        .filter((id): id is string => id !== null)
        .map((expenseId, i) => ({
          kind: 'expense',
          label: i === 0 ? 'Open expense' : `Open other expense ${String(i)}`,
          expenseId,
        }));
    }
    case 'EXPENSE_THRESHOLD_EXCEEDED':
      return [{ kind: 'route', label: 'Open expenses', to: ROUTES.tenantExpenses }];
    case 'FUEL_ALLOWANCE_EXCEEDED':
      return [
        ...job(c.job_id),
        { kind: 'route', label: 'Open fuel log', to: `${ROUTES.tenantExpenses}?tab=fuel` },
      ];
    case 'WORK_WITHOUT_AUTHORIZATION': {
      const recordId = str(e.record_id);
      const expense: SourceLink[] =
        e.record_type === 'EXPENSE' && recordId !== null
          ? [{ kind: 'expense', label: 'Open expense', expenseId: recordId }]
          : [];
      return [...job(c.subject_type === 'JOB' ? c.subject_id : c.job_id), ...expense];
    }
    case 'UNREPORTED_ENGINE_ACTIVITY': {
      const nearby = Array.isArray(e.running_jobs_nearby)
        ? (e.running_jobs_nearby as unknown[])
        : [];
      return nearby.slice(0, 3).flatMap((j) => {
        const row = j as Record<string, unknown>;
        return job(str(row.job_id), `Open job ${str(row.job_number) ?? ''}`.trim());
      });
    }
    case 'CASH_NOT_HANDED_OVER':
      return [{ kind: 'route', label: 'Open cash custody', to: financeTabPath('custody') }];
    default:
      return [];
  }
}

/** Links from one piece of evidence to its source records. */
export function sourceLinks(s: CaseSignalDto, c: AnomalyCaseDto): SourceLink[] {
  switch (s.source_type) {
    case 'RISK_SIGNAL':
      return riskSignalLinks(s, c);
    case 'METER_EXCEPTION':
      return [
        {
          kind: 'route',
          label: 'Open exceptions',
          to: exceptionsPath(c.job_id ?? undefined),
        },
      ];
    case 'TRACKING_ALERT':
      return [{ kind: 'route', label: 'Open alerts', to: ROUTES.tenantAlerts }];
    case 'CASH_VARIANCE':
      return [{ kind: 'route', label: 'Open cash custody', to: financeTabPath('custody') }];
    case 'REVENUE_DIFFERENCE':
      return [
        {
          kind: 'route',
          label: 'Open revenue difference',
          to: `/tenant/revenue-differences/${s.source_id}`,
        },
      ];
    case 'SOD_EVENT':
    case 'PREDICTION':
      return [];
  }
}

/** Server search over current tenant members by name (assignee pickers and filters). */
export function searchPeople(q: string, signal: AbortSignal): Promise<PersonDto[]> {
  return peopleService.search(q, signal);
}

export const personLabel = (p: PersonDto) => p.display_name;
export const personId = (p: PersonDto) => p.user_id;
