/**
 * Plain-language explanations of risk signals and the other evidence linked to investigation cases. Signals are
 * facts and thresholds for human review — the wording is deliberately neutral ("needs review") and never a
 * verdict about a person. Recorded values are shown as stored (money and times only formatted).
 */
import type { CaseSignalDto, CaseSourceType, ExceptionType, RuleCode } from '../../api/types';
import { EXCEPTION_TYPES } from '../../api/services/meterSchemas';
import { formatMoney } from '../../utils/money';
import { humanize } from '../../utils/text';
import { formatDuration, formatInstantIn } from '../../utils/time';
import { EXCEPTION_TYPE_LABELS, explainException } from '../meter/exceptionText';

export const NEUTRAL_SIGNAL_NOTICE =
  'Signals are recorded evidence that needs review. They are not a conclusion about any person.';

/** Rule titles (backend `RULE_TITLES`). */
export const RULE_LABELS: Readonly<Record<RuleCode, string>> = {
  UNREPORTED_ENGINE_ACTIVITY: 'Engine activity without an active job',
  DUPLICATE_RECEIPT: 'Same receipt image on more than one expense',
  FUEL_ALLOWANCE_EXCEEDED: 'Fuel above the allowance for the meter hours',
  EXPENSE_THRESHOLD_EXCEEDED: 'Weekly machine spending above the threshold',
  CASH_NOT_HANDED_OVER: 'Cash held beyond the handover limits',
  WORK_WITHOUT_AUTHORIZATION: 'Work recorded outside an authorized job',
  UNEXPLAINED_ENGINE_HOURS: 'Engine hours still unexplained after the review period',
  ENGINE_RUNNING_WITHOUT_WORK: 'Engine running without work during the day',
  MACHINE_FUEL_ABOVE_NORM: 'Fuel above the norm for the engine hours',
};

export const SOURCE_TYPE_LABELS: Readonly<Record<CaseSourceType, string>> = {
  RISK_SIGNAL: 'Risk signal',
  METER_EXCEPTION: 'Meter exception',
  TRACKING_ALERT: 'Tracking alert',
  SOD_EVENT: 'Segregation of duties',
  PREDICTION: 'Model output',
  CASH_VARIANCE: 'Cash difference',
  REVENUE_DIFFERENCE: 'Revenue difference',
};

/** Tracking alert types linked to cases (backend `ALERT_TITLES`); others are humanised. */
const ALERT_LABELS: Readonly<Record<string, string>> = {
  TAMPER: 'Tracker tamper signal',
  UNAUTHORIZED_MOVEMENT: 'Movement outside the approved operating window',
  RESTRICTED_AREA_ENTRY: 'Entry into a restricted area',
};

const SOD_CODE = 'SEGREGATION_OF_DUTIES_ATTEMPT';

const RECORD_TYPE_LABELS: Readonly<Record<string, string>> = {
  JOB_ACTIVITY: 'work log entry',
  METER_CAPTURE: 'meter reading',
  EXPENSE: 'expense',
};

type Evidence = Readonly<Record<string, unknown>>;

function isRuleCode(code: string): code is RuleCode {
  return Object.hasOwn(RULE_LABELS, code);
}

function isExceptionType(code: string): code is ExceptionType {
  return (EXCEPTION_TYPES as readonly string[]).includes(code);
}

/** Small typed readers over free-form evidence; missing values read as `—`. */
class Facts {
  constructor(
    private readonly e: Evidence,
    private readonly tz: string,
  ) {}

  raw(key: string): unknown {
    return this.e[key];
  }

  text(key: string): string {
    const v = this.e[key];
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v === 'string') return v;
    if (typeof v === 'number' || typeof v === 'boolean') return String(v);
    return JSON.stringify(v);
  }

  has(key: string): boolean {
    const v = this.e[key];
    return v !== null && v !== undefined && v !== '';
  }

  time(key: string): string {
    const v = this.e[key];
    return typeof v === 'string' ? formatInstantIn(v, this.tz) : '—';
  }

  /** Minutes as a readable duration: 1001.3 -> "16 h 41 min". */
  minutes(key: string): string {
    const n = Number(this.e[key]);
    return this.has(key) && Number.isFinite(n) ? formatDuration(n * 60) : '—';
  }

  money(key: string, currencyKey = 'currency'): string {
    const amount = this.e[key];
    const currency = this.e[currencyKey];
    if (typeof amount !== 'string' && typeof amount !== 'number') return '—';
    return typeof currency === 'string' ? formatMoney(String(amount), currency) : String(amount);
  }

  list(key: string): readonly Evidence[] {
    const v = this.e[key];
    if (!Array.isArray(v)) return [];
    return v.filter((x): x is Evidence => typeof x === 'object' && x !== null && !Array.isArray(x));
  }

  strings(key: string): readonly string[] {
    const v = this.e[key];
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
  }

  sub(row: Evidence): Facts {
    return new Facts(row, this.tz);
  }
}

