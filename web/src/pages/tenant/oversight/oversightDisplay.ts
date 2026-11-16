import type { CapabilityCode } from '../../../access/capabilities';
import { pathCapability } from '../../../access/capabilities';
import type { ScorecardRecordDto, ScorecardRecordItem } from '../../../api/oversightTypes';
import type { SelectOption } from '../../../components/forms/FormikSelectField';
import { recordPath } from '../../../navigation/recordRoutes';
import {
  caseDetailPath,
  engineHoursMachinePath,
  exceptionsPath,
  ROUTES,
} from '../../../navigation/routes';

/** Neutral names of the scorecard items: things to look at, never a verdict. */
export const SCORECARD_ITEM_LABELS: Readonly<Record<ScorecardRecordItem, string>> = {
  MISSING_DAILY_REPORT: 'Missing daily reports',
  LATE_DAILY_REPORT: 'Late daily reports',
  UNEXPLAINED_HOURS: 'Unexplained engine hours',
  ALERT: 'Tracking alerts',
  CASH_HELD_TOO_LONG: 'Cash held too long',
  CASH_DIFFERENCE: 'Cash differences',
  REVENUE_DIFFERENCE: 'Revenue differences',
  REFUSED_ATTEMPT: 'Refused attempts',
  PATTERN_SIGNAL: 'Repeated items raised for review',
};

/** Display order of the record groups on a person's scorecard. */
export const SCORECARD_RECORD_ORDER: readonly ScorecardRecordItem[] = [
  'MISSING_DAILY_REPORT',
  'LATE_DAILY_REPORT',
  'UNEXPLAINED_HOURS',
  'ALERT',
  'CASH_HELD_TOO_LONG',
  'CASH_DIFFERENCE',
  'REVENUE_DIFFERENCE',
  'REFUSED_ATTEMPT',
  'PATTERN_SIGNAL',
];

export const SCORECARD_ITEM_OPTIONS: readonly SelectOption[] = SCORECARD_RECORD_ORDER.filter(
  (i) => i !== 'PATTERN_SIGNAL',
).map((value) => ({ value, label: SCORECARD_ITEM_LABELS[value] }));

export interface RecordLink {
  to: string;
  label: string;
}

const caseIdOf = (r: ScorecardRecordDto): string | null => {
  const v = r.detail?.case_id;
  return typeof v === 'string' && v !== '' ? v : null;
};

/** The page that opens the record behind a scorecard item (null when there is none to open). */
function rawRecordLink(r: ScorecardRecordDto): RecordLink | null {
  const id = r.record_id;
  switch (r.record_type) {
    case 'job_exception':
      return { to: exceptionsPath(), label: 'Open exceptions' };
    case 'engine_interval':
      return r.machine_id != null
        ? { to: engineHoursMachinePath(r.machine_id), label: 'Open engine-hour ledger' }
        : null;
    case 'tracking_alert':
      return { to: ROUTES.tenantAlerts, label: 'Open alerts' };
    case 'cash_remittance_overdue':
      return id === null
        ? null
        : { to: recordPath('REMITTANCE_OVERDUE', id), label: 'Open the flag' };
    case 'cash_variance':
      return id === null ? null : { to: recordPath('CASH_VARIANCE', id), label: 'Open difference' };
    case 'revenue_difference':
      return id === null
        ? null
        : { to: recordPath('REVENUE_DIFFERENCE', id), label: 'Open difference' };
    case 'security_event':
      return { to: ROUTES.tenantSecurityEvents, label: 'Open security events' };
    case 'risk_signal': {
      const caseId = caseIdOf(r);
      return caseId === null ? null : { to: caseDetailPath(caseId), label: 'Open investigation' };
    }
    default:
      return null;
  }
}

/** Record link, dropped when its page belongs to a capability the tenant switched off. */
export function scorecardRecordLink(
  r: ScorecardRecordDto,
  disabled: ReadonlySet<string>,
): RecordLink | null {
  const link = rawRecordLink(r);
  if (link === null) return null;
  const capability: CapabilityCode | null = pathCapability(link.to);
  return capability !== null && disabled.has(capability) ? null : link;
}

export const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);
export const MAX_PERIOD_DAYS = 93;
const daysBetween = (a: string, b: string) => (Date.parse(b) - Date.parse(a)) / 86_400_000 + 1;

/** Period check for the From / To fields: an error message, or null when usable. */
export function periodError(from: string, to: string): string | null {
  if (!isDay(from) || !isDay(to)) return null;
  if (from > to) return 'The “from” day must not be after the “to” day.';
  if (daysBetween(from, to) > MAX_PERIOD_DAYS)
    return `Choose at most ${String(MAX_PERIOD_DAYS)} days.`;
  return null;
}
