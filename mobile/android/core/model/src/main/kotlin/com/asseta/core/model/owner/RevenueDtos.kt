package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// DEC-031 Phase 1 (revenue reconciliation): read online by the Owner and Supervisor apps; no sync operations.

/** `RevenueAdjustmentDto`: an append-only change of an explained / confirmed difference after a later approval. */
@Serializable
data class RevenueAdjustmentDto(
    val id: String,
    @SerialName("previous_difference") val previousDifference: String,
    @SerialName("new_difference") val newDifference: String,
    val amount: String,
    @SerialName("cause_type") val causeType: String,
    @SerialName("cause_id") val causeId: String,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    @SerialName("created_at") val createdAt: String,
)

/** `RevenueDifferenceDto`: expected revenue of one machine-period (one currency) not matched by money. */
@Serializable
data class RevenueDifferenceDto(
    val id: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("period_kind") val periodKind: String,
    @SerialName("period_key") val periodKey: String,
    @SerialName("period_start") val periodStart: String,
    @SerialName("period_end") val periodEnd: String,
    @SerialName("local_from") val localFrom: String,
    @SerialName("local_to") val localTo: String,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
    val currency: String,
    @SerialName("expected_amount") val expectedAmount: String,
    @SerialName("in_progress_amount") val inProgressAmount: String,
    @SerialName("attributed_amount") val attributedAmount: String,
    val difference: String,
    @SerialName("adjusted_difference") val adjustedDifference: String? = null,
    @SerialName("customer_work_hours") val customerWorkHours: String,
    @SerialName("non_revenue_hours") val nonRevenueHours: String,
    @SerialName("unexplained_hours") val unexplainedHours: String,
    @SerialName("unexplained_expected_amount") val unexplainedExpectedAmount: String,
    /** `{"jobs":[{job_id, job_number, currency, expected, in_progress, attributed, completed}], "money_sources":[...], "unexplained":{...}}`. */
    val detail: JsonObject = JsonObject(emptyMap()),
    val status: String,
    @SerialName("case_id") val caseId: String? = null,
    @SerialName("case_number") val caseNumber: String? = null,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("opened_at") val openedAt: String,
    @SerialName("computed_at") val computedAt: String,
    @SerialName("reason_id") val reasonId: String? = null,
    @SerialName("reason_name") val reasonName: String? = null,
    @SerialName("explanation_note") val explanationNote: String? = null,
    @SerialName("explained_by") val explainedBy: String? = null,
    @SerialName("explained_by_name") val explainedByName: String? = null,
    @SerialName("explained_at") val explainedAt: String? = null,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    val adjustments: List<RevenueAdjustmentDto> = emptyList(),
) {
    companion object {
        const val OPEN = "OPEN"
        const val EXPLANATION_PROPOSED = "EXPLANATION_PROPOSED"
        const val EXPLAINED = "EXPLAINED"
        const val CONFIRMED = "CONFIRMED"
        const val CLEARED = "CLEARED"
    }
}

/** `RevenueExplanationIn` (tenant.revenue.explain). */
@Serializable
data class RevenueExplanationIn(@SerialName("reason_id") val reasonId: String, val note: String)

/** `RevenueDecisionIn` (tenant.revenue.decide): APPROVE / REJECT the explanation or CONFIRM the difference. */
@Serializable
data class RevenueDecisionIn(val decision: String, val note: String) {
    companion object {
        const val APPROVE = "APPROVE"
        const val REJECT = "REJECT"
        const val CONFIRM = "CONFIRM"
    }
}

/** `RevenueReasonDto` (the tenant's revenue reason list). */
@Serializable
data class RevenueReasonDto(
    val id: String,
    val code: String,
    val name: String,
    val description: String? = null,
    @SerialName("is_active") val isActive: Boolean,
    val version: Int,
    @SerialName("deactivated_at") val deactivatedAt: String? = null,
    @SerialName("deactivation_reason") val deactivationReason: String? = null,
)

