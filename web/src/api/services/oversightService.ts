/**
 * Oversight (DEC-031 Phase 5): the people scorecard (M1) and idle machines (M2). Each endpoint needs
 * its tenant capability (SCORECARD, IDLE_MACHINES); the server refuses with <CAPABILITY>_DISABLED
 * while it is off.
 */
import { array, mixed, object, string, type Schema } from 'yup';
import type {
  AmountByCurrencyDto,
  CashHeldDto,
  IdleMachineDto,
  ScorecardDetailDto,
  ScorecardItem,
  ScorecardRecordDto,
  ScorecardRecordItem,
  ScorecardRowDto,
} from '../oversightTypes';
import type { Page } from '../types';
import { bool, id, int, nullableId, nullableInt, nullableText, oneOf, text } from './schemaKit';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
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
  'REFUSED_ATTEMPT',
];
const RECORD_ITEMS: readonly ScorecardRecordItem[] = [...SCORECARD_ITEMS, 'PATTERN_SIGNAL'];
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
  refused_attempts: int(),
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

export const idleMachineSchema: Schema<IdleMachineDto> = object({
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  category_id: nullableId(),
  idle_since: text(),
  idle_days: int(),
  last_engine_activity_at: nullableText(),
  last_machine_report_id: nullableId(),
  last_machine_report_number: optionalText(),
});

const scorecardPage = tenantPageSchema(scorecardRowSchema);
const idlePage = tenantPageSchema(idleMachineSchema);

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
  /** GET /tenant/idle-machines (listIdleMachines). Filter: category_id; `q` = asset code or name. */
  listIdleMachines(query: TenantListQuery, signal?: AbortSignal): Promise<Page<IdleMachineDto>> {
    return tenantPage('/tenant/idle-machines', idlePage, query, 'idle machines', signal);
  },
};
