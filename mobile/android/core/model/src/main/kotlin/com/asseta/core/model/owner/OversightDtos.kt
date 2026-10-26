package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/*
 * DEC-031 Phase 5 oversight reads (contracts/openapi.json): people scorecard, unbilled work, idle machines and site
 * check-ins. Money, hours and distances from the server stay as sent (decimal strings / numbers); unknown enum values
 * are kept as text.
 */

/** `AmountByCurrencyDto`. */
@Serializable
data class AmountByCurrencyDto(val currency: String, val count: Int, val amount: String)

/** `CashHeldDto`: cash the person holds now, oldest part received at [heldSince]. */
@Serializable
data class CashHeldDto(
    val currency: String,
    val amount: String,
    @SerialName("held_since") val heldSince: String?,
    @SerialName("held_days") val heldDays: Int?,
)

/** `ScorecardRowDto`: one person's counts of items to look at for the period (never a verdict). */
@Serializable
data class ScorecardRowDto(
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    @SerialName("staff_kind") val staffKind: String,
    @SerialName("employee_code") val employeeCode: String?,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("day_from") val dayFrom: String,
    @SerialName("day_to") val dayTo: String,
    val machines: Int,
    @SerialName("daily_reports_missing") val dailyReportsMissing: Int,
    @SerialName("daily_reports_late") val dailyReportsLate: Int,
    @SerialName("unexplained_hours") val unexplainedHours: String,
    @SerialName("unexplained_items") val unexplainedItems: Int,
    val alerts: Int,
    @SerialName("alerts_open") val alertsOpen: Int,
    @SerialName("alerts_acknowledged") val alertsAcknowledged: Int,
    @SerialName("avg_hours_to_acknowledge") val avgHoursToAcknowledge: String?,
    @SerialName("max_hours_to_acknowledge") val maxHoursToAcknowledge: String?,
    @SerialName("cash_held_too_long") val cashHeldTooLong: Int,
    @SerialName("cash_differences") val cashDifferences: Int,
    @SerialName("cash_difference_totals") val cashDifferenceTotals: List<AmountByCurrencyDto>,
    @SerialName("cash_differences_near_threshold") val cashDifferencesNearThreshold: Int,
    @SerialName("revenue_differences") val revenueDifferences: Int,
    @SerialName("revenue_difference_totals") val revenueDifferenceTotals: List<AmountByCurrencyDto>,
    @SerialName("refused_attempts") val refusedAttempts: Int,
    /** Null while site check-ins were never required in the period. */
    @SerialName("checkins_missed") val checkinsMissed: Int?,
    @SerialName("checkins_made") val checkinsMade: Int,
    @SerialName("pattern_signals") val patternSignals: Int,
    @SerialName("items_total") val itemsTotal: Int,
    /** Now (not limited to the period). */
    @SerialName("cash_held") val cashHeld: List<CashHeldDto> = emptyList(),
)

/** `ScorecardRecordDto`: one item behind a figure, with the record to open ([recordType] + [recordId]). */
@Serializable
data class ScorecardRecordDto(
    val item: String,
    @SerialName("record_type") val recordType: String,
    @SerialName("record_id") val recordId: String?,
    val at: String,
    val day: String?,
    @SerialName("machine_id") val machineId: String? = null,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
    val status: String? = null,
    val amount: String? = null,
    val currency: String? = null,
    val hours: String? = null,
    @SerialName("near_threshold") val nearThreshold: Boolean = false,
    val detail: JsonObject = JsonObject(emptyMap()),
)

/** `ScorecardDetailDto` (GET /scorecard/{staff_member_id}). */
@Serializable
data class ScorecardDetailDto(val row: ScorecardRowDto, val records: List<ScorecardRecordDto>)

/** `UnbilledJobDto`: a completed, billing-ready job not on an issued invoice yet. */
@Serializable
data class UnbilledJobDto(
    @SerialName("job_id") val jobId: String,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("customer_id") val customerId: String,
    @SerialName("customer_name") val customerName: String? = null,
    @SerialName("job_site_id") val jobSiteId: String?,
    @SerialName("job_site_name") val jobSiteName: String? = null,
    @SerialName("supervisor_staff_id") val supervisorStaffId: String?,
    @SerialName("supervisor_staff_name") val supervisorStaffName: String? = null,
    @SerialName("completed_at") val completedAt: String,
    @SerialName("days_unbilled") val daysUnbilled: Int,
    @SerialName("billable_hours") val billableHours: String?,
    val currency: String,
    val total: String?,
    @SerialName("draft_invoice_id") val draftInvoiceId: String?,
)

/** `IdleMachineDto`: an active machine with no running job and no engine hours for a while. */
@Serializable
data class IdleMachineDto(
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("category_id") val categoryId: String?,
    @SerialName("idle_since") val idleSince: String,
    @SerialName("idle_days") val idleDays: Int,
    @SerialName("last_job_id") val lastJobId: String?,
    @SerialName("last_job_number") val lastJobNumber: String? = null,
    @SerialName("last_job_completed_at") val lastJobCompletedAt: String?,
    @SerialName("last_engine_activity_at") val lastEngineActivityAt: String?,
    @SerialName("planned_job_id") val plannedJobId: String?,
    @SerialName("planned_job_number") val plannedJobNumber: String? = null,
)

/** `SiteCheckinDto`: one GPS check-in at the site. */
@Serializable
data class SiteCheckinDto(
    val id: String,
    @SerialName("client_id") val clientId: String,
    @SerialName("staff_member_id") val staffMemberId: String,
    @SerialName("staff_member_name") val staffMemberName: String? = null,
    @SerialName("recorded_by") val recordedBy: String,
    @SerialName("recorded_by_name") val recordedByName: String? = null,
    @SerialName("captured_at") val capturedAt: String,
    @SerialName("received_at") val receivedAt: String,
    @SerialName("gps_status") val gpsStatus: String,
    val latitude: Double?,
    val longitude: Double?,
    @SerialName("accuracy_m") val accuracyM: Double?,
    @SerialName("job_site_id") val jobSiteId: String?,
    @SerialName("job_site_name") val jobSiteName: String? = null,
    @SerialName("job_id") val jobId: String?,
    @SerialName("job_number") val jobNumber: String? = null,
    @SerialName("distance_m") val distanceM: Double?,
    @SerialName("within_distance") val withinDistance: Boolean? = null,
    val source: String,
)

/** `CheckinSlotDto`: a scheduled check-in (MADE, MISSED, DUE or UPCOMING). */
@Serializable
data class CheckinSlotDto(
    @SerialName("scheduled_at") val scheduledAt: String,
    @SerialName("window_minutes") val windowMinutes: Int,
    val status: String,
    @SerialName("checkin_id") val checkinId: String? = null,
    @SerialName("job_id") val jobId: String? = null,
    @SerialName("job_number") val jobNumber: String? = null,
)

/** `MySiteCheckinsDto` (GET /site-checkins/mine): the caller's schedule and own check-ins. */
@Serializable
data class MySiteCheckinsDto(
    val required: Boolean,
    val times: List<String>,
    @SerialName("window_minutes") val windowMinutes: Int,
    @SerialName("max_distance_m") val maxDistanceM: Int?,
    val timezone: String,
    @SerialName("day_from") val dayFrom: String,
    @SerialName("day_to") val dayTo: String,
    val slots: List<CheckinSlotDto>,
    val checkins: List<SiteCheckinDto>,
)
