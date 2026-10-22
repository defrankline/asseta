import { array, mixed, object, string, type Schema } from 'yup';
import type { TenantOverviewDto } from '../types';
import { int, nullableInt, nullableText, text } from './schemaKit';
import { tenantGet } from './tenantRequest';

function isCountMap(value: unknown): value is Record<string, number> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === 'number')
  );
}

const countMap = () => mixed<Record<string, number>>(isCountMap).required();

const severityFields = {
  info: int(),
  warning: int(),
  critical: int(),
};

const connectivityFields = {
  live: int(),
  recent: int(),
  stale: int(),
  offline: int(),
  never: int(),
  no_tracker: int(),
};

const fleetSchema = object({
  machines: int(),
  connectivity: object(connectivityFields).required(),
  reported_work_state: countMap(),
  engine_on_verified: int(),
  open_alerts: object(severityFields).required(),
  latest_source_at: nullableText(),
})
  .nullable()
  .defined()
  .default(null);

const workSchema = object({
  jobs_by_status: countMap(),
  pending_approvals: nullableInt(),
  readings_needing_review: nullableInt(),
  open_exceptions: nullableInt(),
  latest_source_at: nullableText(),
})
  .nullable()
  .defined()
  .default(null);

const currencySchema = object({
  currency: text(),
  receivables_outstanding: text(),
  receivables_overdue: text(),
  overdue_invoices: int(),
  verified_receipts_mtd: text(),
  approved_expenses_mtd: text(),
  cash_with_supervisors: text(),
});

const moneySchema = object({
  month_start: text(),
  currencies: array(currencySchema).required(),
  latest_source_at: nullableText(),
})
  .nullable()
  .defined()
  .default(null);

const nullableSeverity = () => object(severityFields).nullable().defined().default(null);

const riskSchema = object({
  open_cases: nullableSeverity(),
  signals_last_7_days: nullableSeverity(),
  latest_source_at: nullableText(),
})
  .nullable()
  .defined()
  .default(null);

export const overviewSchema: Schema<TenantOverviewDto> = object({
  tenant_id: string().required(),
  as_of: string().required(),
  timezone: text(),
  fleet: fleetSchema,
  work: workSchema,
  money: moneySchema,
  risk: riskSchema,
});

export const overviewService = {
  /** GET /tenant/overview (getTenantOverview): sections are null without their permission. */
  get(signal?: AbortSignal): Promise<TenantOverviewDto> {
    return tenantGet('/tenant/overview', overviewSchema, 'tenant overview', signal);
  },
};