/** `a meter reading` / `an expense`. */
const withArticle = (noun: string) => `${/^[aeiou]/i.test(noun) ? 'an' : 'a'} ${noun}`;

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

const plural = (n: number, one: string, many: string) => `${String(n)} ${n === 1 ? one : many}`;

type Explainer = (f: Facts) => string;

const RULE_EXPLAIN: Readonly<Record<RuleCode, Explainer>> = {
  UNREPORTED_ENGINE_ACTIVITY: (f) => {
    const basis =
      f.text('basis') === 'ENGINE_HOURS'
        ? `engine hours rising from ${f.text('engine_hours_start')} to ${f.text('engine_hours_end')}`
        : 'ignition on';
    const jobs = f.list('running_jobs_nearby').map((j) => f.sub(j).text('job_number'));
    return (
      `Verified engine activity (${basis}) was recorded for ${f.minutes('uncovered_minutes')}, ` +
      `from ${f.time('uncovered_from')} to ${f.time('uncovered_until')}, while no job on the machine ` +
      `was in progress. The policy threshold is ${f.minutes('threshold_minutes')}.` +
      (f.raw('still_running_when_observed') === true
        ? ' The engine was still running when observed.'
        : '') +
      (jobs.length > 0 ? ` Jobs on this machine around that time: ${jobs.join(', ')}.` : '')
    );
  },
  DUPLICATE_RECEIPT: (f) => {
    const others = f
      .list('same_receipt_on')
      .map((o) => `${f.sub(o).money('amount')} incurred ${f.sub(o).time('incurred_at')}`);
    return (
      `The receipt image on this expense (${f.money('amount')}, incurred ${f.time('incurred_at')}) ` +
      `is identical (SHA-256 ${f.text('receipt_sha256').slice(0, 12)}…) to the receipt on ` +
      `${plural(others.length, 'other expense', 'other expenses')} incurred within ` +
      `${f.text('lookback_days')} days` +
      (others.length > 0 ? `: ${others.join('; ')}.` : '.')
    );
  },
  FUEL_ALLOWANCE_EXCEEDED: (f) =>
    `On job ${f.text('job_number')}, ${f.text('litres_compared')} L of fuel were recorded over ` +
    `${f.text('meter_hours')} meter hours (readings ${f.text('opening_reading')} → ` +
    `${f.text('closing_reading')}): ${f.text('litres_per_meter_hour')} L per meter hour against an ` +
    `allowance of ${f.text('allowance_litres_per_meter_hour')} L per meter hour. Issued into the machine: ` +
    `${f.text('litres_into_machine')} L; logged as used: ${f.text('litres_used')} L.`,
  EXPENSE_THRESHOLD_EXCEEDED: (f) =>
    `Approved and pending expenses on this machine in week ${f.text('iso_week')} total ` +
    `${f.money('approved_and_pending_total')} (${plural(f.strings('expense_ids').length, 'expense', 'expenses')}), ` +
    `above the weekly threshold of ${f.money('threshold_per_week')}.`,
  CASH_NOT_HANDED_OVER: (f) => {
    const limit =
      f.text('limit') === 'ABOVE_AMOUNT_LIMIT'
        ? ` The policy limit for cash held is ${f.money('max_amount')}.`
        : ` The policy expects a handover within ${f.text('max_hours')} h.`;
    return (
      `${f.money('outstanding')} has been held in cash custody since ${f.time('held_since')} ` +
      `(${f.text('held_hours')} h) without a handover.${limit}`
    );
  },
  WORK_WITHOUT_AUTHORIZATION: (f) => {
    const what = RECORD_TYPE_LABELS[f.text('record_type')] ?? 'record';
    const reasons = f.strings('reasons').map((r) => {
      if (r === 'BEFORE_JOB_AUTHORIZED') {
        return f.has('job_approved_at')
          ? `before the job was approved (${f.time('job_approved_at')})`
          : 'while the job was not approved';
      }
      if (r === 'AFTER_JOB_COMPLETED') {
        return `after the job was completed (${f.time('job_completed_at')})`;
      }
      if (r === 'SUPERVISOR_NOT_ASSIGNED_TO_MACHINE') {
        return 'by a supervisor who was not assigned to the machine at that time';
      }
      return humanize(r).toLowerCase();
    });
    return (
      `${capitalize(withArticle(what))} on job ${f.text('job_number')} dated ${f.time('occurred_at')} (received ` +
      `${f.time('received_at')}) was recorded ${reasons.length > 0 ? reasons.join(' and ') : 'outside the authorized period'}. ` +
      `Clock tolerance: ${f.text('tolerance_minutes')} min. Job status now: ${humanize(f.text('job_status_now'))}.`
    );
  },
  UNEXPLAINED_ENGINE_HOURS: (f) =>
    `${f.text('hours')} engine hours on ${f.text('machine_code')} (readings ${f.text('start_reading')} to ` +
    `${f.text('end_reading')}) are not allocated to a job and have not been explained for ` +
    `${f.text('age_days')} days (review period: ${f.text('investigation_after_days')} days). ` +
    'They stay unexplained until a person records an approved explanation.',
  ENGINE_RUNNING_WITHOUT_WORK: (f) => {
    const movements = Number(f.raw('after_hours_movements') ?? 0);
    return (
      `On ${f.text('day')} the machine ran for ${f.minutes('minutes_without_work')} without work: ` +
      `${f.minutes('tracker_minutes_without_job')} of tracker engine-on time with no job in progress and ` +
      `${f.text('meter_unexplained_hours')} unexplained meter hours outside jobs (the larger counts; they may ` +
      `describe the same running). The day's threshold is ${f.minutes('threshold_minutes')}.` +
      (movements > 0
        ? ` ${plural(movements, 'movement', 'movements')} outside the approved operating window that day.`
        : '')
    );
  },
  MACHINE_FUEL_ABOVE_NORM: (f) => {
    const source: Readonly<Record<string, string>> = {
      MACHINE: "the machine's norm",
      MACHINE_CATEGORY: "the machine category's norm",
      TENANT: 'the company norm',
    };
    return (
      `In ${f.text('period_kind') === 'WEEK' ? 'week' : 'the day'} ${f.text('period')}, ` +
      `${f.text('litres_into_machine')} L of fuel were issued or purchased into the machine for ` +
      `${f.text('engine_hours')} engine hours (${f.text('engine_hours_in_jobs')} h in jobs, ` +
      `${f.text('engine_hours_outside_jobs')} h outside jobs): ${f.text('litres_per_engine_hour')} L per ` +
      `engine hour against ${source[f.text('norm_source')] ?? 'the norm'} of ` +
      `${f.text('norm_litres_per_engine_hour')} L per engine hour.`
    );
  },
};

