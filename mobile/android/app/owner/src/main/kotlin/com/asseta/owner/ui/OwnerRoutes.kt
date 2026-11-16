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
import com.asseta.owner.ui.accountability.HoursPurchaseScreen
import com.asseta.owner.ui.accountability.HoursPurchaseViewModel
import com.asseta.owner.ui.accountability.HoursStatementScreen
import com.asseta.owner.ui.accountability.HoursStatementViewModel
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
import com.asseta.owner.ui.approvals.PaymentReviewScreen
import com.asseta.owner.ui.approvals.PaymentReviewViewModel
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
import com.asseta.owner.ui.home.OwnerHomeScreen
import com.asseta.owner.ui.home.OwnerHomeViewModel
import com.asseta.owner.ui.reports.ReportApprovalScreen
import com.asseta.owner.ui.reports.ReportApprovalViewModel
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
    "engine_hour_classification", "cash_variance", "cash_retention", "custody_adjustment", "daily_report", "work_allocation_correction",
    "work_allocation", "adjustment_request",
)

/** Live-update entities of the customer hours screens. */
private val HOURS_ENTITIES = arrayOf("hours_purchase", "hours_transfer", "hours_cancellation", "adjustment_request", "machine_report", "credit_invoice")

/** Live-update entities of machine reports and the credit sales waiting next to them (ADR-008). */
private val REPORT_ENTITIES = arrayOf("machine_report", "meter_capture", "hours_purchase", "credit_invoice")

/**
 * The company's approvals list: every kind the role may decide (ADR-008: machine reports, credit sales, expenses, then
 * the rest). One instance per company, shared by the side menu badge, Home and the Approvals screen.
 */
fun approvalsViewModel(graph: OwnerGraph, data: OwnerData, features: OwnerFeatures): ApprovalsViewModel = ApprovalsViewModel(
    data,
    graph.refreshTriggers(
        "approval", "expense", "meter_reset", "cash_handover", "customer_payment", "meter_exception", "exception", "petty_cash_movement",
        "petty_cash_adjustment", *REPORT_ENTITIES, *ACCOUNTABILITY_ENTITIES,
    ),
    meterResets = features.meterEvidence, handovers = features.finance, exceptions = features.meterEvidence,
    payments = features.confirmPayments,
    decisions = DecisionKind.visible(features),
    expenseRequests = features.approvals,
    pettyCash = features.pettyCashApprove,
    machineReports = features.machineReports,
    creditSales = features.creditSales,
    expenseDetails = features.expenses,
)

