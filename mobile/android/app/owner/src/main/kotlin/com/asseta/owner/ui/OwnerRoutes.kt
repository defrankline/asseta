package com.asseta.owner.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.owner.OwnerGraph
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.accountability.AccountabilityScreen
import com.asseta.owner.ui.accountability.AccountabilityViewModel
import com.asseta.owner.ui.accountability.CashRecordScreen
import com.asseta.owner.ui.accountability.CashRecordViewModel
import com.asseta.owner.ui.accountability.RemittanceOverdueListScreen
import com.asseta.owner.ui.accountability.RemittanceOverdueListViewModel
import com.asseta.owner.ui.accountability.RemittanceOverdueScreen
import com.asseta.owner.ui.accountability.RemittanceOverdueViewModel
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionScreen
import com.asseta.owner.ui.accountability.DecisionViewModel
import com.asseta.owner.ui.accountability.OwnerAccountabilityTexts
import com.asseta.owner.ui.accountability.DailySheetScreen
import com.asseta.owner.ui.accountability.CustomerHoursScreen
import com.asseta.owner.ui.accountability.CustomerHoursViewModel
import com.asseta.owner.ui.accountability.HoursPurchaseScreen
import com.asseta.owner.ui.accountability.HoursPurchaseViewModel
import com.asseta.owner.ui.accountability.HoursStatementScreen
import com.asseta.owner.ui.accountability.HoursStatementViewModel
import com.asseta.owner.ui.accountability.DailySheetViewModel
import com.asseta.owner.ui.accountability.RevenueDifferenceScreen
import com.asseta.owner.ui.accountability.RevenueDifferenceViewModel
import com.asseta.owner.ui.accountability.SheetDayScreen
import com.asseta.owner.ui.accountability.SheetDayViewModel
import com.asseta.owner.ui.alerts.AlertDetailScreen
import com.asseta.owner.ui.alerts.AlertDetailViewModel
import com.asseta.owner.ui.alerts.AlertsScreen
import com.asseta.owner.ui.alerts.AlertsViewModel
import com.asseta.owner.ui.approvals.ApprovalDetailScreen
import com.asseta.owner.ui.approvals.ApprovalDetailViewModel
import com.asseta.owner.ui.approvals.ApprovalsScreen
import com.asseta.owner.ui.approvals.ApprovalsViewModel
import com.asseta.owner.ui.approvals.MeterResetScreen
import com.asseta.owner.ui.approvals.MeterResetViewModel
import com.asseta.owner.ui.cash.CashScreen
import com.asseta.owner.ui.cash.CashViewModel
import com.asseta.owner.ui.cash.HandoverScreen
import com.asseta.owner.ui.cash.HandoverViewModel
import com.asseta.owner.ui.cases.CaseDetailScreen
import com.asseta.owner.ui.cases.CaseDetailViewModel
import com.asseta.owner.ui.cases.CasesScreen
import com.asseta.owner.ui.cases.CasesViewModel
import com.asseta.owner.ui.exceptions.ExceptionDetailScreen
import com.asseta.owner.ui.exceptions.ExceptionDetailViewModel
import com.asseta.owner.ui.exceptions.ExceptionsScreen
import com.asseta.owner.ui.exceptions.ExceptionsViewModel
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
import com.asseta.owner.ui.notifications.NotificationDetailScreen
import com.asseta.owner.ui.notifications.NotificationDetailViewModel
import com.asseta.owner.ui.notifications.NotificationsScreen
import com.asseta.owner.ui.notifications.NotificationsViewModel
import com.asseta.owner.ui.settings.PushControl
import com.asseta.owner.ui.settings.SettingsScreen
import com.asseta.owner.ui.settings.SettingsViewModel
import com.asseta.owner.ui.spend.FieldSpendScreen
import com.asseta.owner.ui.spend.FieldSpendViewModel

/** Live-update entities of the accountability decisions (WebSocket "entity changed" frames). */
private val ACCOUNTABILITY_ENTITIES = arrayOf(
    "customer_discount", "credit_arrangement", "hours_transfer", "hours_cancellation", "meter_baseline", "meter_correction",
    "engine_hour_classification", "cash_variance", "cash_retention", "custody_adjustment", "revenue_difference", "non_revenue_approval",
)

/** Live-update entities of the customer hours screens. */
private val HOURS_ENTITIES = arrayOf("hours_purchase", "hours_transfer", "hours_cancellation", "job")

