package com.asseta.owner.ui.home

import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.OverviewSeverityCountsDto
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.owner.ui.common.freshnessLine
import java.math.BigDecimal

/** Emphasis of a KPI; the UI maps it to a colour (never the only signal: the label says what it is). */
enum class KpiTone { NORMAL, GOOD, WARNING, CRITICAL, MUTED }

data class OverviewRow(
    val label: String,
    val value: String,
    val detail: String? = null,
    val tone: KpiTone = KpiTone.NORMAL,
    val target: OwnerDestination? = null,
)

data class OverviewGroup(val heading: String?, val rows: List<OverviewRow>)

data class OverviewAction(val label: String, val target: OwnerDestination)

data class OverviewSection(
    val title: String,
    val freshness: String,
    val groups: List<OverviewGroup>,
    val actions: List<OverviewAction> = emptyList(),
    val emptyText: String? = null,
)

/**
 * What the Overview shows, as data: sections, labels, values and where a tap leads. The iOS app builds the same list
 * (`OverviewPresentation` in AssetaOwnerKit) so both Owner apps show identical figures and wording.
 */
object OverviewPresentation {
    const val NO_SECTIONS = "Your role has no dashboard sections in this company."
    val JOB_STATUS_ORDER = listOf("IN_PROGRESS", "APPROVED", "PENDING_APPROVAL", "DRAFT", "COMPLETED", "CANCELLED")

    fun asOf(o: TenantOverviewDto): String = "Figures as of ${OwnerFormat.dateTime(o.asOf, OwnerFormat.zone(o.timezone))} (${o.timezone})"

    /** "3 critical · 1 warning · 0 info" under a severity total. */
    fun breakdown(c: OverviewSeverityCountsDto): String = "${c.critical} critical · ${c.warning} warning · ${c.info} info"

    /** [cached]: the overview is an offline snapshot, so "live" counts describe the moment it was saved. */
    fun sections(
        o: TenantOverviewDto,
        cached: Boolean,
        nowMs: Long,
        money: (BigDecimal, String) -> String = { v, c -> OwnerFormat.money(v, c) },
    ): List<OverviewSection> = listOfNotNull(
        o.fleet?.let { f ->
            val c = f.connectivity
            val rows = listOf(
                OverviewRow("Machines", "${f.machines}"),
                OverviewRow(if (cached) "Live when saved" else "Live now", "${c.live}", tone = if (cached) KpiTone.MUTED else KpiTone.GOOD),
                OverviewRow("Recent", "${c.recent}"),
                OverviewRow("Stale", "${c.stale}", tone = if (c.stale > 0) KpiTone.WARNING else KpiTone.NORMAL),
                OverviewRow("Offline", "${c.offline}", tone = if (c.offline > 0) KpiTone.CRITICAL else KpiTone.NORMAL),
                OverviewRow("Never reported", "${c.never}", tone = KpiTone.MUTED),
                OverviewRow("No tracker", "${c.noTracker}", tone = KpiTone.MUTED),
                OverviewRow("Engine on (tracker verified)", "${f.engineOnVerified}"),
            ) + f.reportedWorkState.toSortedMap().map { (k, v) -> OverviewRow("Reported ${OwnerFormat.humanize(k).lowercase()}", "$v") } +
                OverviewRow(
                    "Open alerts", "${f.openAlerts.total}", breakdown(f.openAlerts),
                    if (f.openAlerts.critical > 0) KpiTone.CRITICAL else KpiTone.NORMAL, OwnerDestination.Alerts(),
                )
            OverviewSection("Fleet", freshnessLine(f.latestSourceAt, nowMs), listOf(OverviewGroup(null, rows)), listOf(OverviewAction("Open fleet map", OwnerDestination.Fleet)))
        },
        o.work?.let { w ->
            val statuses = w.jobsByStatus.keys.sortedWith(compareBy({ JOB_STATUS_ORDER.indexOf(it).let { i -> if (i < 0) Int.MAX_VALUE else i } }, { it }))
            val rows = statuses.map { OverviewRow(OwnerFormat.humanize(it), "${w.jobsByStatus.getValue(it)}") } + listOfNotNull(
                w.pendingApprovals?.let {
                    OverviewRow("Pending approvals", "$it", tone = if (it > 0) KpiTone.WARNING else KpiTone.NORMAL, target = OwnerDestination.Approvals())
                },
                w.readingsNeedingReview?.let { OverviewRow("Readings needing review", "$it") },
                w.openExceptions?.let {
                    OverviewRow("Open meter exceptions", "$it", tone = if (it > 0) KpiTone.WARNING else KpiTone.NORMAL, target = OwnerDestination.Exceptions())
                },
            )
            OverviewSection("Jobs and work", freshnessLine(w.latestSourceAt, nowMs), listOf(OverviewGroup(null, rows)), listOf(OverviewAction("Open jobs", OwnerDestination.Jobs)))
        },
        o.money?.let { m ->
            val groups = m.currencies.map { c ->
                OverviewGroup(
                    c.currency,
                    listOf(
                        OverviewRow("Receivables outstanding", money(c.receivablesOutstanding.value, c.currency)),
                        OverviewRow(
                            "Overdue (${c.overdueInvoices} invoices)", money(c.receivablesOverdue.value, c.currency),
                            tone = if (c.overdueInvoices > 0) KpiTone.CRITICAL else KpiTone.NORMAL,
                        ),
                        OverviewRow("Verified receipts this month", money(c.verifiedReceiptsMtd.value, c.currency), tone = KpiTone.GOOD),
                        OverviewRow("Approved expenses this month", money(c.approvedExpensesMtd.value, c.currency)),
                        OverviewRow("Cash with supervisors", money(c.cashWithSupervisors.value, c.currency)),
                    ),
                )
            }
            OverviewSection(
                "Money (month from ${m.monthStart})", freshnessLine(m.latestSourceAt, nowMs), groups,
                emptyText = "No financial activity this month.".takeIf { groups.isEmpty() },
            )
        },
        o.risk?.let { r ->
            val rows = listOfNotNull(
                r.openCases?.let { OverviewRow("Open investigations", "${it.total}", breakdown(it), if (it.critical > 0) KpiTone.CRITICAL else KpiTone.NORMAL) },
                r.signalsLast7Days?.let { OverviewRow("Signals (last 7 days)", "${it.total}", breakdown(it)) },
            )
            OverviewSection("Investigations and signals", freshnessLine(r.latestSourceAt, nowMs), listOf(OverviewGroup(null, rows)), listOf(OverviewAction("Open investigations", OwnerDestination.Cases)))
        },
    )
}
