package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// DEC-032 Phase 4 (contracts/openapi.json): the management view sections, one employee's records, transaction lookup.
// A `route` is a web console route; the app opens its own screen when it has one (ManagementLinks), else the web.

@Serializable
data class PeriodDto(@SerialName("date_from") val dateFrom: String? = null, @SerialName("date_to") val dateTo: String? = null)

@Serializable
data class HoursFigureDto(val hours: String, val count: Int, val route: String)

@Serializable
data class MoneyLineDto(val currency: String, val count: Int, val amount: String)

@Serializable
data class MoneyFigureDto(val lines: List<MoneyLineDto> = emptyList(), val count: Int, val route: String)

@Serializable
data class CountFigureDto(val count: Int, val route: String)

@Serializable
data class PurchaseQueueItemDto(
    @SerialName("purchase_id") val purchaseId: String,
    @SerialName("purchase_number") val purchaseNumber: String? = null,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("hours_awaiting") val hoursAwaiting: String,
    @SerialName("amount_open") val amountOpen: String,
    val currency: String,
    @SerialName("created_at") val createdAt: String,
    val route: String,
)

@Serializable
data class PurchaseQueueDto(
    val count: Int,
    val hours: String,
    val amounts: List<MoneyLineDto> = emptyList(),
    val items: List<PurchaseQueueItemDto> = emptyList(),
    val route: String,
)

@Serializable
data class CustomerRemainingDto(
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    val activated: String,
    val consumed: String,
    val remaining: String,
    val route: String,
)

@Serializable
data class CustomerHoursSectionDto(
    val purchased: HoursFigureDto,
    @SerialName("purchased_value") val purchasedValue: MoneyFigureDto,
    val activated: HoursFigureDto,
    val consumed: HoursFigureDto,
    val remaining: HoursFigureDto,
    @SerialName("remaining_by_customer") val remainingByCustomer: List<CustomerRemainingDto> = emptyList(),
    @SerialName("remaining_customers_total") val remainingCustomersTotal: Int,
    @SerialName("unpaid_purchases") val unpaidPurchases: PurchaseQueueDto,
    @SerialName("unconfirmed_purchases") val unconfirmedPurchases: PurchaseQueueDto,
    @SerialName("awaiting_activation") val awaitingActivation: PurchaseQueueDto,
)

@Serializable
data class ExcavatorHoursDto(
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("operating_hours") val operatingHours: String,
    @SerialName("customer_hours") val customerHours: String,
    @SerialName("authorized_hours") val authorizedHours: String,
    @SerialName("unexplained_hours") val unexplainedHours: String,
    val route: String,
)

@Serializable
data class TypeCountDto(val type: String, val count: Int, val route: String)

@Serializable
data class DiscrepanciesFigureDto(val count: Int, @SerialName("by_type") val byType: List<TypeCountDto> = emptyList(), val route: String)

@Serializable
data class ExcavatorOperationsSectionDto(
    @SerialName("operating_hours") val operatingHours: HoursFigureDto,
    @SerialName("customer_hours") val customerHours: HoursFigureDto,
    @SerialName("authorized_non_customer_hours") val authorizedNonCustomerHours: HoursFigureDto,
    @SerialName("unexplained_hours") val unexplainedHours: HoursFigureDto,
    @SerialName("by_excavator") val byExcavator: List<ExcavatorHoursDto> = emptyList(),
    @SerialName("meter_discrepancies") val meterDiscrepancies: DiscrepanciesFigureDto,
    @SerialName("pending_reports") val pendingReports: CountFigureDto,
    @SerialName("returned_reports") val returnedReports: CountFigureDto,
)

@Serializable
data class EmployeeCashDto(
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    val currency: String,
    val outstanding: String,
    @SerialName("in_transit_out") val inTransitOut: String,
    @SerialName("claimed_unverified_handovers") val claimedUnverifiedHandovers: String,
    @SerialName("pending_floats") val pendingFloats: String,
    @SerialName("approved_retention") val approvedRetention: String,
    val route: String,
)

