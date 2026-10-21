import { array, type Schema } from 'yup';
import { apiClient } from '../client';
import type {
  ChargePreviewDto,
  EndEnrollmentIn,
  EnrollmentDto,
  EnrollmentResultDto,
  EntitlementDto,
  GenerateInvoicesDto,
  InvoiceDto,
  NewRateVersionIn,
  OverridePendingChargeIn,
  PendingChargeDto,
  RateVersionDto,
  TransitionIn,
} from '../types';
import { parseResponse } from '../validation';
import {
  chargePreviewSchema,
  enrollmentResultSchema,
  enrollmentSchema,
  entitlementSchema,
  generateInvoicesSchema,
  invoiceSchema,
  pendingChargeSchema,
  rateVersionSchema,
} from './billingSchemas';

const rateListSchema: Schema<RateVersionDto[]> = array(rateVersionSchema).required();
const enrollmentListSchema: Schema<EnrollmentDto[]> = array(enrollmentSchema).required();
const pendingListSchema: Schema<PendingChargeDto[]> = array(pendingChargeSchema).required();

const sub = (sid: string) => `/platform/subscriptions/${encodeURIComponent(sid)}`;
const opts = (signal?: AbortSignal) => (signal ? { signal } : undefined);

/** A null body ("no charge / nothing due") is a valid response for previews. */
function parseNullable<T>(schema: Schema<T>, data: unknown, what: string): T | null {
  return data === null || data === '' ? null : parseResponse(schema, data, what);
}

export const subscriptionService = {
  /** POST /subscriptions/{sid}/transitions (transitionSubscription). */
  async transition(
    sid: string,
    body: TransitionIn,
    idempotencyKey: string,
  ): Promise<EntitlementDto> {
    const data = await apiClient.post<unknown>(`${sub(sid)}/transitions`, body, { idempotencyKey });
    return parseResponse(entitlementSchema, data, 'entitlement');
  },

  /** POST /subscriptions/{sid}/entitlement/evaluate (evaluateEntitlement). */
  async evaluateEntitlement(sid: string, idempotencyKey: string): Promise<EntitlementDto> {
    const data = await apiClient.post<unknown>(`${sub(sid)}/entitlement/evaluate`, null, {
      idempotencyKey,
    });
    return parseResponse(entitlementSchema, data, 'entitlement');
  },

  /** GET /subscriptions/{sid}/rate-versions (listRateVersions). */
  async listRateVersions(sid: string, signal?: AbortSignal): Promise<RateVersionDto[]> {
    const data = await apiClient.get<unknown>(`${sub(sid)}/rate-versions`, opts(signal));
    return parseResponse(rateListSchema, data, 'rate versions');
  },

  /** POST /subscriptions/{sid}/rate-versions (createRateVersion). */
  async createRateVersion(
    sid: string,
    body: NewRateVersionIn,
    idempotencyKey: string,
  ): Promise<RateVersionDto> {
    const data = await apiClient.post<unknown>(`${sub(sid)}/rate-versions`, body, {
      idempotencyKey,
    });
    return parseResponse(rateVersionSchema, data, 'rate version');
  },

  /** GET /subscriptions/{sid}/enrollments (listEnrollments). */
  async listEnrollments(sid: string, signal?: AbortSignal): Promise<EnrollmentDto[]> {
    const data = await apiClient.get<unknown>(`${sub(sid)}/enrollments`, opts(signal));
    return parseResponse(enrollmentListSchema, data, 'enrollments');
  },

  /** POST .../enrollments/{eid}/end-preview (previewEndEnrollment). Read-only; null = no charge. */
  async previewEndEnrollment(
    sid: string,
    eid: string,
    body: EndEnrollmentIn,
    idempotencyKey: string,
  ): Promise<ChargePreviewDto | null> {
    const data = await apiClient.post<unknown>(
      `${sub(sid)}/enrollments/${encodeURIComponent(eid)}/end-preview`,
      body,
      { idempotencyKey },
    );
    return parseNullable(chargePreviewSchema, data, 'charge preview');
  },

  /** POST .../enrollments/{eid}/end (endEnrollment). */
  async endEnrollment(
    sid: string,
    eid: string,
    body: EndEnrollmentIn,
    idempotencyKey: string,
  ): Promise<EnrollmentResultDto> {
    const data = await apiClient.post<unknown>(
      `${sub(sid)}/enrollments/${encodeURIComponent(eid)}/end`,
      body,
      { idempotencyKey },
    );
    return parseResponse(enrollmentResultSchema, data, 'enrollment result');
  },

  /** GET /subscriptions/{sid}/pending-charges (listPendingCharges). */
  async listPendingCharges(sid: string, signal?: AbortSignal): Promise<PendingChargeDto[]> {
    const data = await apiClient.get<unknown>(`${sub(sid)}/pending-charges`, opts(signal));
    return parseResponse(pendingListSchema, data, 'pending charges');
  },

  /** PATCH /platform/pending-charges/{pid} (overridePendingCharge). */
  async overridePendingCharge(
    pid: string,
    body: OverridePendingChargeIn,
    idempotencyKey: string,
  ): Promise<PendingChargeDto> {
    const data = await apiClient.patch<unknown>(
      `/platform/pending-charges/${encodeURIComponent(pid)}`,
      body,
      { idempotencyKey },
    );
    return parseResponse(pendingChargeSchema, data, 'pending charge');
  },

  /** GET /subscriptions/{sid}/invoices/preview (previewNextInvoice). Null = nothing due. */
  async previewNextInvoice(
    sid: string,
    asOf: string | undefined,
    signal?: AbortSignal,
  ): Promise<InvoiceDto | null> {
    const data = await apiClient.get<unknown>(`${sub(sid)}/invoices/preview`, {
      ...(asOf !== undefined ? { params: { as_of: asOf } } : {}),
      ...(signal ? { signal } : {}),
    });
    return parseNullable(invoiceSchema, data, 'invoice preview');
  },

  /** POST /subscriptions/{sid}/invoices/generate (generateInvoices). Idempotent per period. */
  async generateInvoices(
    sid: string,
    asOf: string,
    idempotencyKey: string,
  ): Promise<GenerateInvoicesDto> {
    const data = await apiClient.post<unknown>(
      `${sub(sid)}/invoices/generate`,
      { as_of: asOf },
      { idempotencyKey },
    );
    return parseResponse(generateInvoicesSchema, data, 'generated invoices');
  },
};
