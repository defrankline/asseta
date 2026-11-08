package com.asseta.core.model.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** One line of unbillable hours in a daily report (`UnbillableLineIn`); hours are decimal strings, never floats. */
@Serializable
data class UnbillableLinePayload(
    @SerialName("reason_id") val reasonId: String,
    val hours: String,
)

/**
 * `DAILY_REPORT` (`DailyReportIn` without `id`: the operation id is the report id). The photos go by resumable upload
 * (purpose DAILY_REPORT_EVIDENCE); [evidenceUploadIds] is filled in as each one completes, before the operation is sent.
 */
@Serializable
data class DailyReportPayload(
    @SerialName("machine_id") val machineId: String,
    @SerialName("report_date") val reportDate: String,
    @SerialName("opening_ref") val openingRef: String,
    @SerialName("closing_ref") val closingRef: String,
    /** Null: the server takes the total minus the unbillable hours. */
    @SerialName("billable_hours") val billableHours: String? = null,
    val unbillable: List<UnbillableLinePayload> = emptyList(),
    val note: String? = null,
    @SerialName("evidence_upload_ids") val evidenceUploadIds: List<String> = emptyList(),
    @SerialName("supersedes_id") val supersedesId: String? = null,
    @SerialName("client_created_at") val clientCreatedAt: String,
)

/** `SyncChangeoverJobDto`: a job a changeover can move on to, office-created ones included. */
@Serializable
data class SyncChangeoverJobDto(
    val id: String,
    @SerialName("job_number") val jobNumber: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String,
    val status: String,
    @SerialName("sync_revision") val syncRevision: Long,
)

/** `SyncUnbillableReasonDto`: one entry of the tenant's unbillable-reason list. */
@Serializable
data class SyncUnbillableReasonDto(
    val id: String,
    val code: String,
    val name: String,
    val description: String? = null,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("sync_revision") val syncRevision: Long,
)
