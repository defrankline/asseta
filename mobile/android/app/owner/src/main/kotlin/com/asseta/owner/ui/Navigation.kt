package com.asseta.owner.ui

import com.asseta.core.domain.owner.OwnerDestination

/** Bottom-bar tabs; opening a tab resets the back stack, any other destination is pushed. */
enum class OwnerTab(val label: String, val root: OwnerDestination) {
    HOME("Home", OwnerDestination.Home),
    FLEET("Fleet", OwnerDestination.Fleet),
    JOBS("Jobs", OwnerDestination.Jobs),
    ALERTS("Alerts", OwnerDestination.Alerts()),
    MORE("More", OwnerDestination.More),
}

object OwnerNavigation {
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
    fun currentTab(stack: List<OwnerDestination>): OwnerTab = stack.firstNotNullOfOrNull { tabOf(it) } ?: OwnerTab.HOME

    fun title(d: OwnerDestination): String = when (d) {
        OwnerDestination.Home -> "Overview"
        OwnerDestination.Fleet -> "Fleet"
        is OwnerDestination.Machine -> "Machine"
        OwnerDestination.Jobs -> "Jobs"
        is OwnerDestination.Job -> "Job"
        is OwnerDestination.Alerts -> "Alerts"
        is OwnerDestination.Approvals -> "Approvals"
        OwnerDestination.Cases -> "Investigations"
        is OwnerDestination.Case -> "Investigation"
        is OwnerDestination.Notifications -> "Notifications"
        OwnerDestination.Settings -> "Settings"
        OwnerDestination.More -> "More"
    }
}
