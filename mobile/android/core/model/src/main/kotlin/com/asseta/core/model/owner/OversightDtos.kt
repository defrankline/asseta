package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/*
 * DEC-031 Phase 5 oversight reads (contracts/openapi.json): people scorecard and idle machines. Money, hours and
 * distances from the server stay as sent (decimal strings / numbers); unknown enum values are kept as text.
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
    @SerialName("refused_attempts") val refusedAttempts: Int,
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

/** `IdleMachineDto`: an active machine with no approved machine-report hours for a while. */
@Serializable
data class IdleMachineDto(
    @SerialName("machine_id") val machineId: String,
    @SerialName("machine_code") val machineCode: String? = null,
    @SerialName("machine_name") val machineName: String? = null,
    @SerialName("category_id") val categoryId: String?,
    @SerialName("idle_since") val idleSince: String,
    @SerialName("idle_days") val idleDays: Int,
    @SerialName("last_machine_report_id") val lastMachineReportId: String?,
    @SerialName("last_machine_report_number") val lastMachineReportNumber: String? = null,
    @SerialName("last_engine_activity_at") val lastEngineActivityAt: String?,
)

