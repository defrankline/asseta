package com.asseta.owner.ui

import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.owner.OwnerGraph
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.alerts.AlertsScreen
import com.asseta.owner.ui.alerts.AlertsViewModel
import com.asseta.owner.ui.approvals.ApprovalsScreen
import com.asseta.owner.ui.approvals.ApprovalsViewModel
import com.asseta.owner.ui.cases.CaseDetailScreen
import com.asseta.owner.ui.cases.CaseDetailViewModel
import com.asseta.owner.ui.cases.CasesScreen
import com.asseta.owner.ui.cases.CasesViewModel
import com.asseta.owner.ui.fleet.FleetScreen
import com.asseta.owner.ui.fleet.FleetViewModel
import com.asseta.owner.ui.home.HomeScreen
import com.asseta.owner.ui.home.HomeViewModel
import com.asseta.owner.ui.jobs.JobDetailScreen
import com.asseta.owner.ui.jobs.JobDetailViewModel
import com.asseta.owner.ui.jobs.JobsScreen
import com.asseta.owner.ui.jobs.JobsViewModel
import com.asseta.owner.ui.machine.MachineScreen
import com.asseta.owner.ui.machine.MachineViewModel
import com.asseta.owner.ui.notifications.NotificationsScreen
import com.asseta.owner.ui.notifications.NotificationsViewModel
import com.asseta.owner.ui.settings.PushControl
import com.asseta.owner.ui.settings.SettingsScreen
import com.asseta.owner.ui.settings.SettingsViewModel

/** One screen per destination; view models are keyed by tenant (and id) so switching tenant never mixes data. */
@Composable
fun OwnerRoutes(
    graph: OwnerGraph,
    data: OwnerData,
    session: OwnerSession,
    route: OwnerDestination,
    online: Boolean,
    unread: Int?,
    open: (OwnerDestination) -> Unit,
) {
    val t = session.tenantId
    val now = { System.currentTimeMillis() }
    when (route) {
        OwnerDestination.Home -> {
            val vm: HomeViewModel = viewModel(key = "home-$t") { HomeViewModel(data, graph.refreshTriggers("alert", "approval", "job", "case", "fleet.position", debounceMs = 10_000)) }
            HomeScreen(vm, session.tenantName, now, open)
        }
        OwnerDestination.Fleet -> {
            val vm: FleetViewModel = viewModel(key = "fleet-$t") { FleetViewModel(data, graph.refreshTriggers("fleet.position", "alert", debounceMs = 10_000)) }
            FleetScreen(vm, now) { open(OwnerDestination.Machine(it)) }
        }
        is OwnerDestination.Machine -> {
            val vm: MachineViewModel = viewModel(key = "machine-$t-${route.machineId}") {
                MachineViewModel(data, route.machineId, graph.refreshTriggers("fleet.position", "alert", debounceMs = 10_000))
            }
            MachineScreen(vm, online, now, open)
        }
        OwnerDestination.Jobs -> {
            val vm: JobsViewModel = viewModel(key = "jobs-$t") { JobsViewModel(data, graph.refreshTriggers("job")) }
            JobsScreen(vm) { open(OwnerDestination.Job(it)) }
        }
        is OwnerDestination.Job -> {
            val vm: JobDetailViewModel = viewModel(key = "job-$t-${route.jobId}") { JobDetailViewModel(data, route.jobId, graph.refreshTriggers("job", "meter_capture")) }
            JobDetailScreen(vm, online, open)
        }
        is OwnerDestination.Alerts -> {
            val vm: AlertsViewModel = viewModel(key = "alerts-$t-${route.alertId}") { AlertsViewModel(data, route.alertId, graph.refreshTriggers("alert")) }
            AlertsScreen(vm, session, online, open)
        }
        is OwnerDestination.Approvals -> {
            val vm: ApprovalsViewModel = viewModel(key = "approvals-$t-${route.approvalId}") { ApprovalsViewModel(data, route.approvalId, graph.refreshTriggers("approval", "expense")) }
            ApprovalsScreen(vm, session, online)
        }
        OwnerDestination.Cases -> {
            val vm: CasesViewModel = viewModel(key = "cases-$t") { CasesViewModel(data, graph.refreshTriggers("case")) }
            CasesScreen(vm) { open(OwnerDestination.Case(it)) }
        }
        is OwnerDestination.Case -> {
            val vm: CaseDetailViewModel = viewModel(key = "case-$t-${route.caseId}") { CaseDetailViewModel(data, route.caseId, graph.refreshTriggers("case")) }
            CaseDetailScreen(vm, open)
        }
        is OwnerDestination.Notifications -> {
            val vm: NotificationsViewModel = viewModel(key = "inbox-$t") { NotificationsViewModel(data, graph.liveUpdates, graph.refreshTriggers()) }
            NotificationsScreen(vm, online, open)
        }
        OwnerDestination.Settings -> {
            val vm: SettingsViewModel = viewModel(key = "settings-$t") {
                SettingsViewModel(data, object : PushControl {
                    override val available get() = graph.push.available
                    override val providerName get() = graph.push.providerName
                    override suspend fun register() = graph.push.register()
                })
            }
            SettingsScreen(vm, online, session.tenantName)
        }
        OwnerDestination.More -> MoreScreen(unread, open)
    }
}
