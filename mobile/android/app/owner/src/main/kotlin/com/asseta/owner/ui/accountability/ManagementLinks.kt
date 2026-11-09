package com.asseta.owner.ui.accountability

import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.setup.SetupLinks

/** Where a management figure or record leads: an Owner app screen, or the web console in the browser. */
sealed interface FigureTarget {
    data class App(val destination: OwnerDestination) : FigureTarget
    data class Web(val url: String) : FigureTarget
}

/**
 * Maps a server `route` to the app screen that really shows those records (the table in the strings doc); anything the
 * app has no screen for, or the role may not open, opens the web console. Only relative `/tenant/` routes are followed.
 */
object ManagementLinks {
    private val UUID = Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

    /** Lists whose waiting rows the Approvals screen shows (status absent, or a waiting status). */
    private val APPROVAL_LISTS = setOf(
        "hours/transfers", "hours/cancellations", "hours/credit", "hours/discounts", "meter-corrections", "meter-baselines", "meter-resets",
        "engine-hours/classifications", "non-revenue-approvals", "finance/adjustments/requests", "work-allocations/corrections", "approvals",
        "finance/cash/retentions", "finance/cash/adjustments",
    )
    private val WAITING = setOf("PENDING", "PROPOSED")
    private val WAITING_VARIANCES = setOf("WRITE_OFF_PROPOSED", "CLOSURE_PROPOSED")

    private fun query(route: String): Map<String, String> = route.substringAfter('?', "").split('&').filter { '=' in it }.associate { it.substringBefore('=') to it.substringAfter('=') }

    /** The app screen for [route] the role may open, or null (the web then). */
    fun destination(route: String, f: OwnerFeatures): OwnerDestination? {
        val path = route.substringBefore('?').trim('/').split('/').filter { it.isNotEmpty() }
        if (path.firstOrNull() != "tenant") return null
        val rest = path.drop(1)
        val employee = rest.size == 3 && rest[0] == "staff" && rest[2] == "accountability"
        val d = if (employee || rest.lastOrNull()?.let(UUID::matches) == true) record(rest, route) else list(rest.joinToString("/"), query(route))
        return d?.takeIf { allowed(it, f) }
    }

    /** A record route with an id: as a notification deep link, except the two record kinds the app has no screen for. */
    private fun record(rest: List<String>, route: String): OwnerDestination? = when {
        rest.first() == "work-allocations" && rest.getOrNull(1) != "corrections" -> null
        rest.first() == "finance" && rest.getOrNull(1) == "adjustments" && rest.getOrNull(2) != "requests" -> null
        else -> DeepLinkRouter.fromPath(route)
    }

    private fun list(key: String, q: Map<String, String>): OwnerDestination? {
        val status = q["status"]
        return when {
            key == "hours/balances" -> q["customer_id"]?.takeIf(UUID::matches)?.let { OwnerDestination.HoursStatement(it) } ?: OwnerDestination.CustomerHours
            key == "finance/cash" -> OwnerDestination.Cash.takeIf { q.isEmpty() }
            key == "finance/cash/remittance-overdue" -> OwnerDestination.RemittanceOverdue()
            key == "exceptions" -> OwnerDestination.Exceptions()
            key == "cases" -> OwnerDestination.Cases
            key == "accountability/pending-adjustments" || key == "revenue-differences" -> OwnerDestination.Approvals()
            key == "daily-reports" -> OwnerDestination.Approvals().takeIf { status == "SUBMITTED" }
            key == "jobs" -> OwnerDestination.Approvals().takeIf { status == "PENDING_APPROVAL" }
            key == "finance/cash/variances" -> OwnerDestination.Approvals().takeIf { status in WAITING_VARIANCES }
            key == "finance/cash/remittances" -> OwnerDestination.Approvals().takeIf { status == "CLAIMED" || q["partial_reason_pending"] == "true" }
            key in APPROVAL_LISTS -> OwnerDestination.Approvals().takeIf { status == null || status in WAITING }
            else -> null
        }
    }

    private fun allowed(d: OwnerDestination, f: OwnerFeatures): Boolean = when (d) {
        is OwnerDestination.Approvals -> f.approvalsScreen
        is OwnerDestination.Decision -> DecisionKind.of(d.kind)?.visibleTo(f) == true
        is OwnerDestination.Handover, is OwnerDestination.CashRecord, OwnerDestination.Cash -> f.finance
        is OwnerDestination.RemittanceOverdue -> f.finance && f.cashCustody
        OwnerDestination.CustomerHours, is OwnerDestination.HoursPurchase, is OwnerDestination.HoursStatement -> f.customerHours
        is OwnerDestination.Exceptions, is OwnerDestination.MeterException, is OwnerDestination.MeterReset -> f.meterEvidence
        OwnerDestination.Cases, is OwnerDestination.Case -> f.cases
        is OwnerDestination.EmployeeAccountability -> f.employeeAccountability
        is OwnerDestination.Job, OwnerDestination.Jobs -> f.jobs
        is OwnerDestination.Machine, OwnerDestination.Fleet -> f.fleet
        is OwnerDestination.Alerts -> f.alerts
        else -> true
    }

    /** The app screen, else the web console, else nothing (an empty or non-relative route). */
    fun target(route: String?, f: OwnerFeatures, webBase: String): FigureTarget? {
        if (route.isNullOrBlank()) return null
        destination(route, f)?.let { return FigureTarget.App(it) }
        return SetupLinks.webUrl(webBase, route)?.let { FigureTarget.Web(it) }
    }

    /** An excavator's hours open its daily sheet when machine days are open to the role, else the machine, else the web. */
    fun excavatorTarget(machineId: String, route: String, f: OwnerFeatures, webBase: String): FigureTarget? = when {
        f.machineDays -> FigureTarget.App(OwnerDestination.DailySheet(machineId))
        f.fleet -> FigureTarget.App(OwnerDestination.Machine(machineId))
        else -> target(route, f, webBase)
    }
}
