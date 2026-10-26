/**
 * Customer hours over days (DEC-031 P2 / P3): low-balance warnings and the customer hours statement
 * (JSON + PDF). Gated by the CUSTOMER_HOURS capability; reading needs `tenant.hours.read`.
 */
import { array, boolean, object, string, type Schema } from 'yup';
import { http } from '../client';
import type {
  HoursStatementDto,
  HoursStatementLineDto,
  HoursStatementPurchaseDto,
  HoursStatementTotalsDto,
  HoursStatementUsageDto,
  LowBalanceAlertDto,
  LowBalanceSmsStatus,
} from '../hoursTypes';
import { requestContext } from '../requestContext';
import type { Page } from '../types';
import { LEDGER_ENTRY_TYPES, PURCHASE_STATUSES } from './hoursSchemas';
import { exportError, filenameFromDisposition } from './reportService';
import { bool, id, int, nullableId, nullableText, oneOf, text } from './schemaKit';
import {
  seg,
  tenantGet,
  tenantPage,
  tenantPageSchema,
  type TenantListQuery,
} from './tenantRequest';

const optionalText = () => string().nullable().default(null);

export const LOW_BALANCE_SMS_STATUSES: readonly LowBalanceSmsStatus[] = [
  'NOT_REQUESTED',
  'PENDING',
  'QUEUED',
  'NO_PHONE',
];

export const lowBalanceAlertSchema: Schema<LowBalanceAlertDto> = object({
  id: id(),
  purchase_id: id(),
  purchase_number: optionalText(),
  customer_id: id(),
  customer_name: optionalText(),
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  sequence: int(),
  threshold_hours: text(),
  remaining_hours: text(),
  available_hours: text(),
  crossed_at: text(),
  rearmed_at: nullableText(),
  notify_customer: bool(),
  customer_sms_status: oneOf(LOW_BALANCE_SMS_STATUSES),
  customer_sms_id: nullableId(),
  policy_version: text(),
});

const machineRef = () => ({
  machine_id: id(),
  machine_code: optionalText(),
  machine_name: optionalText(),
});

const totalsSchema: Schema<HoursStatementTotalsDto> = object({
  opening_balance: text(),
  bought: text(),
  activated: text(),
  used: text(),
  transferred_in: text(),
  transferred_out: text(),
  expired: text(),
  cancelled: text(),
  closing_balance: text(),
  provisional_at_close: text(),
  awaiting_activation: text(),
});

const statementPurchaseSchema: Schema<HoursStatementPurchaseDto> = object({
  purchase_id: id(),
  purchase_number: optionalText(),
  ...machineRef(),
  status: oneOf(PURCHASE_STATUSES),
  bought_at: text(),
  hours: text(),
  activated: text(),
  amount: text(),
  currency: text(),
  effective_rate: text(),
  remaining_at_close: text(),
  next_expiry_at: nullableText(),
  expiring_hours: text(),
  cancelled_at: nullableText(),
});

const usageSchema: Schema<HoursStatementUsageDto> = object({
  day: text(),
  job_id: nullableId(),
  job_number: optionalText(),
  ...machineRef(),
  hours: text(),
  basis: oneOf(['DAILY', 'FINAL'] as const),
  job_running: boolean().required(),
});

const lineSchema: Schema<HoursStatementLineDto> = object({
  entry_id: id(),
  occurred_at: text(),
  day: text(),
  entry_type: oneOf(LEDGER_ENTRY_TYPES),
  hours: text(),
  balance_after: text(),
  purchase_id: id(),
  purchase_number: optionalText(),
  ...machineRef(),
  job_id: nullableId(),
  job_number: optionalText(),
  reason: nullableText(),
});

export const hoursStatementSchema: Schema<HoursStatementDto> = object({
  customer_id: id(),
  customer_name: optionalText(),
  machine_id: nullableId(),
  machine_code: optionalText(),
  machine_name: optionalText(),
  date_from: text(),
  date_to: text(),
  timezone: text(),
  generated_at: text(),
  pdf_path: text(),
  totals: totalsSchema,
  purchases: array(statementPurchaseSchema).required(),
  usage: array(usageSchema).required(),
  lines: array(lineSchema).required(),
});

const alertPage = tenantPageSchema(lowBalanceAlertSchema);
const ALERTS = '/tenant/hours-low-balance-alerts';

export interface StatementQuery {
  machine_id?: string | undefined;
  date_from?: string | undefined;
  date_to?: string | undefined;
}

/** A downloaded statement PDF. */
export interface PdfFile {
  blob: Blob;
  filename: string;
}

/** `pdf_path` is absolute (`/api/v1/tenant/...`); the client already prefixes the API base. */
export function apiRelativePath(path: string): string {
  return path.replace(/^\/api\/v\d+(?=\/)/, '');
}

export const hoursStatementService = {
  /** GET /tenant/customers/{id}/hours-statement (getCustomerHoursStatement); ≤ 366 tenant-local days. */
  statement(
    customerId: string,
    query: StatementQuery,
    signal?: AbortSignal,
  ): Promise<HoursStatementDto> {
    return tenantGet(
      `/tenant/customers/${seg(customerId)}/hours-statement`,
      hoursStatementSchema,
      'hours statement',
      signal,
      { machine_id: query.machine_id, date_from: query.date_from, date_to: query.date_to },
    );
  },
  /** GET the statement's `pdf_path` (downloadCustomerHoursStatementPdf); the download is audited. */
  async downloadPdf(pdfPath: string): Promise<PdfFile> {
    const response = await http.get<Blob>(apiRelativePath(pdfPath), {
      responseType: 'blob',
      tenantScoped: true,
      validateStatus: () => true,
    });
    if (response.status < 200 || response.status >= 300) {
      const error = await exportError(response.status, response.data);
      if (error.status === 401) requestContext.onUnauthorized();
      throw error;
    }
    const headers = response.headers as Record<string, unknown>;
    const disposition = headers['content-disposition'];
    return {
      blob: response.data,
      filename: filenameFromDisposition(
        typeof disposition === 'string' ? disposition : null,
        'hours-statement.pdf',
      ),
    };
  },
  /** GET /tenant/hours-low-balance-alerts (listHoursLowBalanceAlerts). Filters: purchase, customer, machine, armed. */
  listLowBalanceAlerts(
    query: TenantListQuery,
    signal?: AbortSignal,
  ): Promise<Page<LowBalanceAlertDto>> {
    return tenantPage(ALERTS, alertPage, query, 'low-balance warnings', signal);
  },
  /** GET /tenant/hours-low-balance-alerts/{id} (getHoursLowBalanceAlert). */
  getLowBalanceAlert(alertId: string, signal?: AbortSignal): Promise<LowBalanceAlertDto> {
    return tenantGet(
      `${ALERTS}/${seg(alertId)}`,
      lowBalanceAlertSchema,
      'low-balance warning',
      signal,
    );
  },
};
