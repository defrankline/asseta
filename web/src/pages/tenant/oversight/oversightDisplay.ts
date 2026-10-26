import type { CapabilityCode } from '../../../access/capabilities';
import { pathCapability } from '../../../access/capabilities';
import type {
  CheckinSlotStatus,
  ScorecardRecordDto,
  ScorecardRecordItem,
  SiteCheckinDto,
} from '../../../api/oversightTypes';
import type { SelectOption } from '../../../components/forms/FormikSelectField';
import type { StatusTone } from '../../../components/display/StatusChip';
import { siteCheckinsPath } from '../../../navigation/oversightRoutes';
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
  MISSED_CHECKIN: 'Missed site check-ins',
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
  'MISSED_CHECKIN',
  'PATTERN_SIGNAL',
];

export const SCORECARD_ITEM_OPTIONS: readonly SelectOption[] = SCORECARD_RECORD_ORDER.filter(
  (i) => i !== 'PATTERN_SIGNAL',
).map((value) => ({ value, label: SCORECARD_ITEM_LABELS[value] }));

export const SLOT_STATUS_LABELS: Readonly<Record<CheckinSlotStatus, string>> = {
  MADE: 'Made',
  MISSED: 'Missed',
  DUE: 'Due now',
  UPCOMING: 'Upcoming',
};

export const SLOT_STATUS_TONES: Readonly<Record<CheckinSlotStatus, StatusTone>> = {
  MADE: 'success',
  MISSED: 'warning',
  DUE: 'info',
  UPCOMING: 'default',
};

export const SOURCE_LABELS: Readonly<Record<string, string>> = {
  API: 'Web',
  SYNC: 'Supervisor app',
};

export interface RecordLink {
  to: string;
  label: string;
}

const caseIdOf = (r: ScorecardRecordDto): string | null => {
  const v = r.detail?.case_id;
  return typeof v === 'string' && v !== '' ? v : null;
};

/** The page that opens the record behind a scorecard item (null when there is none to open). */
function rawRecordLink(r: ScorecardRecordDto, staffId: string): RecordLink | null {
  const id = r.record_id;
  switch (r.record_type) {
    case 'job_exception':
      return {
        to: r.job_id != null ? exceptionsPath(r.job_id) : exceptionsPath(),
        label: 'Open exceptions',
      };
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
    case 'site_checkin_slot':
      return {
        to: siteCheckinsPath({
          staff_id: staffId,
          day_from: r.day ?? undefined,
          day_to: r.day ?? undefined,
        }),
        label: 'Check-ins that day',
      };
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
  staffId: string,
  disabled: ReadonlySet<string>,
): RecordLink | null {
  const link = rawRecordLink(r, staffId);
  if (link === null) return null;
  const capability: CapabilityCode | null = pathCapability(link.to);
  return capability !== null && disabled.has(capability) ? null : link;
}

/** "Within the distance" / "Farther than allowed" / distance only. */
export function distanceText(c: Pick<SiteCheckinDto, 'distance_m' | 'within_distance'>): string {
  if (c.distance_m === null) return 'Not measured';
  const metres = `${String(Math.round(c.distance_m))} m from the site`;
  if (c.within_distance === true) return `${metres} (within the distance)`;
  if (c.within_distance === false) return `${metres} (farther than set)`;
  return metres;
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

export const CHECKIN_ERROR_HINTS: Readonly<Record<string, string>> = {
  SITE_CHECKIN_DISABLED: 'Site check-ins are switched off for your company.',
  STAFF_NOT_LINKED: 'Your login is not linked to a staff record; ask an administrator.',
  CHECKIN_IN_FUTURE: "Your device's clock is ahead; correct the time and try again.",
  JOB_SITE_NOT_FOUND: 'That site is not known; reload and try again.',
  CHECKIN_ID_CONFLICT: 'This check-in was already sent with different details; reload.',
};
