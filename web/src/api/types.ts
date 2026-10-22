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

/** Navigation entry granted via role_menus; `group` is the key of its MenuGroupDto. */
export type MenuDto = Schemas['MenuDto'];

/** Side-navigation section (parent of menus); listed only when it holds a visible menu. */
export type MenuGroupDto = Schemas['MenuGroupDto'];

/** @deprecated alias kept for readability at call sites. */
export type TenantMenu = MenuDto;

/** Commercial/entitlement access state of a tenant (set by platform billing). */
export type TenantAccessState = Schemas['TenantAccessState'];

export type TenantAccess = Schemas['TenantAccessDto'];

export type MeResponse = Schemas['MeDto'];

export type PersonDto = Schemas['PersonDto'];

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

// ---- Tenant console (Gate 3): customers, contracts, rate cards, jobs, meter evidence ----

export type CustomerDto = Schemas['CustomerDto'];
export type CustomerIn = Schemas['CustomerIn'];
export type CustomerPage = Schemas['Page_CustomerDto_'];
export type ContractStatus = Schemas['ContractStatus'];
export type ContractDto = Schemas['ContractDto'];
export type ContractIn = Schemas['ContractIn'];
export type ContractPage = Schemas['Page_ContractDto_'];
export type RateCardDto = Schemas['RateCardDto'];
export type RateCardIn = Schemas['RateCardIn'];

export type JobStatus = Schemas['JobStatus'];
export type StandbyTreatment = Schemas['StandbyTreatment'];
export type JobDto = Schemas['JobDto'];
export type JobIn = Schemas['JobIn'];
export type JobPage = Schemas['Page_JobDto_'];
export type JobSummaryDto = Schemas['JobSummaryDto'];
export type JobTransitionIn = Schemas['JobTransitionIn'];
export type JobAction = JobTransitionIn['action'];
export type ActivityType = Schemas['ActivityType'];
export type ActivityDto = Schemas['ActivityDto'];
export type ActivityIn = Schemas['ActivityIn'];
export type AcknowledgementDto = Schemas['AcknowledgementDto'];
export type AcknowledgementIn = Schemas['AcknowledgementIn'];
export type AcknowledgementMethod = AcknowledgementIn['method'];

export type AttachmentDto = Schemas['AttachmentDto'];
export type AttachmentUploadIn = Schemas['Body_uploadAttachment'];
export type PhotoUrlDto = Schemas['PhotoUrlDto'];
export type CaptureMode = Schemas['CaptureMode'];
export type CaptureState = Schemas['CaptureState'];
export type ReadingKind = Schemas['ReadingKind'];
export type GpsStatus = Schemas['GpsStatus'];
export type GpsIn = Schemas['GpsIn'];
export type MeterCaptureDto = Schemas['MeterCaptureDto'];
export type MeterCaptureIn = Schemas['MeterCaptureIn'];
export type FindingDto = Schemas['FindingDto'];
export type CaptureResultDto = Schemas['CaptureResultDto'];
export type ExceptionType = Schemas['ExceptionType'];
export type ExceptionStatus = Schemas['ExceptionStatus'];
export type ExceptionDto = Schemas['ExceptionDto'];
export type ExceptionPage = Schemas['Page_ExceptionDto_'];
export type ReviewIn = Schemas['ReviewIn'];
export type ReviewOutcome = ReviewIn['outcome'];
export type ResetDto = Schemas['ResetDto'];
export type ResetIn = Schemas['ResetIn'];

// ---- Managed service (DEC-018): consented, audited platform access to a client tenant ----

export type MandateScope = Schemas['MandateScope'];
/** IN_FORCE | SCHEDULED | EXPIRED | REVOKED | ENDED (typed as string by the contract). */
export type MandateStatus = 'IN_FORCE' | 'SCHEDULED' | 'EXPIRED' | 'REVOKED' | 'ENDED';
export type MandateBadgeDto = Schemas['MandateBadgeDto'];
export type MandateDto = Schemas['MandateDto'];
export type MandateDetailDto = Schemas['MandateDetailDto'];
export type MandateAssignmentDto = Schemas['MandateAssignmentDto'];
export type MandateGrantIn = Schemas['MandateGrantIn'];
export type MandateAssignmentIn = Schemas['MandateAssignmentIn'];
export type MandateCloseIn = Schemas['MandateCloseIn'];
export type MandateActionDto = Schemas['MandateActionDto'];
export type ClientMandateDto = Schemas['ClientMandateDto'];
export type PlatformStaffDto = Schemas['PlatformStaffDto'];
export type AssignableRoleDto = Schemas['AssignableRoleDto'];

