/**
 * Oversight (DEC-031 Phase 5): the people scorecard (M1), unbilled work and idle machines (M2) and
 * site check-ins (M3). Each endpoint needs its tenant capability (SCORECARD, UNBILLED_WORK,
 * IDLE_MACHINES, SITE_CHECKIN); the server refuses with <CAPABILITY>_DISABLED while it is off.
 */
import { array, boolean, mixed, number, object, string, type Schema } from 'yup';
import type {
  AmountByCurrencyDto,
  CashHeldDto,
  CheckinSlotDto,
  CheckinSlotStatus,
  IdleMachineDto,
  MySiteCheckinsDto,
  ScorecardDetailDto,
  ScorecardItem,
  ScorecardRecordDto,
  ScorecardRecordItem,
  ScorecardRowDto,
  SiteCheckinDto,
  SiteCheckinIn,
  UnbilledJobDto,
} from '../oversightTypes';
import type { Page } from '../types';
import { GPS_STATUSES } from './meterSchemas';
import {
  bool,
  id,
  int,
  nullableId,
  nullableInt,
  nullableNum,
  nullableText,
  oneOf,
  text,
} from './schemaKit';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
  tenantSend,
  type TenantListQuery,
} from './tenantRequest';

const optionalText = () => string().nullable().default(null);
const optionalId = () => string().nullable().default(null);

export const SCORECARD_ITEMS: readonly ScorecardItem[] = [
  'MISSING_DAILY_REPORT',
  'LATE_DAILY_REPORT',
  'UNEXPLAINED_HOURS',
  'ALERT',
  'CASH_HELD_TOO_LONG',
  'CASH_DIFFERENCE',
  'REVENUE_DIFFERENCE',
  'REFUSED_ATTEMPT',
  'MISSED_CHECKIN',
];
const RECORD_ITEMS: readonly ScorecardRecordItem[] = [...SCORECARD_ITEMS, 'PATTERN_SIGNAL'];
export const CHECKIN_SLOT_STATUSES: readonly CheckinSlotStatus[] = [
  'MADE',
  'MISSED',
  'DUE',
  'UPCOMING',
];

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

const amountByCurrency: Schema<AmountByCurrencyDto> = object({
  currency: text(),
  count: int(),
  amount: text(),
});

const cashHeld: Schema<CashHeldDto> = object({
  currency: text(),
  amount: text(),
  held_since: nullableText(),
  held_days: nullableInt(),
});

export const scorecardRowSchema: Schema<ScorecardRowDto> = object({
  staff_member_id: id(),
  staff_member_name: optionalText(),
  staff_kind: text(),
  employee_code: nullableText(),
  is_active: bool(),
  day_from: text(),
  day_to: text(),
  machines: int(),
  daily_reports_missing: int(),
  daily_reports_late: int(),
  unexplained_hours: text(),
  unexplained_items: int(),
  alerts: int(),
  alerts_open: int(),
  alerts_acknowledged: int(),
  avg_hours_to_acknowledge: nullableText(),
  max_hours_to_acknowledge: nullableText(),
  cash_held: array(cashHeld).default([]),
  cash_held_too_long: int(),
  cash_differences: int(),
  cash_difference_totals: array(amountByCurrency).required(),
  cash_differences_near_threshold: int(),
  revenue_differences: int(),
  revenue_difference_totals: array(amountByCurrency).required(),
  refused_attempts: int(),
  checkins_missed: nullableInt(),
  checkins_made: int(),
  pattern_signals: int(),
  items_total: int(),
});

