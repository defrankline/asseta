#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Lists reachable from the "More" entry.
enum MoreItem: Hashable { case setup, approvals, accountability, findReference, customerHours, scorecard, exceptions, fieldSpend, cash, investigations, notifications, settings }

/// Owner home for one tenant (ADR-008): a sliding side menu over Home, one navigation stack, deep links from notification
/// taps, offline/stale state. The Jobs tab is gone; every other screen stays reachable (side menu, Home tiles, More).
public struct OwnerRootView: View {
    @State private var model: OwnerModel
    @State private var path = NavigationPath()
    @State private var top: AnyHashable?
    @State private var menuOpen = false
    @State private var confirmSignOut = false
    @State private var push = PushCenter.shared
    @Environment(\.scenePhase) private var scenePhase

    public init(context: HomeContext) {
        _model = State(initialValue: OwnerModel(session: context.session, me: context.me, tenant: context.tenant))
    }

    public var body: some View {
        SideDrawer(isOpen: $menuOpen) {
            NavigationStack(path: $path) {
                OwnerHomeView(model: model, openMenu: { menuOpen = true }, push: append)
                    .navigationDestination(for: OwnerScreen.self) { screen($0) }
                    // Pushed screens use the inline title (as on Android).
                    .navigationDestination(for: OwnerRoute.self) {
                        RouteView(model: model, route: $0).navigationBarTitleDisplayMode(.inline)
                    }
                    .navigationDestination(for: MoreItem.self) {
                        MoreDestination(model: model, item: $0).navigationBarTitleDisplayMode(.inline)
                    }
            }
        } menu: {
            OwnerMenu(model: model, current: top, go: go,
                      switchCompany: model.me.tenants.filter({ $0.accessState.allowsEntry }).count > 1
                          ? { menuOpen = false; model.leaveTenant() } : nil,
                      signOut: { menuOpen = false; confirmSignOut = true })
        }
        .tint(Brand.amber)
        .task {
            await model.start()
            consumePendingLink()
        }
        .onDisappear { model.stop() }
        .onChange(of: path.count) { _, count in if count == 0 { top = nil } }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { model.foreground() }
            if phase == .background { model.background() }
        }
        .onChange(of: push.pendingLink) { _, _ in consumePendingLink() }
        .confirmationDialog("Sign out?", isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button("Sign out", role: .destructive) { Task { await model.signOut() } }
        }
        .alert("Access changed", isPresented: Binding(get: { model.accessLostMessage != nil }, set: { _ in })) {
            Button("OK") { model.leaveTenant() }
        } message: {
            Text(model.accessLostMessage ?? "")
        }
    }

    @ViewBuilder private func screen(_ screen: OwnerScreen) -> some View {
        switch screen {
        case .approvals: OwnerApprovalsHubView(model: model, back: pop, push: append)
        case .customers: OwnerCustomersView(model: model, back: pop, push: append)
        case .machines: OwnerMachinesView(model: model, back: pop, push: append)
        case .money: OwnerMoneyView(model: model, back: pop, push: append)
        case .reports: OwnerReportsView(model: model, back: pop)
        case .more: MoreView(model: model).navigationBarTitleDisplayMode(.inline)
        case .settings: SettingsView(model: model).navigationBarTitleDisplayMode(.inline)
        }
    }

    private func pop() { if !path.isEmpty { path.removeLast() } }

    /// Pushes a screen, a record route or a More entry (each has its own destination).
    private func append(_ value: AnyHashable) {
        switch value.base {
        case let screen as OwnerScreen: path.append(screen)
        case let route as OwnerRoute: path.append(route)
        case let item as MoreItem: path.append(item)
        default: break
        }
        if top == nil { top = value }
    }

    /// A side-menu entry: its screen on top of Home (nil = Home).
    private func go(_ value: AnyHashable?) {
        menuOpen = false
        path = NavigationPath()
        top = nil
        if let value { append(value) }
    }

    /// Follows a notification tap. A link for another company switches company first (if this
    /// user may open it); the new home screen then consumes the link.
    private func consumePendingLink() {
        guard let link = push.pendingLink else { return }
        if let tenantID = link.tenantID, tenantID != model.tenant.tenantID {
            if let other = model.me.tenants.first(where: { $0.tenantID == tenantID && $0.accessState.allowsEntry }) {
                model.stop()
                model.session.selectTenant(other)
            } else {
                push.pendingLink = nil
            }
            return
        }
        push.pendingLink = nil
        navigate(to: link.route)
    }

    /// Opens a route under the screen it belongs to (a capability the tenant switched off falls back to its list,
    /// follow-up F1; jobs are gone, so their links open the inbox).
    private func navigate(to link: OwnerRoute) {
        let route = model.features.route(link)
        let f = model.features
        path = NavigationPath()
        top = nil
        switch route {
        case .overview: break
        case .fleet where f.fleet: append(OwnerScreen.machines)
        case .machine where f.fleet, .dailySheet where f.allows(route), .dailySheetDay where f.allows(route):
            append(OwnerScreen.machines); append(route)
        case .machineReport where f.machineReports: append(OwnerScreen.approvals); append(route)
        case .approvals: append(OwnerScreen.approvals)
        case .approval, .meterReset where f.meterEvidence:
            append(OwnerScreen.approvals); append(route)
        case let .decision(kind, _) where f.decisionKinds.contains(kind):
            append(OwnerScreen.approvals); append(route)
        case .handover where f.finance, .customerPayment where f.finance, .pettyCashMovement where f.pettyCashRead,
             .pettyCashAdjustment where f.pettyCashRead, .revenueDifference where f.allows(route), .dailyReport where f.allows(route):
            append(OwnerScreen.approvals); append(route)
        case .customerHours where f.allows(route): append(OwnerScreen.customers)
        case .hoursPurchase where f.allows(route), .hoursStatement where f.allows(route):
            append(OwnerScreen.customers); append(route)
        case .cash where f.finance: append(OwnerScreen.money); append(route)
        case .cashTransfer where f.allows(route), .cashFloat where f.allows(route), .overdueRemittances where f.allows(route),
             .overdueRemittance where f.allows(route):
            append(OwnerScreen.money); append(route)
        case .jobs, .job: append(OwnerRoute.notifications)
        case .setupChecklist where !f.setupRead: break
        default:
            append(f.allows(route) ? route : OwnerRoute.notifications)
        }
    }
}

