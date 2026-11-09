package com.asseta.owner.ui.accountability

import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.ApprovalsTileDto
import com.asseta.core.model.owner.CashSectionDto
import com.asseta.core.model.owner.CustomerHoursSectionDto
import com.asseta.core.model.owner.ExceptionsSectionDto
import com.asseta.core.model.owner.ExcavatorOperationsSectionDto
import com.asseta.core.model.owner.HoursFigureDto
import com.asseta.core.model.owner.KindCountDto
import com.asseta.core.model.owner.MoneyFigureDto
import com.asseta.core.model.owner.MoneyLineDto
import com.asseta.core.model.owner.PurchaseQueueDto
import com.asseta.owner.ui.OwnerFeatures
import java.time.ZoneId

private val T = ManagementTexts

/** One row of a management card: a figure with what it opens, or a sub-heading ([heading] true). */
data class ManagementRow(
    val key: String,
    val label: String,
    val value: String? = null,
    val caption: String? = null,
    val target: FigureTarget? = null,
    val heading: Boolean = false,
)

data class ManagementGroup(val key: String, val title: String, val rows: List<ManagementRow>, val footer: String? = null)

/** Pure presentation of the four guideline groups (unit-tested; same figures and links as iOS). */
class ManagementPresentation(private val f: OwnerFeatures, private val webBase: String, private val zone: ZoneId = ZoneId.systemDefault()) {
    private fun target(route: String?) = ManagementLinks.target(route, f, webBase)

    fun money(amount: String, currency: String): String = amount.toBigDecimalOrNull()?.let { OwnerFormat.money(it, currency) } ?: "$amount $currency"
    private fun lines(list: List<MoneyLineDto>): String = if (list.isEmpty()) T.NONE else list.joinToString(", ") { money(it.amount, it.currency) }
    private fun h(raw: String): String = "${OwnerFormat.hoursNumber(raw)} h"
    private fun nonZero(raw: String, currency: String): String? = raw.toBigDecimalOrNull()?.takeIf { it.signum() != 0 }?.let { OwnerFormat.money(it, currency) }

    private fun hoursRow(key: String, label: String, x: HoursFigureDto) = ManagementRow(key, label, h(x.hours), target = target(x.route))
    private fun moneyRow(key: String, label: String, x: MoneyFigureDto) = ManagementRow(key, label, lines(x.lines), target = target(x.route))
    private fun countRow(key: String, label: String, count: Int, route: String) = ManagementRow(key, label, "$count", target = target(route))
    private fun queueRow(key: String, label: String, q: PurchaseQueueDto) =
        ManagementRow(key, label, "${q.count} · ${h(q.hours)}", caption = lines(q.amounts).takeIf { q.amounts.isNotEmpty() }, target = target(q.route))
    private fun heading(key: String, label: String) = ManagementRow(key, label, heading = true)

    private fun kindRows(prefix: String, kinds: List<KindCountDto>) = kinds.map { k ->
        ManagementRow("$prefix-${k.kind}", T.kind(k.kind), "${k.count}", caption = k.oldestAt?.let { T.oldest(OwnerFormat.date(it, zone)) }, target = target(k.route))
    }

    fun groups(s: AccountabilitySummaryDto): List<ManagementGroup> = listOfNotNull(s.hoursSection?.let(::hours), s.operationsSection?.let(::operations), s.cashSection?.let(::cash), s.exceptionsSection?.let(::exceptions))

    private fun hours(s: CustomerHoursSectionDto): ManagementGroup {
        val rows = buildList {
            add(hoursRow("purchased", T.HOURS_PURCHASED, s.purchased))
            add(moneyRow("purchased_value", T.HOURS_PURCHASED_VALUE, s.purchasedValue))
            add(hoursRow("activated", T.HOURS_ACTIVATED, s.activated))
            add(hoursRow("consumed", T.HOURS_CONSUMED, s.consumed))
            add(hoursRow("remaining", T.HOURS_REMAINING, s.remaining))
            add(queueRow("unpaid", T.HOURS_UNPAID, s.unpaidPurchases))
            add(queueRow("unconfirmed", T.HOURS_UNCONFIRMED, s.unconfirmedPurchases))
            add(queueRow("awaiting", T.HOURS_AWAITING, s.awaitingActivation))
            if (s.remainingByCustomer.isNotEmpty()) {
                add(heading("by_customer", T.HOURS_BY_CUSTOMER))
                s.remainingByCustomer.forEach { c ->
                    add(ManagementRow("customer-${c.customerId}", DisplayNames.or(c.customerName, c.customerId), h(c.remaining), target = target(c.route)))
                }
            }
        }
        val shown = s.remainingByCustomer.size
        return ManagementGroup("hours_section", T.HOURS_TITLE, rows, T.customersShown(shown, s.remainingCustomersTotal).takeIf { shown < s.remainingCustomersTotal })
    }

