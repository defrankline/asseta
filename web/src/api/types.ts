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

// ---- Tenant console (Gate 2): fleet registry, trackers, geospatial, policy, tenant billing ----

export type MachineStatus = Schemas['MachineStatus'];
export type Ownership = Schemas['Ownership'];
export type MachineDto = Schemas['MachineDto'];
export type MachineCreateIn = Schemas['MachineCreateIn'];
export type MachineUpdateIn = Schemas['MachineUpdateIn'];
export type MachinePage = Schemas['Page_MachineDto_'];
export type CategoryDto = Schemas['CategoryDto'];
export type CategoryIn = Schemas['CategoryIn'];
export type AreaDto = Schemas['AreaDto'];
export type AreaIn = Schemas['AreaIn'];

export type StaffKind = Schemas['StaffKind'];
export type StaffDto = Schemas['StaffDto'];
export type StaffIn = Schemas['StaffIn'];
export type StaffPage = Schemas['Page_StaffDto_'];
export type AssignmentRole = Schemas['AssignmentRole'];
export type AssignmentDto = Schemas['AssignmentDto'];
export type AssignIn = Schemas['AssignIn'];
export type EndAssignmentIn = Schemas['EndAssignmentIn'];

export type Capability = Schemas['Capability'];
export type CapabilityDto = Schemas['CapabilityDto'];
export type ProvisioningState = Schemas['ProvisioningState'];
export type TelemetryAdapterKind = Schemas['TelemetryAdapterKind'];
export type TrackerModelDto = Schemas['TrackerModelDto'];
export type TrackerDto = Schemas['TrackerDto'];
export type TrackerIn = Schemas['TrackerIn'];
export type TrackerPage = Schemas['Page_TrackerDto_'];
export type TrackerAssignmentDto = Schemas['TrackerAssignmentDto'];
export type AssignTrackerIn = Schemas['AssignTrackerIn'];
export type UnassignTrackerIn = Schemas['UnassignTrackerIn'];
export type TrackerStateIn = Schemas['TrackerStateIn'];
export type IngestionStatus = Schemas['IngestionStatus'];
export type QuarantineReason = Schemas['QuarantineReason'];
export type IngestionEventDto = Schemas['IngestionEventDto'];
export type IngestionEventPage = Schemas['Page_IngestionEventDto_'];

export type Connectivity = Schemas['Connectivity'];
export type Observed = Schemas['Observed'];
export type Compliance = Schemas['Compliance'];
export type MachineMapDto = Schemas['MachineMapDto'];
export type HistoryDto = Schemas['HistoryDto'];
export type TrackPointDto = Schemas['TrackPointDto'];
export type StopDto = Schemas['StopDto'];
export type SiteVisitDto = Schemas['SiteVisitDto'];

export type GeoPoint = Schemas['GeoPoint'];
export type GeoPolygon = Schemas['GeoPolygon'];
export type GeoLineString = Schemas['GeoLineString'];
export type JobSiteDto = Schemas['JobSiteDto'];
export type JobSiteIn = Schemas['JobSiteIn'];
export type GeofenceKind = Schemas['GeofenceKind'];
export type GeofenceShape = Schemas['GeofenceShape'];
export type GeofenceDto = Schemas['GeofenceDto'];
export type GeofenceIn = Schemas['GeofenceIn'];

export type AlertStatus = Schemas['AlertStatus'];
export type AlertType = Schemas['AlertType'];
export type AlertSeverity = Schemas['AlertSeverity'];
export type AlertDto = Schemas['AlertDto'];
export type AlertActionIn = Schemas['AlertActionIn'];
export type AlertPage = Schemas['Page_AlertDto_'];

export type PolicyType = Schemas['PolicyType'];
export type PolicyScope = Schemas['PolicyScope'];
export type EffectivePolicyDto = Schemas['EffectivePolicyDto'];
export type PolicyVersionDto = Schemas['PolicyVersionDto'];
export type PolicyVersionIn = Schemas['PolicyVersionIn'];

export type EnrollAssetIn = Schemas['EnrollAssetIn'];
