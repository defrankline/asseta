import { array, object, string, type Schema } from 'yup';
import type {
  EmployeeAccountabilityDto,
  EmployeeRecordDto,
  HoursFigureDto,
  CountFigureDto,
  LookupMatchDto,
  LookupResultDto,
  MoneyFigureDto,
  MoneyLineDto,
  PendingItemDto,
  PurchaseQueueDto,
} from '../custodyTypes';
import { bool, id, int, nullableId, nullableInt, nullableText, text } from './schemaKit';

/** Management view of guideline sections 8 and 10: figures with their `route` (DEC-032 Phase 4). */

const optText = () => string().nullable();

const moneyLine: Schema<MoneyLineDto> = object({ currency: text(), count: int(), amount: text() });
const moneyFigure: Schema<MoneyFigureDto> = object({
  lines: array(moneyLine).required(),
  count: int(),
  route: text(),
});
const hoursFigure: Schema<HoursFigureDto> = object({ hours: text(), count: int(), route: text() });
const countFigure: Schema<CountFigureDto> = object({ count: int(), route: text() });

const queue: Schema<PurchaseQueueDto> = object({
  count: int(),
  hours: text(),
  amounts: array(moneyLine).required(),
  route: text(),
  items: array(
    object({
      purchase_id: id(),
      purchase_number: optText(),
      customer_id: id(),
      customer_name: optText(),
      hours_awaiting: text(),
      amount_open: text(),
      currency: text(),
      created_at: text(),
      route: text(),
    }),
  ).required(),
});

const hoursSection = object({
  purchased: hoursFigure,
  purchased_value: moneyFigure,
  activated: hoursFigure,
  consumed: hoursFigure,
  remaining: hoursFigure,
  remaining_by_customer: array(
    object({
      customer_id: id(),
      customer_name: optText(),
      remaining: text(),
      activated: text(),
      consumed: text(),
      route: text(),
    }),
  ).required(),
  remaining_customers_total: int(),
  unpaid_purchases: queue,
  unconfirmed_purchases: queue,
  awaiting_activation: queue,
});

const typeCount = object({ type: text(), count: int(), route: text() });

const operationsSection = object({
  operating_hours: hoursFigure,
  customer_hours: hoursFigure,
  authorized_non_customer_hours: hoursFigure,
  unexplained_hours: hoursFigure,
  by_excavator: array(
    object({
      machine_id: id(),
      machine_code: optText(),
      machine_name: optText(),
      operating_hours: text(),
      customer_hours: text(),
      authorized_hours: text(),
      unexplained_hours: text(),
      route: text(),
    }),
  ).required(),
  meter_discrepancies: object({
    count: int(),
    by_type: array(typeCount).required(),
    route: text(),
  }),
  pending_reports: countFigure,
  returned_reports: countFigure,
});

const cashSection = object({
  collected: moneyFigure,
  held_by_employee: array(
    object({
      staff_member_id: id(),
      staff_member_name: optText(),
      currency: text(),
      outstanding: text(),
      in_transit_out: text(),
      claimed_unverified_handovers: text(),
      pending_floats: text(),
      approved_retention: text(),
      route: text(),
    }),
  ).required(),
  transferred: moneyFigure,
  in_transit: moneyFigure,
  declared_for_remittance: moneyFigure,
  confirmed_by_company: moneyFigure,
  outstanding: moneyFigure,
  unconfirmed_remittances: moneyFigure,
  disputed_remittances: moneyFigure,
  disputed_transfers: moneyFigure,
});

const kindCount = object({
  kind: text(),
  count: int(),
  oldest_at: nullableText(),
  route: text(),
});

export const pendingItemSchema: Schema<PendingItemDto> = object({
  kind: text(),
  record_type: text(),
  id: id(),
  reference: nullableText(),
  status: text(),
  requested_by: nullableId(),
  requested_by_name: optText(),
  requested_at: text(),
  amount: nullableText(),
  unit: nullableText(),
  currency: nullableText(),
  customer_id: nullableId(),
  customer_name: optText(),
  machine_id: nullableId(),
  machine_code: optText(),
  machine_name: optText(),
  staff_member_id: nullableId(),
  staff_member_name: optText(),
  route: nullableText(),
});

