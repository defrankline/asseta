package com.asseta.core.model.owner

import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/** `AlertDto` (listTrackingAlerts / actOnTrackingAlert). [evidence] is server-defined and shown as key/value pairs. */
@Serializable
data class AlertDto(
    val id: SerializableUuid,
    @SerialName("alert_type") val alertType: String,
    val severity: String,
    val status: String,
    val title: String,
    @SerialName("event_time") val eventTime: String,
    @SerialName("created_at") val createdAt: String,
    val evidence: Map<String, JsonElement> = emptyMap(),
    @SerialName("machine_id") val machineId: SerializableUuid? = null,
    @SerialName("tracker_id") val trackerId: SerializableUuid? = null,
    @SerialName("acknowledged_at") val acknowledgedAt: String? = null,
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("resolution_note") val resolutionNote: String? = null,
    @SerialName("policy_version") val policyVersion: String? = null,
)

/** `AlertActionIn`: [action] is ACKNOWLEDGE or RESOLVE (RESOLVE requires a [note], `422 NOTE_REQUIRED`). */
@Serializable
data class AlertActionIn(val action: String, val note: String? = null) {
    companion object {
        const val ACKNOWLEDGE = "ACKNOWLEDGE"
        const val RESOLVE = "RESOLVE"
    }
}

/** `ApprovalRequestDto` (listApprovalRequests / decideApprovalRequest). */
@Serializable
data class ApprovalRequestDto(
    val id: SerializableUuid,
    @SerialName("subject_type") val subjectType: String,
    @SerialName("subject_id") val subjectId: SerializableUuid,
    val amount: DecimalAmount,
    val currency: String,
    val reason: String,
    val status: String,
    @SerialName("requested_at") val requestedAt: String,
    @SerialName("policy_version") val policyVersion: String,
    @SerialName("requested_by") val requestedBy: SerializableUuid? = null,
    @SerialName("decided_at") val decidedAt: String? = null,
    @SerialName("decided_by") val decidedBy: SerializableUuid? = null,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `ApprovalDecisionIn`. Submitters cannot decide their own expense (`422 SEGREGATION_OF_DUTIES`). */
@Serializable
data class ApprovalDecisionIn(val approve: Boolean, val note: String? = null)

/** `ExpenseDto` subset shown with an expense approval (getExpense) and in the field spend lists (listExpenses). */
@Serializable
data class ExpenseDto(
    val id: SerializableUuid,
    val amount: DecimalAmount,
    val currency: String,
    val description: String,
    val status: String,
    @SerialName("incurred_at") val incurredAt: String,
    @SerialName("submitted_at") val submittedAt: String,
    @SerialName("paid_from") val paidFrom: String,
    val supplier: String? = null,
    @SerialName("receipt_attachment_ids") val receiptAttachmentIds: List<SerializableUuid> = emptyList(),
    @SerialName("machine_id") val machineId: SerializableUuid? = null,
    @SerialName("job_id") val jobId: SerializableUuid? = null,
    @SerialName("custodian_staff_id") val custodianStaffId: SerializableUuid? = null,
    @SerialName("receipt_required") val receiptRequired: Boolean = false,
    @SerialName("decision_note") val decisionNote: String? = null,
)

/** `AnomalyCaseDto` (listAnomalyCases). Investigations are read-only in the Owner app. */
@Serializable
data class AnomalyCaseDto(
    val id: SerializableUuid,
    @SerialName("case_number") val caseNumber: String,
    val title: String,
    val status: String,
    val severity: String,
    @SerialName("subject_type") val subjectType: String,
    @SerialName("subject_id") val subjectId: SerializableUuid,
    @SerialName("opened_at") val openedAt: String,
    @SerialName("last_signal_at") val lastSignalAt: String,
    @SerialName("policy_version") val policyVersion: String,
    val version: Long,
    @SerialName("signal_count") val signalCount: Int? = null,
    @SerialName("machine_id") val machineId: SerializableUuid? = null,
    @SerialName("job_id") val jobId: SerializableUuid? = null,
    @SerialName("staff_member_id") val staffMemberId: SerializableUuid? = null,
    @SerialName("assignee_user_id") val assigneeUserId: SerializableUuid? = null,
    @SerialName("assignee_name") val assigneeName: String? = null,
    @SerialName("latest_outcome") val latestOutcome: String? = null,
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("resolved_by") val resolvedBy: SerializableUuid? = null,
)

/** `AnomalyCaseDetailDto` (getAnomalyCase). */
@Serializable
data class AnomalyCaseDetailDto(
    val case: AnomalyCaseDto,
    val signals: List<CaseSignalDto> = emptyList(),
    val notes: List<CaseNoteDto> = emptyList(),
    val outcomes: List<CaseOutcomeDto> = emptyList(),
)

@Serializable
data class CaseSignalDto(
    val id: SerializableUuid,
    val code: String,
    val severity: String,
    @SerialName("source_type") val sourceType: String,
    @SerialName("source_id") val sourceId: SerializableUuid,
    @SerialName("observed_at") val observedAt: String,
    @SerialName("linked_at") val linkedAt: String,
    val evidence: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class CaseNoteDto(
    val id: SerializableUuid,
    val kind: String,
    val body: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("author_user_id") val authorUserId: SerializableUuid? = null,
    @SerialName("author_name") val authorName: String? = null,
)

@Serializable
data class CaseOutcomeDto(
    val id: SerializableUuid,
    val outcome: String,
    val explanation: String,
    val sequence: Int,
    @SerialName("decided_at") val decidedAt: String,
    @SerialName("decided_by") val decidedBy: SerializableUuid,
    @SerialName("decided_by_name") val decidedByName: String? = null,
)