/** `NonRevenueActivityDto`: an ended, non-billable work-log entry of a declared non-revenue type, with its status. */
@Serializable
data class NonRevenueActivityDto(
    @SerialName("activity_id") val activityId: String,
    @SerialName("job_id") val jobId: String,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("activity_type") val activityType: String,
    @SerialName("started_at") val startedAt: String,
    @SerialName("ended_at") val endedAt: String,
    val hours: String,
    val note: String? = null,
    @SerialName("approval_id") val approvalId: String? = null,
    /** NONE | PROPOSED | APPROVED | REJECTED. */
    @SerialName("approval_status") val approvalStatus: String,
)

/** `NonRevenueApprovalDto`: one explanation of non-revenue time, waiting for (or past) a second person's decision. */
@Serializable
data class NonRevenueApprovalDto(
    val id: String,
    @SerialName("activity_id") val activityId: String,
    @SerialName("job_id") val jobId: String,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("activity_type") val activityType: String,
    @SerialName("started_at") val startedAt: String,
    @SerialName("ended_at") val endedAt: String,
    val hours: String,
    @SerialName("reason_id") val reasonId: String,
    @SerialName("reason_name") val reasonName: String? = null,
    val note: String,
    val status: String,
    @SerialName("proposed_by") val proposedBy: String? = null,
    @SerialName("proposed_by_name") val proposedByName: String? = null,
    @SerialName("proposed_at") val proposedAt: String,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    @SerialName("policy_version") val policyVersion: String,
)

/** `NonRevenueApprovalIn` (tenant.revenue.explain). */
@Serializable
data class NonRevenueApprovalIn(@SerialName("activity_id") val activityId: String, @SerialName("reason_id") val reasonId: String, val note: String)

/** `NonRevenueDecisionIn` (tenant.revenue.decide): APPROVE / REJECT. */
@Serializable
data class NonRevenueDecisionIn(val decision: String, val note: String)

/** `SheetJobDto`. */
@Serializable
data class SheetJobDto(
    @SerialName("job_id") val jobId: String,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("billing_mode") val billingMode: String,
    val status: String,
    @SerialName("customer_id") val customerId: String? = null,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("job_site_id") val jobSiteId: String? = null,
    @SerialName("job_site_name") val jobSiteName: String? = null,
    @SerialName("customer_work_hours") val customerWorkHours: String,
    @SerialName("revenue_hours") val revenueHours: String,
)

/** `SheetMoneyDto`: one currency of a machine-day. */
@Serializable
data class SheetMoneyDto(
    val currency: String,
    val expected: String,
    @SerialName("in_progress") val inProgress: String,
    val attributed: String,
    val difference: String,
    @SerialName("unexplained_hours") val unexplainedHours: String = "0",
    @SerialName("unexplained_expected") val unexplainedExpected: String = "0",
)

/** `SheetReadingDto`. */
@Serializable
data class SheetReadingDto(
    val id: String,
    val kind: String,
    @SerialName("captured_at") val capturedAt: String,
    val reading: String,
    val state: String,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
)

/** `SheetSegmentDto`: one reading-to-reading interval overlapping the day. */
@Serializable
data class SheetSegmentDto(
    @SerialName("start_ref") val startRef: String,
    @SerialName("end_ref") val endRef: String,
    @SerialName("start_at") val startAt: String,
    @SerialName("end_at") val endAt: String,
    val kind: String,
    val classification: String,
    val review: String,
    @SerialName("hours_in_day") val hoursInDay: String,
    @SerialName("customer_work_hours_in_day") val customerWorkHoursInDay: String,
    @SerialName("non_revenue_by_type") val nonRevenueByType: Map<String, String> = emptyMap(),
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
)