    private fun operations(s: ExcavatorOperationsSectionDto) = ManagementGroup(
        "operations_section", T.OPS_TITLE,
        buildList {
            add(hoursRow("operating", T.OPS_OPERATING, s.operatingHours))
            add(hoursRow("customer", T.OPS_CUSTOMER, s.customerHours))
            add(hoursRow("authorized", T.OPS_AUTHORIZED, s.authorizedNonCustomerHours))
            add(hoursRow("unexplained", T.OPS_UNEXPLAINED, s.unexplainedHours))
            add(countRow("discrepancies", T.OPS_DISCREPANCIES, s.meterDiscrepancies.count, s.meterDiscrepancies.route))
            s.meterDiscrepancies.byType.forEach { t -> add(countRow("discrepancy-${t.type}", T.discrepancy(t.type), t.count, t.route)) }
            add(countRow("pending_reports", T.OPS_PENDING_REPORTS, s.pendingReports.count, s.pendingReports.route))
            add(countRow("returned_reports", T.OPS_RETURNED_REPORTS, s.returnedReports.count, s.returnedReports.route))
            if (s.byExcavator.isNotEmpty()) {
                add(heading("by_excavator", T.OPS_BY_EXCAVATOR))
                s.byExcavator.forEach { e ->
                    add(
                        ManagementRow(
                            "excavator-${e.machineId}", DisplayNames.or(e.machineCode ?: e.machineName, e.machineId), h(e.operatingHours),
                            caption = T.excavatorRow(OwnerFormat.hoursNumber(e.customerHours), OwnerFormat.hoursNumber(e.authorizedHours), OwnerFormat.hoursNumber(e.unexplainedHours)),
                            target = ManagementLinks.excavatorTarget(e.machineId, e.route, f, webBase),
                        ),
                    )
                }
            }
        },
    )

    private fun cash(s: CashSectionDto) = ManagementGroup(
        "cash_section", T.CASH_TITLE,
        buildList {
            add(moneyRow("collected", T.CASH_COLLECTED, s.collected))
            add(moneyRow("transferred", T.CASH_TRANSFERRED, s.transferred))
            add(moneyRow("in_transit", T.CASH_IN_TRANSIT, s.inTransit))
            add(moneyRow("declared", T.CASH_DECLARED, s.declaredForRemittance))
            add(moneyRow("confirmed", T.CASH_CONFIRMED, s.confirmedByCompany))
            add(moneyRow("outstanding", T.CASH_OUTSTANDING, s.outstanding))
            add(moneyRow("unconfirmed", T.CASH_UNCONFIRMED, s.unconfirmedRemittances))
            add(moneyRow("disputed_remittances", T.CASH_DISPUTED_REMITTANCES, s.disputedRemittances))
            add(moneyRow("disputed_transfers", T.CASH_DISPUTED_TRANSFERS, s.disputedTransfers))
            if (s.heldByEmployee.isNotEmpty()) {
                add(heading("held", T.CASH_HELD))
                s.heldByEmployee.forEach { b ->
                    add(
                        ManagementRow(
                            "held-${b.staffMemberId}-${b.currency}", DisplayNames.or(b.staffMemberName, b.staffMemberId), money(b.outstanding, b.currency),
                            caption = T.heldCaption(nonZero(b.inTransitOut, b.currency), nonZero(b.claimedUnverifiedHandovers, b.currency), nonZero(b.pendingFloats, b.currency), nonZero(b.approvedRetention, b.currency)),
                            target = target(b.route),
                        ),
                    )
                }
            }
        },
    )