// ---- Tenant users & roles ----

export type MemberDto = Schemas['MemberDto'];
export type MemberRoleDto = Schemas['MemberRoleDto'];

// ---- Record lifecycle (details, optimistic edit, deactivate / reactivate; never deleted) ----

export type LifecycleChangeIn = Schemas['LifecycleChangeIn'];
export type CustomerUpdateIn = Schemas['CustomerUpdateIn'];
export type StaffUpdateIn = Schemas['StaffUpdateIn'];
export type JobSiteUpdateIn = Schemas['JobSiteUpdateIn'];
export type CategoryUpdateIn = Schemas['CategoryUpdateIn'];
export type AreaUpdateIn = Schemas['AreaUpdateIn'];
export type ExpenseCategoryDto = Schemas['ExpenseCategoryDto'];
export type ExpenseCategoryIn = Schemas['ExpenseCategoryIn'];
export type ExpenseCategoryUpdateIn = Schemas['ExpenseCategoryUpdateIn'];
export type ContractUpdateIn = Schemas['ContractUpdateIn'];
export type JobUpdateIn = Schemas['JobUpdateIn'];
export type TrackerUpdateIn = Schemas['TrackerUpdateIn'];
export type TrackerModelIn = Schemas['TrackerModelIn'];
export type TrackerModelUpdateIn = Schemas['TrackerModelUpdateIn'];
export type GatewayDto = Schemas['GatewayDto'];
export type GatewayIn = Schemas['GatewayIn'];
export type GatewayCreatedDto = Schemas['GatewayCreatedDto'];
export type TenantUpdateIn = Schemas['TenantUpdateIn'];

// ---- Tenant hire finance (Gate 5, R1-G): invoices, payments, receivables, cash custody ----

export type HireInvoiceDto = Schemas['HireInvoiceDto'];
export type HireInvoiceLineDto = Schemas['HireInvoiceLineDto'];
export type HireInvoiceStatus = Schemas['HireInvoiceStatus'];
export type HireInvoiceDraftIn = Schemas['HireInvoiceDraftIn'];
export type HireInvoiceIssueIn = Schemas['HireInvoiceIssueIn'];
export type HireInvoiceVoidIn = Schemas['HireInvoiceVoidIn'];
export type ChargeKind = Schemas['ChargeKind'];
export type InvoicePaymentState = NonNullable<HireInvoiceDto['payment_state']>;
export type CustomerPaymentDto = Schemas['CustomerPaymentDto'];
export type CustomerPaymentIn = Schemas['CustomerPaymentIn'];
export type HireAllocationDto = Schemas['HireAllocationDto'];
export type HireAllocationIn = Schemas['HireAllocationIn'];
export type HireAllocateIn = Schemas['HireAllocateIn'];
export type HirePaymentMethod = Schemas['HirePaymentMethod'];
export type SettlementStatus = Schemas['SettlementStatus'];
export type SettlementDecisionIn = Schemas['SettlementDecisionIn'];
export type CustomerBalanceDto = Schemas['CustomerBalanceDto'];
export type CustomerStatementDto = Schemas['CustomerStatementDto'];
export type StatementLineDto = Schemas['StatementLineDto'];
export type StatementLineKind = StatementLineDto['kind'];
export type CashCollectionIn = Schemas['CashCollectionIn'];
export type CashFloatIn = Schemas['CashFloatIn'];
export type CustodyEntryType = Schemas['CustodyEntryType'];
export type CashCustodyEntryDto = Schemas['CashCustodyEntryDto'];
export type CashCustodyBalanceDto = Schemas['CashCustodyBalanceDto'];
export type CashHandoverIn = Schemas['CashHandoverIn'];
export type CashHandoverDto = Schemas['CashHandoverDto'];
export type CashReconciliationDto = Schemas['CashReconciliationDto'];
export type CashReconciliationDayDto = Schemas['CashReconciliationDayDto'];
export type ProfitabilityDto = Schemas['ProfitabilityDto'];
export type ProfitabilityRowDto = Schemas['ProfitabilityRowDto'];
export type ProfitabilityGroupBy = ProfitabilityDto['group_by'];

// ---- Field expenses, fuel and approvals (Gate 5, R1-G) ----

export type ExpenseDto = Schemas['ExpenseDto'];
export type ExpenseIn = Schemas['ExpenseIn'];
export type ExpenseStatus = Schemas['ExpenseStatus'];
export type ExpensePaidFrom = Schemas['ExpensePaidFrom'];
export type FuelEventDto = Schemas['FuelEventDto'];
export type FuelEventIn = Schemas['FuelEventIn'];
export type FuelEventType = Schemas['FuelEventType'];
export type ApprovalRequestDto = Schemas['ApprovalRequestDto'];
export type ApprovalStatus = Schemas['ApprovalStatus'];
export type ApprovalDecisionIn = Schemas['ApprovalDecisionIn'];

