package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// DEC-032 Phase 1: the work allocation ledger and daily operational reports, read online by both apps.

/** `EngineHourReasonDto`: a tenant reason (kinds NON_CUSTOMER_CATEGORY, VARIANCE_REASON, UNBILLABLE_REASON). */
@Serializable
data class EngineHourReasonDto(
    val id: String,
    val kind: String,
    val code: String,
    val name: String,
    val description: String? = null,
    @SerialName("is_active") val isActive: Boolean,
    val version: Int,
) {
    companion object {
        const val UNBILLABLE_REASON = "UNBILLABLE_REASON"
    }
}

/** `UnbillableLineDto`: unbillable hours of a report by reason. */
@Serializable
data class UnbillableLineDto(
    @SerialName("reason_id") val reasonId: String,
    @SerialName("reason_name") val reasonName: String? = null,
    val hours: String,
)

/** `ReportAllocationDto`: one allocation as a daily report recorded it. */
@Serializable
data class ReportAllocationDto(
    @SerialName("allocation_id") val allocationId: String,
    val kind: String,
    @SerialName("customer_id") val customerId: String? = null,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("activity_type") val activityType: String? = null,
    @SerialName("start_reading") val startReading: String,
    @SerialName("end_reading") val endReading: String,
    val hours: String,
)

/** `DailyReportDto`: one machine on one tenant-local day; SUBMITTED, then REVIEWED / RETURNED / SUPERSEDED. */
@Serializable
data class DailyReportDto(
    val id: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("report_date") val reportDate: String,
    @SerialName("opening_ref") val openingRef: String,
    @SerialName("opening_reading") val openingReading: String,
    @SerialName("closing_ref") val closingRef: String,
    @SerialName("closing_reading") val closingReading: String,
    @SerialName("total_hours") val totalHours: String,
    @SerialName("billable_hours") val billableHours: String,
    @SerialName("unbillable_hours") val unbillableHours: String,
    @SerialName("difference_hours") val differenceHours: String,
    val unbillable: List<UnbillableLineDto> = emptyList(),
    val allocations: List<ReportAllocationDto> = emptyList(),
    @SerialName("evidence_attachment_ids") val evidenceAttachmentIds: List<String> = emptyList(),
    val note: String? = null,
    val status: String,
    @SerialName("supersedes_id") val supersedesId: String? = null,
    @SerialName("is_duplicate") val isDuplicate: Boolean = false,
    @SerialName("duplicate_of_id") val duplicateOfId: String? = null,
    @SerialName("is_late") val isLate: Boolean = false,
    @SerialName("submitted_by") val submittedBy: String? = null,
    @SerialName("submitted_by_name") val submittedByName: String? = null,
    @SerialName("submitted_at") val submittedAt: String,
    @SerialName("client_created_at") val clientCreatedAt: String,
    @SerialName("reviewed_by") val reviewedBy: String? = null,
    @SerialName("reviewed_by_name") val reviewedByName: String? = null,
    @SerialName("reviewed_at") val reviewedAt: String? = null,
    @SerialName("review_note") val reviewNote: String? = null,
    val source: String = "",
    @SerialName("policy_version") val policyVersion: String = "",
) {
    companion object {
        const val SUBMITTED = "SUBMITTED"
        const val REVIEWED = "REVIEWED"
        const val RETURNED = "RETURNED"
        const val SUPERSEDED = "SUPERSEDED"
    }
}

/** `DailyReportPrefillDto`: what the server knows of a machine-day before a report is written. */
@Serializable
data class DailyReportPrefillDto(
    @SerialName("machine_id") val machineId: String,
    @SerialName("report_date") val reportDate: String,
    @SerialName("opening_ref") val openingRef: String? = null,
    @SerialName("opening_reading") val openingReading: String? = null,
    @SerialName("opening_at") val openingAt: String? = null,
    @SerialName("closing_ref") val closingRef: String? = null,
    @SerialName("closing_reading") val closingReading: String? = null,
    @SerialName("closing_at") val closingAt: String? = null,
    @SerialName("total_hours") val totalHours: String? = null,
    @SerialName("existing_report_ids") val existingReportIds: List<String> = emptyList(),
)

/** `DailyReportReviewIn` (tenant.meter.review; never the submitter). */
@Serializable
data class DailyReportReviewIn(val decision: String, val note: String) {
    companion object {
        const val REVIEWED = "REVIEWED"
        const val RETURNED = "RETURNED"
    }
}

/** `AllocationLotDto`: the prepaid purchase a stretch of customer work drew its hours from. */
@Serializable
data class AllocationLotDto(
    @SerialName("purchase_id") val purchaseId: String,
    @SerialName("purchase_number") val purchaseNumber: String? = null,
    val hours: String,
)

/** `WorkAllocationDto`: one contiguous stretch of engine hours (CUSTOMER_WORK, AUTHORIZED_ACTIVITY or UNEXPLAINED). */
@Serializable
data class WorkAllocationDto(
    val id: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("work_date") val workDate: String,
    @SerialName("start_reading") val startReading: String,
    @SerialName("start_at") val startAt: String,
    @SerialName("end_reading") val endReading: String,
    @SerialName("end_at") val endAt: String,
    val hours: String,
    val kind: String,
    @SerialName("customer_id") val customerId: String? = null,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("activity_type") val activityType: String? = null,
    @SerialName("reason_id") val reasonId: String? = null,
    @SerialName("reason_name") val reasonName: String? = null,
    val lots: List<AllocationLotDto> = emptyList(),
    @SerialName("evidence_attachment_ids") val evidenceAttachmentIds: List<String> = emptyList(),
    val status: String,
    @SerialName("supersedes_id") val supersedesId: String? = null,
    @SerialName("correction_group_id") val correctionGroupId: String? = null,
    @SerialName("correction_reason") val correctionReason: String? = null,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("recorded_by_name") val recordedByName: String? = null,
    @SerialName("decided_by") val decidedBy: String? = null,
    @SerialName("decided_by_name") val decidedByName: String? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
    @SerialName("created_at") val createdAt: String,
) {
    companion object {
        const val CUSTOMER_WORK = "CUSTOMER_WORK"
        const val AUTHORIZED_ACTIVITY = "AUTHORIZED_ACTIVITY"
        const val UNEXPLAINED = "UNEXPLAINED"
        const val PROPOSED = "PROPOSED"
        const val ACTIVE = "ACTIVE"
    }
}

/** `AllocationCorrectionDto`: the parts proposed to replace one allocation, decided together by a second person. */
@Serializable
data class AllocationCorrectionDto(
    @SerialName("group_id") val groupId: String,
    val status: String,
    @SerialName("supersedes_id") val supersedesId: String? = null,
    val entries: List<WorkAllocationDto> = emptyList(),
)

/** `AllocationDayDto`: one machine-day of the ledger, reconciled against the engine hours. */
@Serializable
data class AllocationDayDto(
    @SerialName("machine_id") val machineId: String,
    val day: String,
    @SerialName("total_engine_hours") val totalEngineHours: String,
    @SerialName("customer_hours") val customerHours: String,
    @SerialName("authorized_hours") val authorizedHours: String,
    @SerialName("unexplained_hours") val unexplainedHours: String,
    @SerialName("allocated_hours") val allocatedHours: String,
    @SerialName("difference_hours") val differenceHours: String,
    val reconciled: Boolean,
)
