/**
 * API DTOs. Contract types are aliases of ./generated/schema.ts (generated from contracts/openapi.json by
 * `npm run gen:api`), so any backend contract drift fails `npm run typecheck`.
 */
import type { components } from './generated/schema';

type Schemas = components['schemas'];

export type Uuid = string;

export type ErrorDetail = Schemas['ErrorDetail'];

export type ErrorEnvelope = Schemas['ErrorEnvelope'];

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type SortDirection = 'asc' | 'desc';

export interface ListQuery {
  page: number;
  page_size: number;
  /** Field name, prefixed with `-` for descending, e.g. `-created_at`. */
  sort?: string;
  q?: string;
}

/** Navigation entry granted via role_menus. */
/** Navigation entry granted via role_menus. */
export type MenuDto = Schemas['MenuDto'];

/** @deprecated alias kept for readability at call sites. */
export type TenantMenu = MenuDto;

/** Commercial/entitlement access state of a tenant (set by platform billing). */
export type TenantAccessState = Schemas['TenantAccessState'];

export type TenantAccess = Schemas['TenantAccessDto'];

export type MeResponse = Schemas['MeDto'];

export type HealthStatus = HealthReadyResponse['status'];

export type HealthCheck = Schemas['CheckResult'];

export type HealthReadyResponse = Schemas['ReadinessDto'];

// ---- Platform billing & tenancy (Gate 1 platform console) ----

export type Cadence = Schemas['Cadence'];
export type MidCycleAddPolicy = Schemas['MidCycleAddPolicy'];
export type MidCycleRemovePolicy = Schemas['MidCycleRemovePolicy'];
export type RoundingMode = Schemas['RoundingMode'];
export type SubscriptionStatus = Schemas['SubscriptionStatus'];
export type TenantStatus = Schemas['TenantStatus'];
export type VerificationStatus = Schemas['VerificationStatus'];
export type InvoiceStatus = Schemas['InvoiceStatus'];
export type InvoiceLineType = Schemas['InvoiceLineType'];
export type PaymentMethod = Schemas['PaymentMethod'];
export type PaymentStatus = Schemas['PaymentStatus'];
export type PendingChargeStatus = Schemas['PendingChargeStatus'];
export type EnrollmentEndReason = Schemas['EnrollmentEndReason'];

export type PlatformDashboardDto = Schemas['PlatformDashboardDto'];
export type CurrencyTotalsDto = Schemas['CurrencyTotalsDto'];

export type TenantDto = Schemas['TenantDto'];
export type TenantOnboardIn = Schemas['TenantOnboardIn'];
export type OnboardResultDto = Schemas['OnboardResultDto'];
export type VerificationIn = Schemas['VerificationIn'];

export type SubscriptionDto = Schemas['SubscriptionDto'];
export type TransitionIn = Schemas['TransitionIn'];
export type EntitlementDto = Schemas['EntitlementDto'];
export type RateVersionDto = Schemas['RateVersionDto'];
export type RateTermsIn = Schemas['RateTermsIn'];
export type NewRateVersionIn = Schemas['NewRateVersionIn'];
export type EnrollmentDto = Schemas['EnrollmentDto'];
export type EndEnrollmentIn = Schemas['EndEnrollmentIn'];
export type EnrollmentResultDto = Schemas['EnrollmentResultDto'];
export type ChargePreviewDto = Schemas['ChargePreviewDto'];
export type PendingChargeDto = Schemas['PendingChargeDto'];
export type OverridePendingChargeIn = Schemas['OverridePendingChargeIn'];

export type InvoiceDto = Schemas['InvoiceDto'];
export type InvoiceLineDto = Schemas['InvoiceLineDto'];
export type GenerateInvoicesIn = Schemas['GenerateInvoicesIn'];
export type GenerateInvoicesDto = Schemas['GenerateInvoicesDto'];
export type CreditAdjustmentIn = Schemas['CreditAdjustmentIn'];

export type PaymentDto = Schemas['PaymentDto'];
export type RecordPaymentIn = Schemas['RecordPaymentIn'];
export type PaymentDecisionIn = Schemas['PaymentDecisionIn'];

export type TenantPage = Schemas['Page_TenantDto_'];
export type InvoicePage = Schemas['Page_InvoiceDto_'];
export type PaymentPage = Schemas['Page_PaymentDto_'];
