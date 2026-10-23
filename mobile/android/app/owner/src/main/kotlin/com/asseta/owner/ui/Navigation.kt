package com.asseta.owner.ui

import com.asseta.core.domain.owner.OwnerDestination

/** Bottom-bar tabs; opening a tab resets the back stack, any other destination is pushed. */
enum class OwnerTab(val label: String, val root: OwnerDestination) {
    HOME("Overview", OwnerDestination.Home),
    FLEET("Fleet", OwnerDestination.Fleet),
    JOBS("Jobs", OwnerDestination.Jobs),
    ALERTS("Alerts", OwnerDestination.Alerts()),
    MORE("More", OwnerDestination.More),
}

object OwnerNavigation {
    /** Tabs the role can use (same gating as iOS): Overview needs fleet, jobs or finance; Alerts needs fleet. */
    fun tabs(features: OwnerFeatures): List<OwnerTab> = OwnerTab.entries.filter {
        when (it) {
            OwnerTab.HOME -> features.overview
            OwnerTab.FLEET, OwnerTab.ALERTS -> features.fleet
            OwnerTab.JOBS -> features.jobs
            OwnerTab.MORE -> true
        }
    }

    /** First screen after entering a company: Overview, else Fleet, else More. */
    fun start(features: OwnerFeatures): OwnerDestination = tabs(features).first().root

    fun tabOf(d: OwnerDestination): OwnerTab? = when (d) {
        OwnerDestination.Home -> OwnerTab.HOME
        OwnerDestination.Fleet -> OwnerTab.FLEET
        OwnerDestination.Jobs -> OwnerTab.JOBS
        is OwnerDestination.Alerts -> if (d.alertId == null) OwnerTab.ALERTS else null
        OwnerDestination.More -> OwnerTab.MORE
        else -> null
    }

    fun navigate(stack: List<OwnerDestination>, to: OwnerDestination): List<OwnerDestination> = when {
        tabOf(to) != null -> listOf(to)
        stack.lastOrNull() == to -> stack
        else -> stack + to
    }

    fun back(stack: List<OwnerDestination>): List<OwnerDestination> = if (stack.size > 1) stack.dropLast(1) else stack

    /** The tab highlighted for the current stack (its root). */
    fun currentTab(stack: List<OwnerDestination>): OwnerTab = stack.firstNotNullOfOrNull { tabOf(it) } ?: OwnerTab.MORE

    /** Screen titles, worded as on iOS; the Overview is titled with the company name. */
    fun title(d: OwnerDestination, tenantName: String = "Overview"): String = when (d) {
        OwnerDestination.Home -> tenantName
        OwnerDestination.Fleet -> "Fleet"
        is OwnerDestination.Machine -> "Machine"
        OwnerDestination.Jobs -> "Jobs"
        is OwnerDestination.Job -> "Job"
        is OwnerDestination.Alerts -> if (d.alertId == null) "Alerts" else "Alert"
        is OwnerDestination.Approvals -> if (d.approvalId == null) "Approvals" else "Approval"
        OwnerDestination.Cases -> "Investigations"
        is OwnerDestination.Case -> "Investigation"
        is OwnerDestination.Notifications -> if (d.notificationId == null) "Notifications" else "Notification"
        OwnerDestination.Settings -> "Settings"
        OwnerDestination.More -> "More"
    }
}
