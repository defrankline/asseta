package com.asseta.core.model.owner

import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * `GET /api/v1/tenant/overview` (getTenantOverview). Each section is null when the caller lacks the permission that
 * gates it; `latest_source_at` is the newest underlying record of that section (freshness of the source data, not of
 * the response).
 */
@Serializable
data class TenantOverviewDto(
    @SerialName("tenant_id") val tenantId: SerializableUuid,
    @SerialName("as_of") val asOf: String,
    val timezone: String,
    val fleet: OverviewFleetSectionDto? = null,
    val work: OverviewWorkSectionDto? = null,
    val money: OverviewMoneySectionDto? = null,
    val risk: OverviewRiskSectionDto? = null,
)

@Serializable
data class OverviewFleetSectionDto(
    val machines: Int,
    val connectivity: OverviewConnectivityCountsDto,
    @SerialName("engine_on_verified") val engineOnVerified: Int,
    @SerialName("open_alerts") val openAlerts: OverviewSeverityCountsDto,
    @SerialName("reported_work_state") val reportedWorkState: Map<String, Int> = emptyMap(),
    @SerialName("latest_source_at") val latestSourceAt: String? = null,
)

@Serializable
data class OverviewConnectivityCountsDto(
    val live: Int = 0,
    val recent: Int = 0,
    val stale: Int = 0,
    val offline: Int = 0,
    val never: Int = 0,
    @SerialName("no_tracker") val noTracker: Int = 0,
)

@Serializable
data class OverviewSeverityCountsDto(val info: Int = 0, val warning: Int = 0, val critical: Int = 0) {
    val total: Int get() = info + warning + critical
}

@Serializable
data class OverviewWorkSectionDto(
    @SerialName("jobs_by_status") val jobsByStatus: Map<String, Int> = emptyMap(),
    @SerialName("open_exceptions") val openExceptions: Int? = null,
    @SerialName("pending_approvals") val pendingApprovals: Int? = null,
    @SerialName("readings_needing_review") val readingsNeedingReview: Int? = null,
    @SerialName("latest_source_at") val latestSourceAt: String? = null,
)

@Serializable
data class OverviewMoneySectionDto(
    @SerialName("month_start") val monthStart: String,
    val currencies: List<OverviewCurrencyMoneyDto> = emptyList(),
    @SerialName("latest_source_at") val latestSourceAt: String? = null,
)

/** All amounts are exact decimal strings in [currency] (never floats). */
@Serializable
data class OverviewCurrencyMoneyDto(
    val currency: String,
    @SerialName("receivables_outstanding") val receivablesOutstanding: DecimalAmount,
    @SerialName("receivables_overdue") val receivablesOverdue: DecimalAmount,
    @SerialName("overdue_invoices") val overdueInvoices: Int,
    @SerialName("verified_receipts_mtd") val verifiedReceiptsMtd: DecimalAmount,
    @SerialName("approved_expenses_mtd") val approvedExpensesMtd: DecimalAmount,
    @SerialName("cash_with_supervisors") val cashWithSupervisors: DecimalAmount,
)

@Serializable
data class OverviewRiskSectionDto(
    @SerialName("open_cases") val openCases: OverviewSeverityCountsDto? = null,
    @SerialName("signals_last_7_days") val signalsLast7Days: OverviewSeverityCountsDto? = null,
    @SerialName("latest_source_at") val latestSourceAt: String? = null,
)

/** Standard list envelope `{"items","total","page","page_size"}`. */
@Serializable
data class PageDto<T>(
    val items: List<T>,
    val total: Int,
    val page: Int,
    @SerialName("page_size") val pageSize: Int,
)

/** `PhotoUrlDto`: short-lived presigned URL for evidence, requested on demand and never cached. */
@Serializable
data class PhotoUrlDto(val url: String, @SerialName("expires_in_seconds") val expiresInSeconds: Int)