@Serializable
data class CashSectionDto(
    val collected: MoneyFigureDto,
    @SerialName("held_by_employee") val heldByEmployee: List<EmployeeCashDto> = emptyList(),
    val transferred: MoneyFigureDto,
    @SerialName("in_transit") val inTransit: MoneyFigureDto,
    @SerialName("declared_for_remittance") val declaredForRemittance: MoneyFigureDto,
    @SerialName("confirmed_by_company") val confirmedByCompany: MoneyFigureDto,
    val outstanding: MoneyFigureDto,
    @SerialName("unconfirmed_remittances") val unconfirmedRemittances: MoneyFigureDto,
    @SerialName("disputed_remittances") val disputedRemittances: MoneyFigureDto,
    @SerialName("disputed_transfers") val disputedTransfers: MoneyFigureDto,
)

@Serializable
data class KindCountDto(val kind: String, val count: Int, @SerialName("oldest_at") val oldestAt: String?, val route: String)

@Serializable
data class OutstandingApprovalsDto(val total: Int, @SerialName("by_kind") val byKind: List<KindCountDto> = emptyList())

@Serializable
data class PendingItemDto(
    val kind: String,
    @SerialName("record_type") val recordType: String,
    val id: String,
    val reference: String?,
    val status: String,
    @SerialName("requested_by") val requestedBy: String?,
    @SerialName("requested_by_name") val requestedByName: String? = null,
    @SerialName("requested_at") val requestedAt: String,
    val amount: String?,
    val unit: String?,
    val currency: String?,
    @SerialName("customer_id") val customerId: String?,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("machine_id") val machineId: String?,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("staff_member_id") val staffMemberId: String?,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    val route: String?,
)

@Serializable
data class PendingAdjustmentsDto(
    val total: Int,
    @SerialName("by_kind") val byKind: List<KindCountDto> = emptyList(),
    val oldest: List<PendingItemDto> = emptyList(),
    val route: String,
)

@Serializable
data class AttemptsFigureDto(
    @SerialName("permission_denied") val permissionDenied: Int,
    @SerialName("segregation_of_duties") val segregationOfDuties: Int,
    val since: String,
    val route: String,
)

@Serializable
data class OverdueReportsDto(
    val total: Int,
    @SerialName("missing_daily_reports") val missingDailyReports: CountFigureDto,
    @SerialName("remittances_overdue_today") val remittancesOverdueToday: CountFigureDto,
)

@Serializable
data class VarianceSourceDto(val source: String, val unit: String, val count: Int, val amounts: List<MoneyLineDto> = emptyList(), val route: String)

@Serializable
data class UnresolvedVariancesDto(val total: Int, @SerialName("by_source") val bySource: List<VarianceSourceDto> = emptyList())

@Serializable
data class ChangeoverJobDto(
    @SerialName("job_id") val jobId: String,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("changed_over_at") val changedOverAt: String,
    @SerialName("days_waiting") val daysWaiting: Int,
    val route: String,
)

@Serializable
data class ChangeoverJobsDto(val count: Int, @SerialName("oldest_days") val oldestDays: Int?, val items: List<ChangeoverJobDto> = emptyList())

@Serializable
data class ExceptionsSectionDto(
    @SerialName("unexplained_engine_hours") val unexplainedEngineHours: HoursFigureDto,
    val shortages: MoneyFigureDto,
    val overages: MoneyFigureDto,
    @SerialName("shortages_opened_in_period") val shortagesOpenedInPeriod: MoneyFigureDto,
    @SerialName("overages_opened_in_period") val overagesOpenedInPeriod: MoneyFigureDto,
    @SerialName("pending_adjustments") val pendingAdjustments: PendingAdjustmentsDto,
    @SerialName("unauthorized_attempts") val unauthorizedAttempts: AttemptsFigureDto,
    @SerialName("unconfirmed_payments") val unconfirmedPayments: MoneyFigureDto,
    @SerialName("outstanding_approvals") val outstandingApprovals: OutstandingApprovalsDto,
    @SerialName("overdue_reports") val overdueReports: OverdueReportsDto,
    @SerialName("unresolved_variances") val unresolvedVariances: UnresolvedVariancesDto,
    @SerialName("changeover_jobs_awaiting_approval") val changeoverJobsAwaitingApproval: ChangeoverJobsDto,
)