// ---- Active system (DEC-022): notifications, platform commerce, SMS wallets ----

export type NotificationDto = Schemas['NotificationDto'];
export type NotificationTarget = Schemas['NotificationTarget'];
export type NotificationSeverity = Schemas['Severity'];
export type NotificationPriority = NotificationDto['priority'];
export type NotificationPage = Schemas['Page_NotificationDto_'];
export type NotificationPreferenceDto = Schemas['NotificationPreferenceDto'];
export type NotificationPreferencesIn = Schemas['NotificationPreferencesIn'];
export type NotificationPreferenceChangeIn = Schemas['NotificationPreferenceChangeIn'];
export type NotificationMarkReadResultDto = Schemas['NotificationMarkReadResultDto'];
export type NotificationUnreadCountDto = Schemas['NotificationUnreadCountDto'];
export type NotificationProfileDto = Schemas['NotificationProfileDto'];
export type NotificationProfileIn = Schemas['NotificationProfileIn'];
export type NotificationTestSendIn = Schemas['NotificationTestSendIn'];
export type NotificationTestSendResultDto = Schemas['NotificationTestSendResultDto'];
export type SmsDeliveryDto = Schemas['SmsDeliveryDto'];
export type SmsDeliveryStatus = Schemas['DeliveryStatus'];
export type SmsDeliveryPage = Schemas['Page_SmsDeliveryDto_'];

export type InvoiceKind = Schemas['InvoiceKind'];
export type FulfilmentStatus = Schemas['FulfilmentStatus'];
export type ProductDto = Schemas['ProductDto'];
export type ProductIn = Schemas['ProductIn'];
export type ProductUpdateIn = Schemas['ProductUpdateIn'];
export type ProductType = Schemas['ProductType'];
export type ProductPage = Schemas['Page_ProductDto_'];
export type AdHocInvoiceIn = Schemas['AdHocInvoiceIn'];
export type AdHocLineIn = Schemas['AdHocLineIn'];
export type VoidInvoiceIn = Schemas['VoidInvoiceIn'];
export type PaymentAllocationDto = Schemas['PaymentAllocationDto'];
export type LineAllocationIn = Schemas['LineAllocationIn'];
export type AllocatePaymentIn = Schemas['AllocatePaymentIn'];
export type SmsWalletDto = Schemas['SmsWalletDto'];
export type SmsWalletEntryDto = Schemas['SmsWalletEntryDto'];
export type SmsWalletEntryType = Schemas['SmsWalletEntryType'];
export type SmsWalletEntryPage = Schemas['Page_SmsWalletEntryDto_'];

// ---- Risk signals and investigation cases (ADR-007) ----
export type RuleCode = Schemas['RuleCode'];
export type SignalSeverity = Schemas['SignalSeverity'];
export type SignalStatus = Schemas['SignalStatus'];
export type SubjectType = Schemas['SubjectType'];
export type CaseStatus = Schemas['CaseStatus'];
export type CaseSourceType = Schemas['CaseSourceType'];
export type CaseNoteKind = Schemas['CaseNoteKind'];
export type CaseOutcomeKind = Schemas['CaseOutcomeKind'];
export type RiskSignalDto = Schemas['RiskSignalDto'];
export type RiskSignalPage = Schemas['Page_RiskSignalDto_'];
export type AnomalyCaseDto = Schemas['AnomalyCaseDto'];
export type AnomalyCasePage = Schemas['Page_AnomalyCaseDto_'];
export type AnomalyCaseDetailDto = Schemas['AnomalyCaseDetailDto'];
export type CaseSignalDto = Schemas['CaseSignalDto'];
export type CaseNoteDto = Schemas['CaseNoteDto'];
export type CaseOutcomeDto = Schemas['CaseOutcomeDto'];
export type CaseAssignIn = Schemas['CaseAssignIn'];
export type CaseNoteIn = Schemas['CaseNoteIn'];
export type CaseResolveIn = Schemas['CaseResolveIn'];
export type CaseReopenIn = Schemas['CaseReopenIn'];