/// Destination for every record route.
struct RouteView: View {
    let model: OwnerModel
    let route: OwnerRoute

    var body: some View {
        switch route {
        case .overview: OverviewView(model: model, open: { _ in })
        case let .machine(id): MachineDetailView(model: model, machineID: id)
        case let .alert(id): AlertDetailView(model: model, alertID: id)
        case .alerts: AlertsView(model: model, machineID: nil)
        case let .approval(id): ApprovalDetailView(model: model, approvalID: id)
        case .approvals: ApprovalsView(model: model)
        case let .investigation(id): CaseDetailView(model: model, caseID: id)
        case let .job(id): JobDetailView(model: model, jobID: id)
        case let .exceptions(jobID): ExceptionsView(model: model, jobID: jobID)
        case .fieldSpend: FieldSpendView(model: model)
        case .cash: CashView(model: model)
        case let .meterReset(id): MeterResetDetailView(model: model, resetID: id)
        case let .handover(id): HandoverDetailView(model: model, handoverID: id)
        case let .customerPayment(id): PaymentReviewView(model: model, paymentID: id)
        case let .pettyCashMovement(id): PettyCashReviewView(model: model, id: id, adjustment: false)
        case let .pettyCashAdjustment(id): PettyCashReviewView(model: model, id: id, adjustment: true)
        case let .exception(id): ExceptionDetailView(model: model, exceptionID: id)
        case let .notification(id): NotificationResolverView(model: model, notificationID: id)
        case .notifications: NotificationsView(model: model)
        case .fleet: FleetView(model: model)
        case .jobs: JobsView(model: model)
        case .investigations: CasesView(model: model)
        case let .decision(kind, id): DecisionDetailView(model: model, kind: kind, recordID: id)
        case .accountability: AccountabilityDashboardView(model: model)
        case let .cashTransfer(id): CashTransferRecordView(model: model, transferID: id)
        case let .cashFloat(id): CashFloatRecordView(model: model, floatID: id)
        case .overdueRemittances: OverdueRemittancesView(model: model)
        case let .overdueRemittance(id): OverdueRemittanceView(model: model, overdueID: id)
        case let .revenueDifference(id): RevenueDifferenceView(model: model, differenceID: id)
        // With revenue checks off (or not readable) a machine's days show the allocations alone (DEC-032).
        case let .dailySheet(machine) where !model.features.revenueRead: LedgerDaysView(model: model, machineID: machine)
        case let .dailySheetDay(machine, day) where !model.features.revenueRead: LedgerDayView(model: model, machineID: machine, day: day)
        case let .dailySheet(machine): DailySheetView(model: model, machineID: machine)
        case let .dailySheetDay(machine, day): DailySheetDayView(model: model, machineID: machine, day: day)
        case let .hoursPurchase(id): HoursPurchaseView(model: model, purchaseID: id)
        case .customerHours: CustomerHoursView(model: model)
        case let .hoursStatement(customer, name): HoursStatementView(model: model, customerID: customer, customerName: name)
        case .scorecard: ScorecardView(model: model)
        case let .scorecardPerson(id, name, from, to): ScorecardPersonView(model: model, staffID: id, name: name, from: from, to: to)
        case .unbilledWork: UnbilledWorkView(model: model)
        case .idleMachines: IdleMachinesView(model: model)
        case .setupChecklist: SetupChecklistView(model: model)
        case let .dailyReport(id): DailyReportReviewView(model: model, reportID: id)
        case let .employeeAccountability(id, name, from, to):
            EmployeeAccountabilityView(model: model, staffID: id, name: name, from: from, to: to)
        case let .machineReport(id): OwnerReportApprovalView(model: model, reportID: id)
        }
    }
}

