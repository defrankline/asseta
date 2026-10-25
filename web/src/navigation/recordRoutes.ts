/**
 * Exact-record routes of the accountability records (DEC-030 G5). Notifications carry
 * `data.kind` + `data.record_id` and link to `<list route>/<id>`; the same table drives web links.
 */
export const CASH_BASE = '/tenant/finance/cash';

export const RECORD_LIST_ROUTES = {
  CASH_TRANSFER: `${CASH_BASE}/transfers`,
  CASH_FLOAT: `${CASH_BASE}/floats`,
  CASH_VARIANCE: `${CASH_BASE}/variances`,
  CASH_RETENTION: `${CASH_BASE}/retentions`,
  CUSTODY_ADJUSTMENT: `${CASH_BASE}/adjustments`,
  CASH_REMITTANCE: `${CASH_BASE}/remittances`,
  REMITTANCE_OVERDUE: `${CASH_BASE}/remittance-overdue`,
  HOURS_DISCOUNT: '/tenant/hours/discounts',
  HOURS_CREDIT: '/tenant/hours/credit',
  HOURS_TRANSFER: '/tenant/hours/transfers',
  HOURS_CANCELLATION: '/tenant/hours/cancellations',
  METER_BASELINE: '/tenant/meter-baselines',
  METER_CORRECTION: '/tenant/meter-corrections',
  ENGINE_HOURS_CLASSIFICATION: '/tenant/engine-hours/classifications',
} as const;

export type RecordKind = keyof typeof RECORD_LIST_ROUTES;

/** Route pattern of a record's detail page (`<list>/:id`). */
export const recordRoutePattern = (kind: RecordKind): string => `${RECORD_LIST_ROUTES[kind]}/:id`;

/** The detail page of one record. */
export function recordPath(kind: RecordKind, id: string): string {
  return `${RECORD_LIST_ROUTES[kind]}/${encodeURIComponent(id)}`;
}

export function isRecordKind(kind: unknown): kind is RecordKind {
  return typeof kind === 'string' && Object.prototype.hasOwnProperty.call(RECORD_LIST_ROUTES, kind);
}

/** Notification / realtime entity types of the records above (backend `notification.rules.RECORDS`). */
export const RECORD_KIND_BY_ENTITY: Readonly<Record<string, RecordKind>> = {
  cash_transfer: 'CASH_TRANSFER',
  supervisor_cash_custody: 'CASH_FLOAT',
  cash_variance: 'CASH_VARIANCE',
  cash_retention: 'CASH_RETENTION',
  custody_adjustment: 'CUSTODY_ADJUSTMENT',
  cash_handover: 'CASH_REMITTANCE',
  cash_remittance_overdue: 'REMITTANCE_OVERDUE',
  customer_discount: 'HOURS_DISCOUNT',
  credit_arrangement: 'HOURS_CREDIT',
  hours_transfer: 'HOURS_TRANSFER',
  hours_cancellation: 'HOURS_CANCELLATION',
  baseline: 'METER_BASELINE',
  correction: 'METER_CORRECTION',
  classification: 'ENGINE_HOURS_CLASSIFICATION',
};

/** Hours records belong to the customer hours capability. */
export const HOURS_RECORD_KINDS: ReadonlySet<RecordKind> = new Set([
  'HOURS_DISCOUNT',
  'HOURS_CREDIT',
  'HOURS_TRANSFER',
  'HOURS_CANCELLATION',
]);