/** Live-update entities behind the people scorecard. */
private val OVERSIGHT_ENTITIES = arrayOf("job_exception", "alert", "cash_remittance_overdue", "cash_variance", "revenue_difference", "site_checkin", "case")

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
    val features = session.features
    val now = { System.currentTimeMillis() }
    when (route) {
        OwnerDestination.Home -> {
            val vm: HomeViewModel = viewModel(key = "home-$t") { HomeViewModel(data, graph.refreshTriggers("alert", "approval", "job", "case", "fleet.position", debounceMs = 10_000)) }
            val setup by data.setupProgress.collectAsStateWithLifecycle()
            val banner = setup?.takeIf { features.setupRead && it.showBanner }
            HomeScreen(vm, features, now, open, header = banner?.let { b -> { com.asseta.owner.ui.setup.SetupBanner(b) { open(OwnerDestination.SetupChecklist) } } })
        }
        OwnerDestination.Fleet -> {
            val vm: FleetViewModel = viewModel(key = "fleet-$t") { FleetViewModel(data, graph.refreshTriggers("fleet.position", "alert", debounceMs = 10_000)) }
            FleetScreen(vm, now) { open(OwnerDestination.Machine(it)) }
        }
        is OwnerDestination.Machine -> {
            val vm: MachineViewModel = viewModel(key = "machine-$t-${route.machineId}") {
                MachineViewModel(data, route.machineId, graph.refreshTriggers("fleet.position", "alert", debounceMs = 10_000))
            }
            MachineScreen(vm, features, online, now, open)
        }
        OwnerDestination.Jobs -> {
            val vm: JobsViewModel = viewModel(key = "jobs-$t") { JobsViewModel(data, graph.refreshTriggers("job")) }
            JobsScreen(vm, session, online) { open(OwnerDestination.Job(it)) }
        }
        is OwnerDestination.Job -> {
            val vm: JobDetailViewModel = viewModel(key = "job-$t-${route.jobId}") {
                JobDetailViewModel(data, route.jobId, features.expenses, graph.refreshTriggers("job", "meter_capture", "exception", "expense", "fuel_event"))
            }
            JobDetailScreen(vm, session, online, open)
        }
        is OwnerDestination.Alerts -> {
            val id = route.alertId
            if (id == null) {
                val vm: AlertsViewModel = viewModel(key = "alerts-$t") { AlertsViewModel(data, graph.refreshTriggers("alert")) }
                AlertsScreen(vm, open)
            } else {
                val vm: AlertDetailViewModel = viewModel(key = "alert-$t-$id") { AlertDetailViewModel(data, id, graph.refreshTriggers("alert")) }
                AlertDetailScreen(vm, session, online, open)
            }
        }
        is OwnerDestination.Approvals -> {
            val id = route.approvalId
            if (id == null) {
                val vm: ApprovalsViewModel = viewModel(key = "approvals-$t") {
                    ApprovalsViewModel(
                        data,
                        graph.refreshTriggers("approval", "expense", "meter_reset", "job", "cash_handover", "meter_exception", "exception", *ACCOUNTABILITY_ENTITIES),
                        meterResets = features.meterEvidence, jobs = features.jobs, handovers = features.finance, exceptions = features.meterEvidence,
                        decisions = DecisionKind.visible(features),
                        revenueOpen = features.revenueExplain || features.revenueDecide,
                    )
                }
                ApprovalsScreen(vm, open)
            } else {
                val vm: ApprovalDetailViewModel = viewModel(key = "approval-$t-$id") { ApprovalDetailViewModel(data, id, graph.refreshTriggers("approval", "expense")) }
                ApprovalDetailScreen(vm, session, online)
            }
        }
        is OwnerDestination.MeterReset -> {
            val vm: MeterResetViewModel = viewModel(key = "meter-reset-$t-${route.resetId}") { MeterResetViewModel(data, route.resetId, graph.refreshTriggers("meter_reset")) }
            MeterResetScreen(vm, session, online)
        }
        is OwnerDestination.Exceptions -> {
            val vm: ExceptionsViewModel = viewModel(key = "exceptions-$t-${route.jobId ?: "all"}") {
                ExceptionsViewModel(data, route.jobId, graph.refreshTriggers("exception", "job"))
            }
            ExceptionsScreen(vm, open)
        }
        is OwnerDestination.MeterException -> {
            val vm: ExceptionDetailViewModel = viewModel(key = "exception-$t-${route.exceptionId}") {
                ExceptionDetailViewModel(data, route.exceptionId, graph.refreshTriggers("meter_exception", "exception"))
            }
            ExceptionDetailScreen(vm, session, online, open)
        }
        is OwnerDestination.Handover -> {
            val vm: HandoverViewModel = viewModel(key = "handover-$t-${route.handoverId}") { HandoverViewModel(data, route.handoverId, graph.refreshTriggers("cash_handover")) }
            HandoverScreen(vm, session, online)
        }
        OwnerDestination.FieldSpend -> {
            val vm: FieldSpendViewModel = viewModel(key = "spend-$t") { FieldSpendViewModel(data, graph.refreshTriggers("expense", "fuel_event")) }
            FieldSpendScreen(vm, features, open)
        }
        OwnerDestination.Cash -> {
            val vm: CashViewModel = viewModel(key = "cash-$t") {
                CashViewModel(data, graph.refreshTriggers("cash", "cash_handover", "expense"), handovers = features.finance)
            }
            CashScreen(vm, session, online, open)
        }
        OwnerDestination.Cases -> {
            val vm: CasesViewModel = viewModel(key = "cases-$t") { CasesViewModel(data, graph.refreshTriggers("case")) }
            CasesScreen(vm) { open(OwnerDestination.Case(it)) }
        }
        is OwnerDestination.Case -> {
            val vm: CaseDetailViewModel = viewModel(key = "case-$t-${route.caseId}") { CaseDetailViewModel(data, route.caseId, graph.refreshTriggers("case")) }
            CaseDetailScreen(vm, features, open)
        }
        is OwnerDestination.Notifications -> {
            val id = route.notificationId
            if (id == null) {
                val vm: NotificationsViewModel = viewModel(key = "inbox-$t") { NotificationsViewModel(data, graph.liveUpdates, graph.refreshTriggers()) }
                NotificationsScreen(vm, online, open)
            } else {
                val vm: NotificationDetailViewModel = viewModel(key = "notification-$t-$id") { NotificationDetailViewModel(data, id) }
                NotificationDetailScreen(vm)
            }
        }
        OwnerDestination.Settings -> {
            val vm: SettingsViewModel = viewModel(key = "settings-$t") {
                SettingsViewModel(data, object : PushControl {
                    override val available get() = graph.push.available
                    override val providerName get() = graph.push.providerName
                    override val registered get() = graph.push.registeredDeviceId != null
                    override suspend fun register() = graph.push.register()
                })
            }
            SettingsScreen(vm, session, online)
        }
        OwnerDestination.More -> MoreScreen(session, unread, open)
        is OwnerDestination.Decision -> {
            val kind = DecisionKind.of(route.kind)
            if (kind == DecisionKind.REVENUE_DIFFERENCE) {
                val vm: RevenueDifferenceViewModel = viewModel(key = "revenue-difference-$t-${route.id}") {
                    RevenueDifferenceViewModel(data, route.id, features.revenueExplain, graph.refreshTriggers("revenue_difference"))
                }
                RevenueDifferenceScreen(vm, session, online)
            } else if (kind == null) {
                com.asseta.owner.ui.common.EmptyState(OwnerAccountabilityTexts.NOT_FOUND_TITLE, OwnerAccountabilityTexts.NOT_FOUND_MESSAGE)
            } else {
                val vm: DecisionViewModel = viewModel(key = "decision-$t-${route.kind}-${route.id}") {
                    DecisionViewModel(data, kind, route.id, graph.refreshTriggers(*ACCOUNTABILITY_ENTITIES))
                }
                DecisionScreen(vm, session, online)
            }
        }
        is OwnerDestination.CashRecord -> {
            val vm: CashRecordViewModel = viewModel(key = "cash-record-$t-${route.kind}-${route.id}") {
                CashRecordViewModel(data, route.kind, route.id, graph.refreshTriggers("cash_transfer", "supervisor_cash_custody"))
            }
            CashRecordScreen(vm)
        }
        is OwnerDestination.RemittanceOverdue -> {
            val id = route.id
            if (id == null) {
                val vm: RemittanceOverdueListViewModel = viewModel(key = "overdue-$t") {
                    RemittanceOverdueListViewModel(data, graph.refreshTriggers("cash_remittance_overdue", "cash_handover"))
                }
                RemittanceOverdueListScreen(vm, open)
            } else {
                val vm: RemittanceOverdueViewModel = viewModel(key = "overdue-$t-$id") {
                    RemittanceOverdueViewModel(data, id, graph.refreshTriggers("cash_remittance_overdue"))
                }
                RemittanceOverdueScreen(vm)
            }
        }
        is OwnerDestination.DailySheet -> {
            val vm: DailySheetViewModel = viewModel(key = "daily-sheet-$t-${route.machineId}") {
                DailySheetViewModel(data, route.machineId, graph.refreshTriggers("revenue_difference", "meter_capture"))
            }
            DailySheetScreen(vm, open)
        }
        is OwnerDestination.SheetDay -> {
            val vm: SheetDayViewModel = viewModel(key = "sheet-day-$t-${route.machineId}-${route.day}") {
                SheetDayViewModel(data, route.machineId, route.day, graph.refreshTriggers("revenue_difference", "meter_capture"))
            }
            SheetDayScreen(vm, features, open)
        }
        OwnerDestination.CustomerHours -> {
            val vm: CustomerHoursViewModel = viewModel(key = "customer-hours-$t") { CustomerHoursViewModel(data, graph.refreshTriggers(*HOURS_ENTITIES)) }
            CustomerHoursScreen(vm, open)
        }
        is OwnerDestination.HoursPurchase -> {
            val vm: HoursPurchaseViewModel = viewModel(key = "hours-purchase-$t-${route.purchaseId}") {
                HoursPurchaseViewModel(data, route.purchaseId, graph.refreshTriggers(*HOURS_ENTITIES))
            }
            HoursPurchaseScreen(vm, open)
        }
        is OwnerDestination.HoursStatement -> {
            val vm: HoursStatementViewModel = viewModel(key = "hours-statement-$t-${route.customerId}") {
                HoursStatementViewModel(data, route.customerId, graph.refreshTriggers(*HOURS_ENTITIES))
            }
            HoursStatementScreen(vm, online, route.customerName)
        }
        OwnerDestination.Scorecard -> {
            val vm: com.asseta.owner.ui.accountability.ScorecardViewModel = viewModel(key = "scorecard-$t") {
                com.asseta.owner.ui.accountability.ScorecardViewModel(data, graph.refreshTriggers(*OVERSIGHT_ENTITIES))
            }
            com.asseta.owner.ui.accountability.ScorecardScreen(vm, open)
        }
        is OwnerDestination.ScorecardPerson -> {
            val (from, to) = com.asseta.owner.ui.accountability.ScorecardPeriod.LAST_30_DAYS.range(java.time.LocalDate.now()).let { (f, l) ->
                (route.dayFrom?.let { runCatching { java.time.LocalDate.parse(it) }.getOrNull() } ?: f) to
                    (route.dayTo?.let { runCatching { java.time.LocalDate.parse(it) }.getOrNull() } ?: l)
            }
            val vm: com.asseta.owner.ui.accountability.ScorecardPersonViewModel = viewModel(key = "scorecard-person-$t-${route.staffId}-$from-$to") {
                com.asseta.owner.ui.accountability.ScorecardPersonViewModel(data, route.staffId, from, to, graph.refreshTriggers(*OVERSIGHT_ENTITIES))
            }
            com.asseta.owner.ui.accountability.ScorecardPersonScreen(vm, features, open)
        }
        OwnerDestination.UnbilledWork -> {
            val vm: com.asseta.owner.ui.accountability.UnbilledWorkViewModel = viewModel(key = "unbilled-$t") {
                com.asseta.owner.ui.accountability.UnbilledWorkViewModel(data, graph.refreshTriggers("job", "invoice"))
            }
            com.asseta.owner.ui.accountability.UnbilledWorkScreen(vm, features, open)
        }
        OwnerDestination.IdleMachines -> {
            val vm: com.asseta.owner.ui.accountability.IdleMachinesViewModel = viewModel(key = "idle-$t") {
                com.asseta.owner.ui.accountability.IdleMachinesViewModel(data, graph.refreshTriggers("job", "machine"))
            }
            com.asseta.owner.ui.accountability.IdleMachinesScreen(vm, features, open)
        }
        OwnerDestination.SetupChecklist -> {
            val vm: com.asseta.owner.ui.setup.SetupChecklistViewModel = viewModel(key = "setup-$t") {
                com.asseta.owner.ui.setup.SetupChecklistViewModel(data, graph.refreshTriggers())
            }
            com.asseta.owner.ui.setup.SetupChecklistScreen(vm, session, online, com.asseta.core.network.NetworkFactory.defaultWebBaseUrl, open)
        }
        OwnerDestination.Accountability -> {
            val vm: AccountabilityViewModel = viewModel(key = "accountability-$t") {
                AccountabilityViewModel(data, graph.refreshTriggers(*ACCOUNTABILITY_ENTITIES, "cash_handover", "approval", "case", "cash_remittance_overdue"))
            }
            AccountabilityScreen(vm, features, open)
        }
    }
}