export const scorecardRecordSchema: Schema<ScorecardRecordDto> = object({
  item: oneOf(RECORD_ITEMS),
  record_type: text(),
  record_id: nullableId(),
  at: text(),
  day: nullableText(),
  machine_id: optionalId(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  job_id: optionalId(),
  job_number: optionalText(),
  currency: optionalText(),
  amount: optionalText(),
  hours: optionalText(),
  status: optionalText(),
  near_threshold: bool(),
  detail: mixed<Record<string, unknown>>(isPlainRecord).default({}),
});

export const scorecardDetailSchema: Schema<ScorecardDetailDto> = object({
  row: scorecardRowSchema,
  records: array(scorecardRecordSchema).required(),
});

export const unbilledJobSchema: Schema<UnbilledJobDto> = object({
  job_id: id(),
  job_number: optionalText(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  customer_id: id(),
  customer_name: optionalText(),
  job_site_id: nullableId(),
  job_site_name: optionalText(),
  supervisor_staff_id: nullableId(),
  supervisor_staff_name: optionalText(),
  completed_at: text(),
  days_unbilled: int(),
  billable_hours: nullableText(),
  currency: text(),
  total: nullableText(),
  draft_invoice_id: nullableId(),
});

export const idleMachineSchema: Schema<IdleMachineDto> = object({
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  category_id: nullableId(),
  idle_since: text(),
  idle_days: int(),
  last_job_id: nullableId(),
  last_job_number: optionalText(),
  last_job_completed_at: nullableText(),
  last_engine_activity_at: nullableText(),
  planned_job_id: nullableId(),
  planned_job_number: optionalText(),
});

export const siteCheckinSchema: Schema<SiteCheckinDto> = object({
  id: id(),
  client_id: id(),
  staff_member_id: id(),
  staff_member_name: optionalText(),
  recorded_by: id(),
  recorded_by_name: optionalText(),
  captured_at: text(),
  received_at: text(),
  gps_status: oneOf(GPS_STATUSES),
  latitude: nullableNum(),
  longitude: nullableNum(),
  accuracy_m: nullableNum(),
  job_site_id: nullableId(),
  job_site_name: optionalText(),
  job_id: nullableId(),
  job_number: optionalText(),
  distance_m: nullableNum(),
  within_distance: boolean().nullable().default(null),
  source: text(),
});

const slotSchema: Schema<CheckinSlotDto> = object({
  scheduled_at: text(),
  window_minutes: int(),
  status: oneOf(CHECKIN_SLOT_STATUSES),
  checkin_id: optionalId(),
  job_id: optionalId(),
  job_number: optionalText(),
});

export const mySiteCheckinsSchema: Schema<MySiteCheckinsDto> = object({
  required: bool(),
  times: array(text()).required(),
  window_minutes: int(),
  max_distance_m: number().integer().nullable().defined(),
  timezone: text(),
  day_from: text(),
  day_to: text(),
  slots: array(slotSchema).required(),
  checkins: array(siteCheckinSchema).required(),
});

const scorecardPage = tenantPageSchema(scorecardRowSchema);
const unbilledPage = tenantPageSchema(unbilledJobSchema);
const idlePage = tenantPageSchema(idleMachineSchema);
const checkinPage = tenantPageSchema(siteCheckinSchema);

export interface PeriodQuery {
  day_from?: string | undefined;
  day_to?: string | undefined;
}

export const oversightService = {
  /** GET /tenant/scorecard (listScorecard): one row per person, most items first. Filters: day_from,
   * day_to (≤ 93 days, default 30), staff_id, site_id; `q` = name. */
  listScorecard(query: TenantListQuery, signal?: AbortSignal): Promise<Page<ScorecardRowDto>> {
    return tenantPage('/tenant/scorecard', scorecardPage, query, 'people scorecard', signal);
  },
  /** GET /tenant/scorecard/{staff_member_id} (getScorecard): figures and every record behind them. */
  getScorecard(
    staffMemberId: string,
    query: PeriodQuery & { item?: ScorecardItem | undefined },
    signal?: AbortSignal,
  ): Promise<ScorecardDetailDto> {
    return tenantGet(
      `/tenant/scorecard/${seg(staffMemberId)}`,
      scorecardDetailSchema,
      'scorecard',
      signal,
      { day_from: query.day_from, day_to: query.day_to, item: query.item },
    );
  },
  /** GET /tenant/unbilled-work (listUnbilledWork). Filters: customer_id, machine_id, site_id; `q`. */
  listUnbilledWork(query: TenantListQuery, signal?: AbortSignal): Promise<Page<UnbilledJobDto>> {
    return tenantPage('/tenant/unbilled-work', unbilledPage, query, 'unbilled work', signal);
  },
  /** GET /tenant/idle-machines (listIdleMachines). Filter: category_id; `q` = asset code or name. */
  listIdleMachines(query: TenantListQuery, signal?: AbortSignal): Promise<Page<IdleMachineDto>> {
    return tenantPage('/tenant/idle-machines', idlePage, query, 'idle machines', signal);
  },
  /** GET /tenant/site-checkins (listSiteCheckins): everyone's, newest first. Filters: staff_id,
   * job_site_id, day_from, day_to; `q` = person's name. */
  listCheckins(query: TenantListQuery, signal?: AbortSignal): Promise<Page<SiteCheckinDto>> {
    return tenantPage('/tenant/site-checkins', checkinPage, query, 'site check-ins', signal);
  },
  /** GET /tenant/site-checkins/{id} (getSiteCheckin). */
  getCheckin(checkinId: string, signal?: AbortSignal): Promise<SiteCheckinDto> {
    return tenantGet(
      `/tenant/site-checkins/${seg(checkinId)}`,
      siteCheckinSchema,
      'site check-in',
      signal,
    );
  },
  /** GET /tenant/site-checkins/mine (getMySiteCheckins): own schedule and check-ins. */
  mine(query: PeriodQuery, signal?: AbortSignal): Promise<MySiteCheckinsDto> {
    return tenantGet('/tenant/site-checkins/mine', mySiteCheckinsSchema, 'my check-ins', signal, {
      day_from: query.day_from,
      day_to: query.day_to,
    });
  },
  /** POST /tenant/site-checkins (recordSiteCheckin); replaying a client_id returns the stored one. */
  record(body: SiteCheckinIn): Promise<SiteCheckinDto> {
    return tenantSend(
      'post',
      '/tenant/site-checkins',
      body,
      siteCheckinSchema,
      'site check-in',
      body.client_id,
    );
  },
};