struct MoreDestination: View {
    let model: OwnerModel
    let item: MoreItem

    var body: some View {
        switch item {
        case .setup: SetupChecklistView(model: model)
        case .approvals: ApprovalsView(model: model)
        case .accountability: AccountabilityDashboardView(model: model)
        case .findReference: FindReferenceView(model: model)
        case .customerHours: CustomerHoursView(model: model)
        case .scorecard: ScorecardView(model: model)
        case .exceptions: ExceptionsView(model: model, jobID: nil)
        case .fieldSpend: FieldSpendView(model: model)
        case .cash: CashView(model: model)
        case .investigations: CasesView(model: model)
        case .notifications: NotificationsView(model: model)
        case .settings: SettingsView(model: model)
        }
    }
}

struct MoreView: View {
    let model: OwnerModel

    var body: some View {
        List {
            Section {
                if model.features.setupRead {
                    NavigationLink(value: MoreItem.setup) { Label(SetupTexts.more, systemImage: "checklist") }
                }
                if model.features.approvalsScreen {
                    NavigationLink(value: MoreItem.approvals) { Label("Approvals", systemImage: "checkmark.seal") }
                }
                if model.features.accountability {
                    NavigationLink(value: MoreItem.accountability) {
                        Label(OwnerAccountabilityTexts.moreAccountability, systemImage: "checkmark.shield")
                    }
                }
                if model.features.lookup {
                    NavigationLink(value: MoreItem.findReference) { Label(ManagementTexts.lookupMore, systemImage: "magnifyingglass") }
                }
                if model.features.hoursRead {
                    NavigationLink(value: MoreItem.customerHours) {
                        Label(CustomerHoursTexts.more, systemImage: "hourglass")
                    }
                }
                if model.features.scorecard {
                    NavigationLink(value: MoreItem.scorecard) {
                        Label(OversightTexts.scoreMore, systemImage: "person.text.rectangle")
                    }
                }
                if model.features.meterEvidence {
                    NavigationLink(value: MoreItem.exceptions) {
                        Label(ExceptionText.title, systemImage: "exclamationmark.triangle")
                    }
                }
                if model.features.expenses {
                    NavigationLink(value: MoreItem.fieldSpend) { Label(SpendText.title, systemImage: "receipt") }
                }
                if model.features.finance {
                    NavigationLink(value: MoreItem.cash) { Label(CashText.title, systemImage: "banknote") }
                }
                if model.features.cases {
                    NavigationLink(value: MoreItem.investigations) {
                        Label("Investigations", systemImage: "doc.text.magnifyingglass")
                    }
                }
                if model.features.notifications {
                    NavigationLink(value: MoreItem.notifications) {
                        Label("Notifications", systemImage: "bell")
                            .badge(OwnerFormat.badge(model.unreadCount).map { Text($0) })
                    }
                }
            }
            Section {
                NavigationLink(value: MoreItem.settings) { Label("Settings", systemImage: "gearshape") }
            }
            Section("Company") {
                LabeledContent("Name", value: model.tenant.name)
                if model.isReadOnlyTenant {
                    Text("This company is read-only. Viewing only.").font(.footnote).foregroundStyle(.secondary)
                }
                if model.me.tenants.filter({ $0.accessState.allowsEntry }).count > 1 {
                    Button("Switch company") { model.leaveTenant() }
                }
            }
        }
        .navigationTitle("More")
    }
}
#endif