const exceptionsSection = object({
  unexplained_engine_hours: hoursFigure,
  shortages: moneyFigure,
  overages: moneyFigure,
  shortages_opened_in_period: moneyFigure,
  overages_opened_in_period: moneyFigure,
  pending_adjustments: object({
    total: int(),
    by_kind: array(kindCount).required(),
    oldest: array(pendingItemSchema).required(),
    route: text(),
  }),
  unauthorized_attempts: object({
    since: text(),
    permission_denied: int(),
    segregation_of_duties: int(),
    route: text(),
  }),
  unconfirmed_payments: moneyFigure,
  outstanding_approvals: object({
    total: int(),
    by_kind: array(kindCount).required(),
  }),
  overdue_reports: object({
    missing_daily_reports: countFigure,
    remittances_overdue_today: countFigure,
    total: int(),
  }),
  unresolved_variances: object({
    total: int(),
    by_source: array(
      object({
        source: text(),
        unit: text(),
        count: int(),
        amounts: array(moneyLine).required(),
        route: text(),
      }),
    ).required(),
  }),
  changeover_jobs_awaiting_approval: object({
    count: int(),
    oldest_days: nullableInt(),
    items: array(
      object({
        job_id: id(),
        job_number: optText(),
        machine_id: id(),
        machine_code: optText(),
        machine_name: optText(),
        customer_id: id(),
        customer_name: optText(),
        changed_over_at: text(),
        days_waiting: int(),
        route: text(),
      }),
    ).required(),
  }),
});

/** Fields of the summary added by DEC-032 Phase 4 (each null when hidden or switched off). */
export const summarySectionFields = () => ({
  period: object({ date_from: nullableText(), date_to: nullableText() }).nullable().default(null),
  hours_section: hoursSection.nullable().default(null),
  operations_section: operationsSection.nullable().default(null),
  cash_section: cashSection.nullable().default(null),
  exceptions_section: exceptionsSection.nullable().default(null),
});

const record: Schema<EmployeeRecordDto> = object({
  record_type: text(),
  id: nullableId(),
  reference: optText(),
  status: optText(),
  occurred_at: text(),
  amount: optText(),
  unit: optText(),
  currency: optText(),
  label: optText(),
  counterparty_staff_id: optText(),
  counterparty_staff_name: optText(),
  route: optText(),
});
const records = () => array(record).required();

export const employeeAccountabilitySchema: Schema<EmployeeAccountabilityDto> = object({
  date_from: text(),
  date_to: text(),
  identity: object({
    staff_member_id: id(),
    full_name: text(),
    employee_code: nullableText(),
    kind: text(),
    phone: nullableText(),
    is_active: bool(),
    login_email: nullableText(),
    user_id: nullableId(),
    roles: array(text()).required(),
  }),
  cash_held: array(
    object({
      currency: text(),
      outstanding: text(),
      in_transit_in: text(),
      in_transit_out: text(),
      claimed_unverified_handovers: text(),
      pending_floats: text(),
      approved_retention: text(),
      pending_spending: text(),
      staff_member_id: id(),
      as_of: text(),
    }),
  ).required(),
  collections: records(),
  floats: records(),
  transfers_in: records(),
  transfers_out: records(),
  remittances: records(),
  spending: records(),
  retentions: records(),
  differences: records(),
  custody_adjustments: records(),
  reports_submitted: records(),
  approvals_made: records(),
  adjustments_requested: records(),
  adjustments_decided: records(),
  scorecard_items: records(),
  scorecard_visible: bool(),
  truncated: array(text()).required(),
});

const match: Schema<LookupMatchDto> = object({
  record_type: text(),
  id: id(),
  reference: nullableText(),
  route: nullableText(),
  status: nullableText(),
  recorded_by: optText(),
  recorded_by_name: optText(),
  recorded_at: optText(),
  decided_by: optText(),
  decided_by_name: optText(),
  decided_at: optText(),
  customer_id: optText(),
  customer_name: optText(),
  machine_id: optText(),
  machine_code: optText(),
  machine_name: optText(),
  staff_member_id: optText(),
  staff_member_name: optText(),
  amount: optText(),
  currency: optText(),
  balance_outstanding: optText(),
  balance_unit: optText(),
  hours_remaining: optText(),
});

export const lookupResultSchema: Schema<LookupResultDto> = object({
  reference: text(),
  matches: array(match).required(),
});