    private fun exceptions(s: ExceptionsSectionDto) = ManagementGroup(
        "exceptions_section", T.EXC_TITLE,
        buildList {
            add(hoursRow("unexplained", T.EXC_UNEXPLAINED, s.unexplainedEngineHours))
            add(moneyRow("shortages", T.EXC_SHORTAGES, s.shortages))
            add(moneyRow("overages", T.EXC_OVERAGES, s.overages))
            add(moneyRow("shortages_period", T.EXC_SHORTAGES_PERIOD, s.shortagesOpenedInPeriod))
            add(moneyRow("overages_period", T.EXC_OVERAGES_PERIOD, s.overagesOpenedInPeriod))
            add(moneyRow("unconfirmed_payments", T.EXC_UNCONFIRMED_PAYMENTS, s.unconfirmedPayments))
            val a = s.unauthorizedAttempts
            add(ManagementRow("attempts", T.EXC_ATTEMPTS, "${a.permissionDenied + a.segregationOfDuties}", T.attemptsCaption(a.permissionDenied, a.segregationOfDuties), target(a.route)))
            add(countRow("missing_reports", T.EXC_MISSING_REPORTS, s.overdueReports.missingDailyReports.count, s.overdueReports.missingDailyReports.route))
            add(countRow("overdue_remittances", T.EXC_OVERDUE_REMITTANCES, s.overdueReports.remittancesOverdueToday.count, s.overdueReports.remittancesOverdueToday.route))
            val c = s.changeoverJobsAwaitingApproval
            add(ManagementRow("changeover", T.EXC_CHANGEOVER, "${c.count}", caption = c.oldestDays?.let(T::changeoverCaption)))
            c.items.forEach { j ->
                add(
                    ManagementRow(
                        "changeover-${j.jobId}", T.changeoverRow(DisplayNames.or(j.jobNumber, j.jobId), DisplayNames.or(j.machineCode ?: j.machineName, j.machineId), DisplayNames.or(j.customerName, j.customerId)),
                        T.changeoverDays(j.daysWaiting), target = target(j.route),
                    ),
                )
            }
            add(heading("approvals", T.approvals(s.outstandingApprovals.total)))
            addAll(kindRows("approval", s.outstandingApprovals.byKind))
            add(ManagementRow("pending", T.pending(s.pendingAdjustments.total), heading = true, target = target(s.pendingAdjustments.route)))
            addAll(kindRows("pending", s.pendingAdjustments.byKind))
            add(heading("variances", T.variances(s.unresolvedVariances.total)))
            s.unresolvedVariances.bySource.forEach { v ->
                add(ManagementRow("variance-${v.source}-${v.unit}", T.varianceSource(v.source), "${v.count}", caption = lines(v.amounts).takeIf { v.amounts.isNotEmpty() }, target = target(v.route)))
            }
        },
    )

    companion object {
        /** Old tiles a present section replaces (the section shows the same figures, with links). */
        fun replacedTiles(s: AccountabilitySummaryDto): Set<String> = buildSet {
            if (s.hoursSection != null) addAll(listOf("customer_hours", "hours_awaiting_activation"))
            if (s.cashSection != null) addAll(listOf("cash", "payments"))
            if (s.exceptionsSection != null) addAll(listOf("approvals", "attempts"))
        }

        /** The counts added in DEC-032 Phase 4 (kind code to value): present and non-zero only. */
        fun newApprovalCounts(a: ApprovalsTileDto): List<Pair<String, String>> = listOfNotNull(
            "adjustment_requests" to a.adjustmentRequests, "hours_transfers" to a.hoursTransfers, "hours_cancellations" to a.hoursCancellations,
            "credit_arrangements" to a.creditArrangements, "discounts" to a.discounts, "meter_corrections" to a.meterCorrections,
            "allocation_corrections" to a.allocationCorrections, "classifications" to a.classifications, "non_revenue_approvals" to a.nonRevenueApprovals,
            "variance_closures" to a.varianceClosures, "meter_baselines" to a.meterBaselines, "meter_resets" to a.meterResets,
            "partial_reasons" to a.partialReasons, "jobs_awaiting_approval" to a.jobsAwaitingApproval, "daily_reports_to_review" to a.dailyReportsToReview,
            "case_closures" to a.caseClosures, "revenue_decisions" to a.revenueDecisions,
        ).mapNotNull { (kind, n) -> n?.takeIf { it != 0 }?.let { T.kind(kind) to "$it" } }
    }
}