// --- one employee ------------------------------------------------------------------------------------------------

@Serializable
data class EmployeeIdentityDto(
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("full_name") val fullName: String,
    @SerialName("employee_code") val employeeCode: String?,
    val kind: String,
    @SerialName("is_active") val isActive: Boolean,
    val phone: String?,
    @SerialName("login_email") val loginEmail: String?,
    @SerialName("user_id") val userId: String?,
    val roles: List<String> = emptyList(),
)

@Serializable
data class EmployeeRecordDto(
    @SerialName("record_type") val recordType: String,
    val id: String?,
    val reference: String? = null,
    val status: String? = null,
    @SerialName("occurred_at") val occurredAt: String,
    val amount: String? = null,
    val unit: String? = null,
    val currency: String? = null,
    val label: String? = null,
    @SerialName("counterparty_staff_id") val counterpartyStaffId: String? = null,
    @SerialName("counterparty_staff_name") val counterpartyStaffName: String? = null,
    val route: String? = null,
)

/** Subset of `CashCustodyBalanceDto` the employee screen shows. */
@Serializable
data class EmployeeCashHeldDto(
    val currency: String,
    val outstanding: String,
    @SerialName("in_transit_out") val inTransitOut: String = "0",
    @SerialName("pending_floats") val pendingFloats: String = "0",
    @SerialName("claimed_unverified_handovers") val claimedUnverifiedHandovers: String,
    @SerialName("approved_retention") val approvedRetention: String = "0",
)

@Serializable
data class EmployeeAccountabilityDto(
    val identity: EmployeeIdentityDto,
    @SerialName("date_from") val dateFrom: String,
    @SerialName("date_to") val dateTo: String,
    @SerialName("cash_held") val cashHeld: List<EmployeeCashHeldDto> = emptyList(),
    val collections: List<EmployeeRecordDto> = emptyList(),
    val floats: List<EmployeeRecordDto> = emptyList(),
    @SerialName("transfers_in") val transfersIn: List<EmployeeRecordDto> = emptyList(),
    @SerialName("transfers_out") val transfersOut: List<EmployeeRecordDto> = emptyList(),
    val remittances: List<EmployeeRecordDto> = emptyList(),
    val spending: List<EmployeeRecordDto> = emptyList(),
    val retentions: List<EmployeeRecordDto> = emptyList(),
    val differences: List<EmployeeRecordDto> = emptyList(),
    @SerialName("custody_adjustments") val custodyAdjustments: List<EmployeeRecordDto> = emptyList(),
    @SerialName("reports_submitted") val reportsSubmitted: List<EmployeeRecordDto> = emptyList(),
    @SerialName("approvals_made") val approvalsMade: List<EmployeeRecordDto> = emptyList(),
    @SerialName("adjustments_requested") val adjustmentsRequested: List<EmployeeRecordDto> = emptyList(),
    @SerialName("adjustments_decided") val adjustmentsDecided: List<EmployeeRecordDto> = emptyList(),
    @SerialName("scorecard_items") val scorecardItems: List<EmployeeRecordDto> = emptyList(),
    @SerialName("scorecard_visible") val scorecardVisible: Boolean,
    val truncated: List<String> = emptyList(),
)

// --- lookup --------------------------------------------------------------------------------------------------------

@Serializable
data class LookupMatchDto(
    @SerialName("record_type") val recordType: String,
    val id: String,
    val reference: String?,
    val route: String?,
    val status: String?,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("recorded_by_name") val recordedByName: String? = null,
    @SerialName("recorded_at") val recordedAt: String? = null,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("customer_id") val customerId: String? = null,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("machine_id") val machineId: String? = null,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("staff_member_id") val staffMemberId: String? = null,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    val amount: String? = null,
    val currency: String? = null,
    @SerialName("balance_outstanding") val balanceOutstanding: String? = null,
    @SerialName("balance_unit") val balanceUnit: String? = null,
    @SerialName("hours_remaining") val hoursRemaining: String? = null,
)

@Serializable
data class LookupResultDto(val reference: String, val matches: List<LookupMatchDto> = emptyList())
