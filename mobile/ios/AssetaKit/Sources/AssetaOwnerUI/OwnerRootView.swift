#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

enum OwnerTab: Hashable { case overview, fleet, jobs, alerts, more }

/// Lists reachable from the "More" tab.
enum MoreItem: Hashable { case approvals, accountability, exceptions, fieldSpend, cash, investigations, notifications, settings }

/// Owner home for one tenant: tabs, deep links from notification taps, offline/stale state.
public struct OwnerRootView: View {
    @State private var model: OwnerModel
    @State private var tab: OwnerTab = .overview
    @State private var paths: [OwnerTab: NavigationPath] = [:]
    @State private var push = PushCenter.shared
    @Environment(\.scenePhase) private var scenePhase

    public init(context: HomeContext) {
        _model = State(initialValue: OwnerModel(session: context.session, me: context.me, tenant: context.tenant))
    }

    public var body: some View {
        TabView(selection: $tab) {
            if model.features.overview {
                stack(.overview) { OverviewView(model: model, open: open) }
                    .tabItem { Label("Overview", systemImage: "gauge.with.dots.needle.33percent") }.tag(OwnerTab.overview)
            }
            if model.features.fleet {
                stack(.fleet) { FleetView(model: model).modifier(NotificationBell(model: model) { open(.notifications) }) }
                    .tabItem { Label("Fleet", systemImage: "map") }.tag(OwnerTab.fleet)
            }
            if model.features.jobs {
                stack(.jobs) { JobsView(model: model).modifier(NotificationBell(model: model) { open(.notifications) }) }
                    .tabItem { Label("Jobs", systemImage: "list.clipboard") }.tag(OwnerTab.jobs)
            }
            if model.features.fleet {
                stack(.alerts) {
                    AlertsView(model: model, machineID: nil).modifier(NotificationBell(model: model) { open(.notifications) })
                }
                    .tabItem { Label("Alerts", systemImage: "exclamationmark.triangle") }.tag(OwnerTab.alerts)
            }
            stack(.more) { MoreView(model: model).modifier(NotificationBell(model: model) { open(.notifications) }) }
                .tabItem { Label("More", systemImage: "ellipsis.circle") }.tag(OwnerTab.more)
                .badge(OwnerFormat.badge(model.unreadCount).map { Text($0) })
        }
        .tint(Brand.amber)
        .task {
            if !model.features.overview { tab = model.features.fleet ? .fleet : .more }
            await model.start()
            consumePendingLink()
        }
        .onDisappear { model.stop() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { model.foreground() }
            if phase == .background { model.background() }
        }
        .onChange(of: push.pendingLink) { _, _ in consumePendingLink() }
        .alert("Access changed", isPresented: Binding(get: { model.accessLostMessage != nil }, set: { _ in })) {
            Button("OK") { model.leaveTenant() }
        } message: {
            Text(model.accessLostMessage ?? "")
        }
    }

    private func stack(_ tab: OwnerTab, @ViewBuilder root: () -> some View) -> some View {
        NavigationStack(path: Binding(get: { paths[tab] ?? NavigationPath() }, set: { paths[tab] = $0 })) {
            root()
                // Only a tab's first screen has a large title (as on Android); pushed screens use the inline title.
                .navigationDestination(for: OwnerRoute.self) {
                    RouteView(model: model, route: $0).navigationBarTitleDisplayMode(.inline)
                }
                .navigationDestination(for: MoreItem.self) {
                    MoreDestination(model: model, item: $0).navigationBarTitleDisplayMode(.inline)
                }
        }
    }

    /// Opens a route from inside the app (e.g. an overview tile).
    private func open(_ route: OwnerRoute) { navigate(to: route) }

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

    private func navigate(to route: OwnerRoute) {
        var path = NavigationPath()
        let target: OwnerTab
        switch route {
        case .fleet where model.features.fleet: target = .fleet
        case .jobs where model.features.jobs: target = .jobs
        case .investigations:
            target = .more; path.append(MoreItem.investigations)
        case .machine where model.features.fleet: target = .fleet; path.append(route)
        case .alert where model.features.fleet: target = .alerts; path.append(route)
        case .alerts where model.features.fleet: target = .alerts
        case .job where model.features.jobs: target = .jobs; path.append(route)
        case .approval:
            target = .more; path.append(MoreItem.approvals); path.append(route)
        case .approvals:
            target = .more; path.append(MoreItem.approvals)
        case let .decision(kind, _) where model.features.decisionKinds.contains(kind):
            target = .more; path.append(MoreItem.approvals); path.append(route)
        case .accountability where model.features.accountability:
            target = .more; path.append(MoreItem.accountability)
        case .meterReset where model.features.meterEvidence:
            target = .more; path.append(MoreItem.approvals); path.append(route)
        case .handover where model.features.finance:
            target = .more; path.append(MoreItem.approvals); path.append(route)
        case .exception where model.features.meterEvidence:
            target = .more; path.append(MoreItem.exceptions); path.append(route)
        case .exceptions(nil) where model.features.meterEvidence:
            target = .more; path.append(MoreItem.exceptions)
        case .exceptions where model.features.meterEvidence:
            target = .more; path.append(MoreItem.exceptions); path.append(route)
        case .fieldSpend where model.features.expenses:
            target = .more; path.append(MoreItem.fieldSpend)
        case .cash where model.features.finance:
            target = .more; path.append(MoreItem.cash)
        case .cashTransfer where model.features.finance, .cashFloat where model.features.finance,
             .overdueRemittances where model.features.finance:
            target = .more; path.append(MoreItem.cash); path.append(route)
        case .overdueRemittance where model.features.finance:
            target = .more; path.append(MoreItem.cash); path.append(OwnerRoute.overdueRemittances); path.append(route)
        case .investigation:
            target = .more; path.append(MoreItem.investigations); path.append(route)
        case .notification:
            target = .more; path.append(MoreItem.notifications); path.append(route)
        default:
            target = .more; path.append(MoreItem.notifications)
        }
        paths[target] = path
        tab = target
    }
}

/// Destination for every record route.
struct RouteView: View {
    let model: OwnerModel
    let route: OwnerRoute

    var body: some View {
        switch route {
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
        }
    }
}

struct MoreDestination: View {
    let model: OwnerModel
    let item: MoreItem

    var body: some View {
        switch item {
        case .approvals: ApprovalsView(model: model)
        case .accountability: AccountabilityDashboardView(model: model)
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
                if model.features.approvalsScreen {
                    NavigationLink(value: MoreItem.approvals) { Label("Approvals", systemImage: "checkmark.seal") }
                }
                if model.features.accountability {
                    NavigationLink(value: MoreItem.accountability) {
                        Label(OwnerAccountabilityTexts.moreAccountability, systemImage: "checkmark.shield")
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