/** `SheetMoneySourceDto`: an invoice line or prepaid consumption attributed to the day. */
@Serializable
data class SheetMoneySourceDto(
    val source: String,
    @SerialName("ref_id") val refId: String,
    @SerialName("parent_id") val parentId: String,
    @SerialName("job_id") val jobId: String,
    @SerialName("job_number") val jobNumber: String? = null,
    val currency: String,
    val amount: String,
    val hours: String? = null,
)

/** `SheetFlagRefDto`: the record behind a flag. */
@Serializable
data class SheetFlagRefDto(
    val flag: String,
    @SerialName("record_type") val recordType: String,
    @SerialName("record_id") val recordId: String,
)

/** `SheetFuelDto`. */
@Serializable
data class SheetFuelDto(
    val id: String,
    @SerialName("event_type") val eventType: String,
    val litres: String,
    @SerialName("occurred_at") val occurredAt: String,
    @SerialName("job_id") val jobId: String? = null,
)

/** `DailyMachineSheetRowDto`: one machine on one tenant-local day. */
@Serializable
data class DailyMachineSheetRowDto(
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    val day: String,
    @SerialName("first_reading") val firstReading: String? = null,
    @SerialName("last_reading") val lastReading: String? = null,
    @SerialName("reading_count") val readingCount: Int,
    @SerialName("engine_hours") val engineHours: String,
    @SerialName("customer_work_hours") val customerWorkHours: String,
    @SerialName("non_revenue_hours") val nonRevenueHours: String,
    @SerialName("non_revenue_by_type") val nonRevenueByType: Map<String, String> = emptyMap(),
    @SerialName("non_revenue_pending_hours") val nonRevenuePendingHours: String = "0",
    @SerialName("revenue_hours") val revenueHours: String,
    @SerialName("approved_non_customer_hours") val approvedNonCustomerHours: String,
    @SerialName("identified_variance_hours") val identifiedVarianceHours: String,
    @SerialName("unexplained_hours") val unexplainedHours: String,
    @SerialName("pending_review_hours") val pendingReviewHours: String,
    @SerialName("fuel_litres") val fuelLitres: String,
    val jobs: List<SheetJobDto> = emptyList(),
    val money: List<SheetMoneyDto> = emptyList(),
    val flags: List<String> = emptyList(),
)

/** `DailyMachineSheetDetailDto`: the row plus readings, intervals, money sources, flag records and fuel. */
@Serializable
data class DailyMachineSheetDetailDto(
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    val day: String,
    @SerialName("first_reading") val firstReading: String? = null,
    @SerialName("last_reading") val lastReading: String? = null,
    @SerialName("reading_count") val readingCount: Int,
    @SerialName("engine_hours") val engineHours: String,
    @SerialName("customer_work_hours") val customerWorkHours: String,
    @SerialName("non_revenue_hours") val nonRevenueHours: String,
    @SerialName("non_revenue_by_type") val nonRevenueByType: Map<String, String> = emptyMap(),
    @SerialName("non_revenue_pending_hours") val nonRevenuePendingHours: String = "0",
    @SerialName("revenue_hours") val revenueHours: String,
    @SerialName("approved_non_customer_hours") val approvedNonCustomerHours: String,
    @SerialName("identified_variance_hours") val identifiedVarianceHours: String,
    @SerialName("unexplained_hours") val unexplainedHours: String,
    @SerialName("pending_review_hours") val pendingReviewHours: String,
    @SerialName("fuel_litres") val fuelLitres: String,
    val jobs: List<SheetJobDto> = emptyList(),
    val money: List<SheetMoneyDto> = emptyList(),
    val flags: List<String> = emptyList(),
    val readings: List<SheetReadingDto> = emptyList(),
    val segments: List<SheetSegmentDto> = emptyList(),
    @SerialName("money_sources") val moneySources: List<SheetMoneySourceDto> = emptyList(),
    @SerialName("flag_records") val flagRecords: List<SheetFlagRefDto> = emptyList(),
    @SerialName("fuel_events") val fuelEvents: List<SheetFuelDto> = emptyList(),
)