/** Live-update entities behind the people scorecard. */
private val OVERSIGHT_ENTITIES = arrayOf("meter_exception", "alert", "cash_remittance_overdue", "cash_variance", "case")

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
    /** The company's approvals list (shared with the side menu badge and Home); null without any approval kind. */
    approvals: ApprovalsViewModel? = null,
    /** Opens the side menu (Home's menu button). */
    onMenu: () -> Unit = {},
    setTitle: (OwnerDestination, String) -> Unit = { _, _ -> },
) {
    val t = session.tenantId
    val features = session.features
    val now = { System.currentTimeMillis() }
    when (route) {
        OwnerDestination.Home -> {
            val vm: OwnerHomeViewModel = viewModel(key = "home-$t") { OwnerHomeViewModel(data, features, graph.refreshTriggers(*REPORT_ENTITIES, "hours_purchase", "cash_handover", debounceMs = 5_000)) }
            val pendingReports = approvals?.reports?.state?.collectAsStateWithLifecycle()?.value?.data
            val counts = approvals?.counts?.collectAsStateWithLifecycle()?.value
            val setup by data.setupProgress.collectAsStateWithLifecycle()
            val banner = setup?.takeIf { features.setupRead && it.showBanner }
            val notice = session.companyNotice
            val header: (@Composable () -> Unit)? = if (banner == null && notice == null) null else {
                {
                    androidx.compose.foundation.layout.Column(verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(androidx.compose.ui.unit.Dp(12f))) {
                        notice?.let { text ->
                            val opens = features.closeCompany
                            com.asseta.core.ui.session.CompanyNoticeBanner(
                                text,
                                actionLabel = if (opens) com.asseta.owner.ui.settings.ClosureTexts.BANNER_ACTION else null,
                                onOpen = if (opens) ({ open(OwnerDestination.CompanyClosure) }) else null,
                            )
                        }
                        banner?.let { b -> com.asseta.owner.ui.setup.SetupBanner(b) { open(OwnerDestination.SetupChecklist) } }
                    }
                }
            }
            OwnerHomeScreen(vm, features, session.displayName, session.tenantName, counts, pendingReports, unread, now, onMenu, open, header = header)
        }
        OwnerDestination.Fleet -> {
            val vm: FleetViewModel = viewModel(key = "fleet-$t") { FleetViewModel(data, graph.refreshTriggers("fleet.position", "alert", debounceMs = 10_000)) }
            FleetScreen(vm, now, features.tracking) { open(OwnerDestination.Machine(it)) }
        }
        is OwnerDestination.Machine -> {
            val vm: MachineViewModel = viewModel(key = "machine-$t-${route.machineId}") {
                MachineViewModel(data, route.machineId, graph.refreshTriggers("fleet.position", "alert", debounceMs = 10_000), tracking = features.tracking)
            }
            MachineScreen(vm, features, online, now, open)
        }
        // The old More tab is routed to Home before it gets here.
        OwnerDestination.More -> Unit
        is OwnerDestination.MachineReport -> {
            val vm: ReportApprovalViewModel = viewModel(key = "machine-report-$t-${route.reportId}") {
                ReportApprovalViewModel(data, route.reportId, features.meterEvidence, graph.refreshTriggers(*REPORT_ENTITIES))
            }
            ReportApprovalScreen(vm, session, online, now)
        }
        OwnerDestination.Customers -> {
            val vm: com.asseta.owner.ui.customers.CustomersViewModel = viewModel(key = "customers-$t") {
                com.asseta.owner.ui.customers.CustomersViewModel(data, graph.refreshTriggers(*HOURS_ENTITIES))
            }
            com.asseta.owner.ui.customers.CustomersScreen(vm, open)
        }
        OwnerDestination.Machines -> {
            val vm: com.asseta.owner.ui.machines.MachinesViewModel = viewModel(key = "machines-$t") {
                com.asseta.owner.ui.machines.MachinesViewModel(data, features, graph.refreshTriggers(*REPORT_ENTITIES, "fleet.position", debounceMs = 10_000))
            }
            com.asseta.owner.ui.machines.MachinesScreen(vm, features, now, open)
        }
        OwnerDestination.Money -> {
            val vm: com.asseta.owner.ui.money.MoneyViewModel = viewModel(key = "money-$t") {
                com.asseta.owner.ui.money.MoneyViewModel(data, features, graph.refreshTriggers("hours_purchase", "customer_payment", "credit_invoice", "cash_handover", "cash", "expense"))
            }
            com.asseta.owner.ui.money.MoneyScreen(vm, features, open)
        }
        OwnerDestination.Reports, OwnerDestination.HoursByReason -> {
            // One instance for Reports and the reason breakdown, so the chosen period carries over.
            val vm: com.asseta.owner.ui.reports.OwnerReportsViewModel = viewModel(key = "reports-$t") {
                com.asseta.owner.ui.reports.OwnerReportsViewModel(data, features, graph.refreshTriggers(*REPORT_ENTITIES))
            }
            if (route == OwnerDestination.Reports) com.asseta.owner.ui.reports.OwnerReportsScreen(vm, features, open) else com.asseta.owner.ui.reports.HoursByReasonScreen(vm)
        }
        is OwnerDestination.RecordPayment -> {
            val vm: com.asseta.owner.ui.money.PaymentViewModel = viewModel(key = "payment-form-$t-${route.invoiceId}") {
                com.asseta.owner.ui.money.PaymentViewModel(data, route.invoiceId)
            }
            com.asseta.owner.ui.money.PaymentScreen(vm, session, online)
        }
        OwnerDestination.Dashboard -> {
            val vm: HomeViewModel = viewModel(key = "dashboard-$t") { HomeViewModel(data, graph.refreshTriggers("alert", "approval", "case", "fleet.position", debounceMs = 10_000)) }
            HomeScreen(vm, features, now, open)
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
                if (approvals == null) {
                    com.asseta.owner.ui.common.EmptyState(com.asseta.owner.ui.approvals.ApprovalsTexts.EMPTY_TITLE, com.asseta.owner.ui.approvals.ApprovalsTexts.EMPTY_MESSAGE)
                } else {
                    ApprovalsScreen(approvals, session, online, now, open)
                }
            } else {
                val vm: ApprovalDetailViewModel = viewModel(key = "approval-$t-$id") { ApprovalDetailViewModel(data, id, graph.refreshTriggers("approval", "expense")) }
                ApprovalDetailScreen(vm, session, online)
            }
        }
        is OwnerDestination.MeterReset -> {
            val vm: MeterResetViewModel = viewModel(key = "meter-reset-$t-${route.resetId}") { MeterResetViewModel(data, route.resetId, graph.refreshTriggers("meter_reset")) }
            MeterResetScreen(vm, session, online)
        }
        OwnerDestination.Exceptions -> {
            val vm: ExceptionsViewModel = viewModel(key = "exceptions-$t") {
                ExceptionsViewModel(data, graph.refreshTriggers("exception", "meter_exception"))
            }
            ExceptionsScreen(vm, open)
        }
        is OwnerDestination.MeterException -> {
            val vm: ExceptionDetailViewModel = viewModel(key = "exception-$t-${route.exceptionId}") {
                ExceptionDetailViewModel(data, route.exceptionId, graph.refreshTriggers("meter_exception", "exception"))
            }
            ExceptionDetailScreen(vm, session, online, open)
        }
        is OwnerDestination.PettyCashMovement -> {
            val vm: com.asseta.owner.ui.approvals.PettyCashReviewViewModel = viewModel(key = "petty-movement-$t-${route.movementId}") {
                com.asseta.owner.ui.approvals.PettyCashReviewViewModel.movement(data, route.movementId, graph.refreshTriggers("petty_cash_movement"))
            }
            com.asseta.owner.ui.approvals.PettyCashReviewScreen(vm, session, online)
        }
        is OwnerDestination.PettyCashAdjustment -> {
            val vm: com.asseta.owner.ui.approvals.PettyCashReviewViewModel = viewModel(key = "petty-adjustment-$t-${route.adjustmentId}") {
                com.asseta.owner.ui.approvals.PettyCashReviewViewModel.adjustment(data, route.adjustmentId, graph.refreshTriggers("petty_cash_adjustment"))
            }
            com.asseta.owner.ui.approvals.PettyCashReviewScreen(vm, session, online)
        }
        is OwnerDestination.CustomerPayment -> {
            val vm: PaymentReviewViewModel = viewModel(key = "payment-$t-${route.paymentId}") { PaymentReviewViewModel(data, route.paymentId, graph.refreshTriggers("customer_payment")) }
            PaymentReviewScreen(vm, session, online, open)
        }
        is OwnerDestination.Handover -> {
            val vm: HandoverViewModel = viewModel(key = "handover-$t-${route.handoverId}") { HandoverViewModel(data, route.handoverId, graph.refreshTriggers("cash_handover")) }
            HandoverScreen(vm, session, online, open)
        }
        OwnerDestination.FieldSpend -> {
            val vm: FieldSpendViewModel = viewModel(key = "spend-$t-${features.fuel}") { FieldSpendViewModel(data, graph.refreshTriggers("expense", "fuel_event"), fuel = features.fuel) }
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
        is OwnerDestination.Decision -> {
            val kind = DecisionKind.of(route.kind)
            if (kind == DecisionKind.DAILY_REPORT) {
                val vm: com.asseta.owner.ui.accountability.DailyReportReviewViewModel = viewModel(key = "daily-report-$t-${route.id}") {
                    com.asseta.owner.ui.accountability.DailyReportReviewViewModel(data, route.id, graph.refreshTriggers("daily_report"))
                }
                com.asseta.owner.ui.accountability.DailyReportReviewScreen(vm, session, online)
            } else if (kind == null) {
                com.asseta.owner.ui.common.EmptyState(OwnerAccountabilityTexts.NOT_FOUND_TITLE, OwnerAccountabilityTexts.NOT_FOUND_MESSAGE)
            } else {
                val vm: DecisionViewModel = viewModel(key = "decision-$t-${route.kind}-${route.id}") {
                    DecisionViewModel(data, kind, route.id, graph.refreshTriggers(*ACCOUNTABILITY_ENTITIES))
                }
                DecisionScreen(vm, session, online) { setTitle(route, it) }
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
        is OwnerDestination.MachineDays -> {
            val vm: com.asseta.owner.ui.accountability.LedgerDaysViewModel = viewModel(key = "ledger-days-$t-${route.machineId}") {
                com.asseta.owner.ui.accountability.LedgerDaysViewModel(data, route.machineId, graph.refreshTriggers("work_allocation", "meter_capture"))
            }
            com.asseta.owner.ui.accountability.LedgerDaysScreen(vm, open)
        }
        is OwnerDestination.MachineDay -> {
            val vm: com.asseta.owner.ui.accountability.LedgerDayViewModel = viewModel(key = "ledger-day-$t-${route.machineId}-${route.day}") {
                com.asseta.owner.ui.accountability.LedgerDayViewModel(data, route.machineId, route.day, graph.refreshTriggers("work_allocation", "meter_capture"))
            }
            com.asseta.owner.ui.accountability.LedgerDayScreen(vm)
        }
        // The purchase list is replaced by Customers & hours (OwnerFeatures.route sends it there).
        OwnerDestination.CustomerHours -> Unit
        is OwnerDestination.HoursPurchase -> {
            val vm: HoursPurchaseViewModel = viewModel(key = "hours-purchase-$t-${route.purchaseId}") {
                HoursPurchaseViewModel(data, route.purchaseId, graph.refreshTriggers(*HOURS_ENTITIES), features.paymentDetails)
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
            val employee = OwnerDestination.EmployeeAccountability(route.staffId, route.name, from.toString(), to.toString()).takeIf { features.employeeAccountability }
            com.asseta.owner.ui.accountability.ScorecardPersonScreen(vm, features, employee, open)
        }
        OwnerDestination.IdleMachines -> {
            val vm: com.asseta.owner.ui.accountability.IdleMachinesViewModel = viewModel(key = "idle-$t") {
                com.asseta.owner.ui.accountability.IdleMachinesViewModel(data, graph.refreshTriggers("machine_report", "machine"))
            }
            com.asseta.owner.ui.accountability.IdleMachinesScreen(vm, features, open)
        }
        OwnerDestination.CompanyClosure -> {
            val vm: com.asseta.owner.ui.settings.CompanyClosureViewModel = viewModel(key = "closure-$t") {
                com.asseta.owner.ui.settings.CompanyClosureViewModel(data)
            }
            com.asseta.owner.ui.settings.CompanyClosureScreen(vm, online)
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
            AccountabilityScreen(vm, features, com.asseta.core.network.NetworkFactory.defaultWebBaseUrl, open)
        }
        is OwnerDestination.EmployeeAccountability -> {
            val vm: com.asseta.owner.ui.accountability.EmployeeAccountabilityViewModel = viewModel(key = "employee-$t-${route.staffId}") {
                com.asseta.owner.ui.accountability.EmployeeAccountabilityViewModel(data, route.staffId, route.dayFrom, route.dayTo, graph.refreshTriggers(*ACCOUNTABILITY_ENTITIES, "cash_handover", "cash_transfer"))
            }
            com.asseta.owner.ui.accountability.EmployeeAccountabilityScreen(vm, features, com.asseta.core.network.NetworkFactory.defaultWebBaseUrl, open)
        }
        OwnerDestination.Lookup -> {
            val vm: com.asseta.owner.ui.accountability.LookupViewModel = viewModel(key = "lookup-$t") { com.asseta.owner.ui.accountability.LookupViewModel(data) }
            com.asseta.owner.ui.accountability.LookupScreen(vm, features, com.asseta.core.network.NetworkFactory.defaultWebBaseUrl, open)
        }
    }
}
