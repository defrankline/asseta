import { array, object, type Schema } from 'yup';
import type {
  AnomalyCaseDetailDto,
  AnomalyCaseDto,
  CaseNoteDto,
  CaseNoteKind,
  CaseOutcomeDto,
  CaseOutcomeKind,
  CaseSignalDto,
  CaseSourceType,
  CaseStatus,
  RiskSignalDto,
  RuleCode,
  SignalSeverity,
  SignalStatus,
  SubjectType,
} from '../types';
import { id, int, nullableId, nullableOneOf, nullableText, oneOf, record, text } from './schemaKit';

// ---- Risk signals and investigation cases (ADR-007) ----

export const RULE_CODES: readonly RuleCode[] = [
  'UNREPORTED_ENGINE_ACTIVITY',
  'DUPLICATE_RECEIPT',
  'FUEL_ALLOWANCE_EXCEEDED',
  'EXPENSE_THRESHOLD_EXCEEDED',
  'CASH_NOT_HANDED_OVER',
  'WORK_WITHOUT_AUTHORIZATION',
];
export const SIGNAL_SEVERITIES: readonly SignalSeverity[] = ['INFO', 'WARNING', 'CRITICAL'];
export const SIGNAL_STATUSES: readonly SignalStatus[] = ['OPEN', 'LINKED', 'DISMISSED'];
export const SUBJECT_TYPES: readonly SubjectType[] = ['MACHINE', 'JOB', 'STAFF', 'EXPENSE', 'USER'];
export const CASE_STATUSES: readonly CaseStatus[] = ['OPEN', 'IN_REVIEW', 'RESOLVED'];
export const CASE_SOURCE_TYPES: readonly CaseSourceType[] = [
  'RISK_SIGNAL',
  'METER_EXCEPTION',
  'TRACKING_ALERT',
  'SOD_EVENT',
  'PREDICTION',
];
export const CASE_NOTE_KINDS: readonly CaseNoteKind[] = ['NOTE', 'REOPEN'];
export const CASE_OUTCOMES: readonly CaseOutcomeKind[] = [
  'CONFIRMED_ISSUE',
  'UNCONFIRMED',
  'LEGITIMATE_EXPLANATION',
];

export const riskSignalSchema: Schema<RiskSignalDto> = object({
  id: id(),
  rule_code: oneOf(RULE_CODES),
  rule_version: int(),
  severity: oneOf(SIGNAL_SEVERITIES),
  subject_type: oneOf(SUBJECT_TYPES),
  subject_id: id(),
  machine_id: nullableId(),
  job_id: nullableId(),
  staff_member_id: nullableId(),
  window_start: text(),
  window_end: text(),
  evidence: record(),
  policy_version: text(),
  dedupe_key: text(),
  status: oneOf(SIGNAL_STATUSES),
  created_at: text(),
});

const caseFields = {
  id: id(),
  case_number: text(),
  title: text(),
  subject_type: oneOf(SUBJECT_TYPES),
  subject_id: id(),
  machine_id: nullableId(),
  job_id: nullableId(),
  staff_member_id: nullableId(),
  severity: oneOf(SIGNAL_SEVERITIES),
  status: oneOf(CASE_STATUSES),
  assignee_user_id: nullableId(),
  assignee_name: nullableText().default(null),
  opened_at: text(),
  last_signal_at: text(),
  resolved_at: nullableText(),
  resolved_by: nullableId(),
  signal_count: int().default(0),
  latest_outcome: nullableOneOf(CASE_OUTCOMES).default(null),
  policy_version: text(),
  version: int(),
};

export const anomalyCaseSchema: Schema<AnomalyCaseDto> = object(caseFields);

export const caseSignalSchema: Schema<CaseSignalDto> = object({
  id: id(),
  source_type: oneOf(CASE_SOURCE_TYPES),
  source_id: id(),
  code: text(),
  severity: oneOf(SIGNAL_SEVERITIES),
  observed_at: text(),
  evidence: record(),
  linked_at: text(),
});

export const caseNoteSchema: Schema<CaseNoteDto> = object({
  id: id(),
  kind: oneOf(CASE_NOTE_KINDS),
  body: text(),
  author_user_id: nullableId(),
  author_name: nullableText().default(null),
  created_at: text(),
});

export const caseOutcomeSchema: Schema<CaseOutcomeDto> = object({
  id: id(),
  sequence: int(),
  outcome: oneOf(CASE_OUTCOMES),
  explanation: text(),
  decided_by: id(),
  decided_by_name: nullableText().default(null),
  decided_at: text(),
});

export const anomalyCaseDetailSchema: Schema<AnomalyCaseDetailDto> = object({
  case: object(caseFields).required(),
  signals: array(caseSignalSchema).required(),
  notes: array(caseNoteSchema).required(),
  outcomes: array(caseOutcomeSchema).required(),
});