/** One-sentence, neutral explanation of a risk signal from its recorded evidence. */
export function explainRiskSignal(rule: RuleCode, evidence: Evidence, timeZone: string): string {
  return RULE_EXPLAIN[rule](new Facts(evidence, timeZone));
}

/** Short label of any linked evidence (rule title, exception type, alert type…). */
export function caseSignalLabel(s: Pick<CaseSignalDto, 'source_type' | 'code'>): string {
  if (s.source_type === 'RISK_SIGNAL' && isRuleCode(s.code)) return RULE_LABELS[s.code];
  if (s.source_type === 'METER_EXCEPTION' && isExceptionType(s.code)) {
    return EXCEPTION_TYPE_LABELS[s.code];
  }
  if (s.source_type === 'TRACKING_ALERT') return ALERT_LABELS[s.code] ?? humanize(s.code);
  if (s.source_type === 'SOD_EVENT') return 'Attempt to approve or verify own record';
  return humanize(s.code);
}

/** Neutral sentence for one piece of linked evidence, whatever its source. */
export function explainCaseSignal(
  s: Pick<CaseSignalDto, 'source_type' | 'code' | 'evidence'>,
  timeZone: string,
): string {
  const f = new Facts(s.evidence, timeZone);
  switch (s.source_type) {
    case 'RISK_SIGNAL':
      return isRuleCode(s.code)
        ? explainRiskSignal(s.code, s.evidence, timeZone)
        : `Rule ${humanize(s.code)} recorded evidence for review.`;
    case 'METER_EXCEPTION': {
      const base = isExceptionType(s.code)
        ? explainException(s.code, s.evidence)
        : `Meter exception ${humanize(s.code)} was recorded.`;
      const status = f.text('exception_status');
      if (status === 'CONFIRMED')
        return `${base} A reviewer confirmed the discrepancy as recorded.`;
      return f.raw('blocking') === true ? `${base} It blocks billing until reviewed.` : base;
    }
    case 'TRACKING_ALERT':
      return (
        `Tracking alert "${f.text('alert_title')}" (${ALERT_LABELS[s.code] ?? humanize(s.code)}) ` +
        `was raised for the machine. Alert status: ${humanize(f.text('alert_status'))}.`
      );
    case 'SOD_EVENT':
      return s.code === SOD_CODE || f.has('action')
        ? `The system refused an attempt to ${humanize(f.text('action')).toLowerCase()} ` +
            `${withArticle(humanize(f.text('entity_type')).toLowerCase())} record by the person whose ` +
            'own record it was (segregation of duties).'
        : 'A segregation-of-duties check refused an action.';
    case 'CASH_VARIANCE':
      return (
        `The amount received on a ${humanize(f.text('source_type')).toLowerCase()} differed from the ` +
        `declared amount (declared ${f.text('declared_amount')}, received ${f.text('received_amount')} ` +
        `${f.text('currency')}). It needs review; the difference is not a conclusion.`
      );
    case 'REVENUE_DIFFERENCE':
      return (
        `Engine hours in ${f.text('period')} were not matched by money (expected ${f.text('expected_amount')}, ` +
        `attributed ${f.text('attributed_amount')} ${f.text('currency')}). It needs explaining; the difference ` +
        'is not a conclusion.'
      );
    case 'PREDICTION':
      return 'A model output was surfaced for review; it is an indication, not a finding.';
  }
}