// ---- Governed ML and baseline insights (ADR-007, Gate 6D) ----
export type ModelStatus = Schemas['ModelStatus'];
export type ModelAction = Schemas['ModelAction'];
export type ModelAlgorithm = Schemas['ModelAlgorithm'];
export type ReadinessState = Schemas['ReadinessState'];
export type DecisionState = Schemas['DecisionState'];
export type DriftSummaryLevel = Schemas['DriftSummaryLevel'];
export type InferenceOutcome = Schemas['InferenceOutcome'];
export type MlModelVersionDto = Schemas['MlModelVersionDto'];
export type MlEvaluationDto = Schemas['MlEvaluationDto'];
export type MlApprovalDto = Schemas['MlApprovalDto'];
export type MlManifestSummaryDto = Schemas['MlManifestSummaryDto'];
export type MlDriftFeatureDto = Schemas['MlDriftFeatureDto'];
export type MlDriftDto = Schemas['MlDriftDto'];
export type MlMonitoringDto = Schemas['MlMonitoringDto'];
export type MlModelVersionDetailDto = Schemas['MlModelVersionDetailDto'];
export type MlPredictionDto = Schemas['MlPredictionDto'];
export type MlInferenceAuditDto = Schemas['MlInferenceAuditDto'];
export type MlModelActionIn = Schemas['MlModelActionIn'];
export type MlSettingsDto = Schemas['MlSettingsDto'];
export type MlSettingsIn = Schemas['MlSettingsIn'];
export type MlReadinessDto = Schemas['MlReadinessDto'];
export type MlSnapshotRunIn = Schemas['MlSnapshotRunIn'];
export type MlSnapshotRunDto = Schemas['MlSnapshotRunDto'];
export type MlTrainingRunDto = Schemas['MlTrainingRunDto'];
export type TenantMlDeploymentDto = Schemas['TenantMlDeploymentDto'];
export type TenantMlStatusDto = Schemas['TenantMlStatusDto'];
export type TenantMlState = TenantMlStatusDto['state'];
export type TenantPredictionDto = Schemas['TenantPredictionDto'];
export type FuelEfficiencyInsightDto = Schemas['FuelEfficiencyInsightDto'];
export type WeeklyHoursDto = Schemas['WeeklyHoursDto'];
export type UtilisationInsightDto = Schemas['UtilisationInsightDto'];
export type CashFlowWeekDto = Schemas['CashFlowWeekDto'];
export type CashFlowInsightDto = Schemas['CashFlowInsightDto'];
export type TenantInsightsDto = Schemas['TenantInsightsDto'];
export type InsightStatus = FuelEfficiencyInsightDto['status'];
export type InsightTrend = NonNullable<UtilisationInsightDto['trend']>;
export type ManualOverrideItemDto = Schemas['ManualOverrideItemDto'];
export type ManualOverrideSummaryDto = Schemas['ManualOverrideSummaryDto'];
export type ManualOverrideReportDto = Schemas['ManualOverrideReportDto'];

// ---- Gate 7: overview KPIs, report exports, audit log, PUSH/EMAIL channels ----
export type TenantOverviewDto = Schemas['TenantOverviewDto'];
export type OverviewFleetSectionDto = Schemas['OverviewFleetSectionDto'];
export type OverviewWorkSectionDto = Schemas['OverviewWorkSectionDto'];
export type OverviewMoneySectionDto = Schemas['OverviewMoneySectionDto'];
export type OverviewCurrencyMoneyDto = Schemas['OverviewCurrencyMoneyDto'];
export type OverviewRiskSectionDto = Schemas['OverviewRiskSectionDto'];
export type OverviewSeverityCountsDto = Schemas['OverviewSeverityCountsDto'];
export type OverviewConnectivityCountsDto = Schemas['OverviewConnectivityCountsDto'];
export type ReportDefinitionDto = Schemas['ReportDefinitionDto'];
export type ReportColumnDto = Schemas['ReportColumnDto'];
export type AuditEventDto = Schemas['AuditEventDto'];
export type NotificationChannel = Schemas['Channel'];
export type NotificationCategory = Schemas['Category'];
export type NotificationRoutingDto = Schemas['NotificationRoutingDto'];
export type NotificationRoutingIn = Schemas['NotificationRoutingIn'];
export type NotificationRoutingChangeIn = Schemas['NotificationRoutingChangeIn'];
export type PushDeviceDto = Schemas['PushDeviceDto'];
export type DevicePlatform = Schemas['DevicePlatform'];
export type DeviceApp = Schemas['DeviceApp'];
export type DeviceDeactivation = Schemas['DeviceDeactivation'];
export type ChannelDeliveryStatus = Schemas['ChannelDeliveryStatus'];
export type NotificationChannelDeliveryDto = Schemas['NotificationChannelDeliveryDto'];
