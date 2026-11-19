#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

private typealias T = MachineReportTexts

/// In-app destinations pushed on the shell's navigation stack (same screens as the Android routes).
enum FieldRoute: Hashable {
    // ADR-008 shell
    case sellHours, report(UUID?), money, dashboard, inbox, moneyRecords, myReports, mySales, fuelList, settings
    /// One of my machine reports (read-only detail).
    case myReport(UUID)
    case reading(UUID), machine(UUID), resetDetail(UUID), fuel(UUID), expense(UUID)
    case cash(UUID, collection: Bool), notification(UUID), syncStatus
    /// A request to keep cash (client id or server id).
    case retention(UUID)
    /// An overdue-remittance flag of mine (read online).
    case remittanceOverdue(UUID)
    /// My petty cash funds and what waits for me (DEC-033).
    case pettyCash
    /// Customers (online) and one customer (add / edit its details).
    case customers, customer(UUID)
    /// Customers' usable hours, offline (Dashboard).
    case customerBalances
}

/// Forms presented as sheets (Cancel / Save), as before.
enum FieldSheet: Identifiable {
    case expense(ExpensePolicySnapshot), collection, handover, fuel, reset(machineID: UUID, oldReading: String?)
    // Accountability (each gated by server capability, permission and tenant policy)
    case hoursTransfer, cashTransfer, retention, cashAck(UUID, isFloat: Bool)
    case capture(CaptureTarget, MeterPolicySnapshot)
    /// A petty cash form (DEC-033).
    case pettyCash(PettyCashSheet)
    /// A payment on an open credit invoice, chosen in the form (ADR-008).
    case invoicePayment(UUID?)
    /// "Delete my account" (Settings).
    case deleteAccount

    var id: String {
        switch self {
        case .expense: "expense"
        case .collection: "collection"
        case .handover: "handover"
        case .fuel: "fuel"
        case let .reset(machine, _): "reset-\(machine)"
        case .hoursTransfer: "hours-transfer"
        case .cashTransfer: "cash-transfer"
        case .retention: "retention"
        case let .cashAck(id, _): "cash-ack-\(id)"
        case let .capture(target, _): "capture-\(target.title)-\(target.machineID?.uuidString ?? "")"
        case let .pettyCash(form): form.id
        case let .invoicePayment(id): "invoice-payment-\(id?.uuidString ?? "")"
        case .deleteAccount: "delete-account"
        }
    }
}

/// Supervisor app (ADR-008): a sliding side menu over Home (summary, Sell hours, Machine report, Money, Dashboard tiles
/// and Recent), one navigation stack for every screen, sync status in the header (same as Android `SupervisorHome`).
public struct FieldRootView: View {
    @State private var model: FieldModel
    @Environment(\.scenePhase) private var scenePhase
    @State private var confirmSignOut = false
    @State private var menuOpen = false
    @State private var path: [FieldRoute] = []
    @State private var sheet: FieldSheet?
    @State private var blockedExpense: String?
    @State private var blockedCapture: String?
    private let push = SupervisorPush.shared
    private let showsSwitchCompany: Bool
    private let userName: String

    public init(context: HomeContext) {
        _model = State(initialValue: FieldModel(session: context.session, tenant: context.tenant))
        showsSwitchCompany = context.me.tenants.count > 1
        userName = context.me.displayName
    }

    /// Convenience for `AssetaAppScene(home:)`.
    public static let home: HomeBuilder = { AnyView(FieldRootView(context: $0)) }

    public var body: some View {
        Group {
            switch model.phase {
            case .loading:
                ProgressView("Opening your work…").frame(maxWidth: .infinity, maxHeight: .infinity)
            case let .failed(message):
                ContentUnavailableView("Can't open local data", systemImage: "externaldrive.badge.exclamationmark",
                                       description: Text(message))
            case .ready:
                shell
            }
        }
        .task { await model.start() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await model.sync(force: true); await push.refresh() } }
            if phase == .background { BackgroundSync.schedule() }
        }
        .onChange(of: path) { _, new in if new.last == .inbox { Task { await push.inboxShown() } } }
        .onChange(of: model.phase, initial: true) { openPushedNotification() }
        .onChange(of: push.pendingTap) { openPushedNotification() }
        .onChange(of: push.arrivals) { Task { await model.refreshNotifications() } }
        .confirmationDialog("Sign out?", isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button("Sign out", role: .destructive) { Task { await model.signOut() } }
        } message: {
            Text(signOutMessage)
        }
        .sheet(item: $sheet) { sheet in
            switch sheet {
            case let .expense(snapshot): ExpenseFormView(model: model, snapshot: snapshot)
            case .collection: CashCollectionFormView(model: model)
            case .handover: CashHandoverFormView(model: model)
            case .fuel: FuelFormView(model: model)
            case let .reset(machineID, oldReading): ResetRequestFormView(model: model, machineID: machineID, oldReading: oldReading)
            case .hoursTransfer: HoursTransferFormView(model: model)
            case .cashTransfer: CashTransferFormView(model: model)
            case .retention: RetentionFormView(model: model) { id in open(.retention(id), under: .money) }
            case let .cashAck(id, isFloat): CashAckFormView(model: model, targetID: id, isFloat: isFloat)
            case let .capture(target, snapshot): MeterCaptureView(model: model, target: target, snapshot: snapshot)
            case let .pettyCash(form): form.view(model)
            case let .invoicePayment(id): InvoicePaymentFormView(model: model, invoiceID: id)
            case .deleteAccount:
                NavigationStack {
                    AccountDeletionView(session: model.session, isOnline: model.isOnline)
                        .toolbar {
                            ToolbarItem(placement: .cancellationAction) { Button("Cancel") { self.sheet = nil } }
                        }
                }
            }
        }
        .alert("Can't record now", isPresented: Binding(get: { blockedCapture != nil },
                                                       set: { if !$0 { blockedCapture = nil } })) {
            Button("OK") { blockedCapture = nil }
        } message: { Text(blockedCapture ?? "") }
        .alert("Can't record an expense now", isPresented: Binding(get: { blockedExpense != nil },
                                                                 set: { if !$0 { blockedExpense = nil } })) {
            Button("OK") { blockedExpense = nil }
        } message: { Text(blockedExpense ?? "") }
    }

    private var shell: some View {
        SideDrawer(isOpen: $menuOpen) {
            NavigationStack(path: $path) {
                SupervisorHomeView(model: model, userName: userName, openMenu: { menuOpen = true }, open: open)
                    .navigationDestination(for: FieldRoute.self) { route in
                        destination(route).navigationBarTitleDisplayMode(.inline)
                    }
            }
            .tint(Shell.accent)
        } menu: {
            SupervisorMenu(model: model, userName: userName, current: path.first, showsSwitchCompany: showsSwitchCompany,
                           go: go, switchCompany: { model.stop(); model.session.clearTenantSelection() },
                           signOut: { menuOpen = false; requestSignOut() })
        }
    }

    /// A side-menu entry: its screen on top of Home (nil = Home).
    private func go(_ route: FieldRoute?) {
        menuOpen = false
        path = route.map { [$0] } ?? []
    }

    /// Pushes a screen.
    func open(_ route: FieldRoute) { path.append(route) }

    /// Shows `route` with `parent` underneath (e.g. a cash record on Money).
    private func open(_ route: FieldRoute, under parent: FieldRoute) { path = [parent, route] }

    private func pop() { if !path.isEmpty { path.removeLast() } }

    @ViewBuilder private func destination(_ route: FieldRoute) -> some View {
        switch route {
        case .sellHours: SellHoursView(model: model, close: pop)
        case let .report(machineID):
            if model.access.machineReport {
                MachineReportFlow(model: model, machineID: machineID ?? defaultReportMachine, close: pop,
                                  openMachine: { open(.machine($0)) })
            } else {
                ContentUnavailableView(T.title, systemImage: "gauge", description: Text(FieldAccountabilityTexts.serverTooOld))
            }
        case .money:
            MoneyView(model: model, back: pop, open: open, sheet: { sheet = $0 }, recordExpense: recordExpense)
        case .dashboard: DashboardView(model: model, back: pop, open: open)
        case .inbox:
            InboxTabView(model: model, open: openNotification, attention: openAttention).navigationTitle(T.menuInbox)
                .toolbar { syncToolbar }
        case .moneyRecords:
            MoneyTabView(model: model, acknowledge: { sheet = .cashAck($0, isFloat: $1) }).navigationTitle(T.dashMyCash)
                .toolbar { moneyToolbar }
        case .myReports: MyReportsView(model: model, open: open)
        case let .myReport(id): MachineReportDetailView(model: model, reportID: id)
        case .mySales: MySalesView(model: model)
        case .fuelList:
            FuelTabView(model: model).navigationTitle(T.menuFuel)
                .toolbar {
                    if model.canRecordExpenses {
                        Button("Record fuel event", systemImage: "plus") { sheet = .fuel }.accessibilityIdentifier("fuel.add")
                    }
                }
        case .settings:
            SupervisorSettingsView(model: model, deleteAccount: { sheet = .deleteAccount }, signOut: { requestSignOut() })
        case let .reading(id): ReadingDetailView(model: model, id: id, requestReset: requestReset, capture: capture)
        case let .machine(id):
            MachineDetailView(model: model, machineID: id, requestReset: requestReset, capture: capture)
        case let .resetDetail(id): ResetDetailView(model: model, id: id)
        case let .fuel(id): FuelDetailView(model: model, id: id)
        case let .expense(id): ExpenseDetailView(model: model, id: id, recordExpense: recordExpense)
        case let .cash(id, collection): CashDetailView(model: model, id: id, collection: collection, record: { sheet = $0 })
        case let .notification(id): NotificationDetailView(notification: model.notifications.first { $0.id == id })
        case .syncStatus: SyncStatusView(model: model)
        case let .retention(id): RetentionStatusView(model: model, id: id)
        case let .remittanceOverdue(id): RemittanceOverdueView(model: model, id: id)
        case .pettyCash: MyPettyCashView(model: model, sheet: pettyCashSheet)
        case .customers: CustomersListView(model: model)
        case let .customer(id): CustomerDetailView(model: model, customerID: id)
        case .customerBalances: CustomerBalancesView(model: model)
        }
    }

    /// The machine a report opens on: the first one that needs a report, else the only one.
    private var defaultReportMachine: UUID? {
        let rows = model.machineStandings
        return rows.first { $0.standing.needsReport }?.state.machineID ?? (rows.count == 1 ? rows.first?.state.machineID : nil)
    }

    @ToolbarContentBuilder private var syncToolbar: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            NavigationLink(value: FieldRoute.syncStatus) { SyncBadge(model: model) }.accessibilityIdentifier("sync.status")
        }
    }

    /// The record actions of the money lists (as the Money tab's + menu before).
    @ToolbarContentBuilder private var moneyToolbar: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            let a = model.access
            Menu {
                if model.canRecordExpenses { Button("Record expense", systemImage: "doc.text.viewfinder") { recordExpense() } }
                if model.canRecordCash {
                    Button(T.moneyCollect, systemImage: "banknote") { sheet = .collection }
                    Button("Hand over cash", systemImage: "arrow.up.forward.circle") { sheet = .handover }
                }
                if a.transferCash {
                    Button(FieldAccountabilityTexts.menuTransferCash, systemImage: "arrow.left.arrow.right") { sheet = .cashTransfer }
                }
                if a.askToKeepCash {
                    Button(FieldAccountabilityTexts.menuAskToKeepCash, systemImage: "hand.raised") { sheet = .retention }
                }
                if a.requestHoursTransfer {
                    Button(FieldAccountabilityTexts.menuRequestHoursTransfer, systemImage: "arrow.triangle.swap") { sheet = .hoursTransfer }
                }
            } label: { Image(systemName: "plus") }
            .accessibilityLabel("Record").accessibilityIdentifier("money.add")
        }
    }

    /// The petty cash forms share the root's sheet.
    private var pettyCashSheet: Binding<PettyCashSheet?> {
        Binding(get: { if case let .pettyCash(form)? = sheet { form } else { nil } },
                set: { sheet = $0.map(FieldSheet.pettyCash) })
    }

    private func recordExpense() {
        switch model.expenseGate() {
        case let .allowed(snapshot): sheet = .expense(snapshot)
        case let .blocked(reason): blockedExpense = reason.expenseMessage
        }
    }

    private func requestReset(_ machineID: UUID, _ oldReading: String?) { sheet = .reset(machineID: machineID, oldReading: oldReading) }

    /// A daily reading, baseline or correction: the capture screen under the machine's capture rules.
    private func capture(_ target: CaptureTarget) {
        guard let machineID = target.machineID else { return }
        switch model.gate(machineID: machineID) {
        case let .allowed(snapshot): sheet = .capture(target, snapshot)
        case let .blocked(reason): blockedCapture = reason.message
        }
    }

    /// Opens what a notification is about (marking it read), or its own detail when it points nowhere on the phone.
    private func openNotification(_ notification: NotificationDTO) {
        Task { await model.markRead(notification) }
        follow(InboxLink.from(notification), notificationID: notification.id)
    }

    /// Opens a notification's subject; `notificationID` is the fallback detail (nil: the Inbox list).
    private func follow(_ link: InboxLink, notificationID: UUID?) {
        func fallback() { if let notificationID { open(.notification(notificationID)) } }
        switch link {
        case let .expense(id): open(.expense(model.inbox.expenses.first { $0.serverID == id }?.id ?? id))
        case .money: open(.money)
        case let .machine(id):
            if model.inbox.machines[id] != nil { open(.machine(id)) } else { fallback() }
        case let .cashToAcknowledge(id, isFloat):
            // The answer screen while it still waits for me, else Money.
            open(.money)
            let waiting = model.accountabilityData?.toAcknowledge(myStaffID: model.myStaffID)
            let pending = isFloat ? waiting?.floats.contains { $0.id == id } : waiting?.transfers.contains { $0.id == id }
            if pending == true && model.access.acknowledgeCash { sheet = .cashAck(id, isFloat: isFloat) }
        // CASH_CUSTODY switched off: its records are hidden, so their taps open Money (follow-up F1).
        case let .retention(id):
            if model.access.cashCustodyOn { open(.retention(id), under: .money) } else { open(.money) }
        case let .handover(id):
            // On the phone: its detail; not yet synced here: Money.
            if model.inbox.handovers.contains(where: { $0.id == id }) { open(.cash(id, collection: false), under: .money) } else { open(.money) }
        case let .remittanceOverdue(id):
            // Read online first: a flag the server does not show me (404), offline or switched off opens Money.
            guard model.access.cashCustodyOn else { open(.money); return }
            Task {
                if await model.remittanceOverdue(id) != nil { open(.remittanceOverdue(id), under: .money) } else { open(.money) }
            }
        // DEC-033: the form while the item still waits for me on this phone, else My petty cash.
        case let .pettyCashMovement(id):
            guard model.access.pettyCash else { fallback(); return }
            open(.pettyCash, under: .money)
            if model.pettyCash.waiting.contains(where: { $0.id == id }) { sheet = .pettyCash(.ack(id)) }
        case let .pettyCashHolderChange(id):
            guard model.access.pettyCash else { fallback(); return }
            open(.pettyCash, under: .money)
            if model.pettyCash.waiting.contains(where: { $0.id == id }) { sheet = .pettyCash(.holderChange(id)) }
        case .pettyCash:
            if model.access.pettyCash { open(.pettyCash, under: .money) } else { fallback() }
        case .none: fallback()
        }
    }

    /// A tapped push: the Inbox, then that notification's detail when the Inbox has it.
    private func openPushedNotification() {
        guard model.phase == .ready, let tap = push.pendingTap else { return }
        push.pendingTap = nil
        path = [.inbox]
        Task {
            await model.refreshNotifications()
            guard let id = tap.notificationID, let notification = model.notifications.first(where: { $0.id == id }) else {
                // Not in the Inbox (yet): the exact record the push names, when the app shows that kind.
                if let record = tap.record, let link = InboxLink.from(record: record) { follow(link, notificationID: nil) }
                return
            }
            // Exactly what tapping that notification in the Inbox does (its subject, else its detail).
            openNotification(notification)
        }
    }

    private func openAttention(_ item: AttentionItem) {
        switch item.kind {
        case .reading: open(.reading(item.refID))
        case .reset: open(.resetDetail(item.refID))
        case .expense: open(.expense(item.refID))
        case .fuel: if model.access.fuelOn { open(.fuel(item.refID)) }
        case .collection: open(.cash(item.refID, collection: true))
        case .handover: open(.cash(item.refID, collection: false))
        case .upload: open(.syncStatus)
        }
    }

    private var signOutMessage: String {
        "\(model.overview?.unsyncedCount ?? 0) item(s) are not synced yet. They stay encrypted on this phone and sync after you "
            + "sign in again."
    }

    /// Asks first only when work has not reached the office yet; otherwise signs out straight away.
    private func requestSignOut() {
        if (model.overview?.unsyncedCount ?? 0) > 0 { confirmSignOut = true } else { Task { await model.signOut() } }
    }
}

/// The side menu (design SideNav): Home, Sell hours, Machine report, Money, Dashboard, Inbox, Customers (and Fuel while the
/// company uses it); sync status, switch company, settings, sign out.
struct SupervisorMenu: View {
    let model: FieldModel
    let userName: String
    let current: FieldRoute?
    let showsSwitchCompany: Bool
    let go: (FieldRoute?) -> Void
    let switchCompany: () -> Void
    let signOut: () -> Void

    var body: some View {
        let a = model.access
        let badge = InboxTexts.inboxBadge(unread: model.unreadNotifications, attention: model.inbox.attention.count)
        VStack(alignment: .leading, spacing: 0) {
            DrawerHeader(name: userName, detail: "\(T.roleSupervisor) · \(model.tenant.name)")
            Divider().overlay(Shell.border)
            ScrollView {
                VStack(spacing: 4) {
                    DrawerRow(T.menuHome, systemImage: "house", selected: current == nil) { go(nil) }
                    if a.sellHours {
                        DrawerRow(T.tileSellHours, systemImage: "clock", selected: current == .sellHours) { go(.sellHours) }
                    }
                    if a.machineReport {
                        DrawerRow(T.tileReport, systemImage: "gauge.with.needle", selected: isReport,
                                  badge: SupervisorFigures.badge(model.reportsDue)) { go(.report(nil)) }
                    }
                    DrawerRow(T.tileMoney, systemImage: "banknote", selected: current == .money) { go(.money) }
                    // Fuel while FUEL is on and the user records expenses (never shown, then hidden).
                    if a.fuelMenu {
                        DrawerRow(T.menuFuel, systemImage: "fuelpump", selected: current == .fuelList) { go(.fuelList) }
                    }
                    DrawerRow(T.tileDashboard, systemImage: "chart.bar", selected: current == .dashboard) { go(.dashboard) }
                    DrawerRow(T.menuInbox, systemImage: "envelope", selected: current == .inbox,
                              badge: badge > 0 ? (badge > 99 ? "99+" : "\(badge)") : nil, redBadge: true) { go(.inbox) }
                    DrawerRow(T.menuCustomers, systemImage: "person.badge.plus", selected: current == .customers) { go(.customers) }
                }
                .padding(.top, 14)
            }
            Divider().overlay(Shell.border)
            VStack(spacing: 4) {
                DrawerRow(syncLine, systemImage: syncIcon, small: true, iconColor: syncWaiting ? Shell.warnText : Shell.check) {
                    go(.syncStatus)
                }
                if showsSwitchCompany {
                    DrawerRow(T.menuSwitchCompany, systemImage: "arrow.left.arrow.right.square", small: true, action: switchCompany)
                }
                DrawerRow(T.menuSettings, systemImage: "gearshape", small: true) { go(.settings) }
                DrawerRow(T.menuSignOut, systemImage: "rectangle.portrait.and.arrow.right", small: true, action: signOut)
                Text(T.menuFooter("Asseta Supervisor \(FieldServices.appVersion)"))
                    .font(.system(size: 12)).foregroundStyle(Shell.faint).padding(.horizontal, 12).padding(.top, 6)
            }
            .padding(.top, 12)
        }
        .padding(.horizontal, 16).padding(.top, 56).padding(.bottom, 24)
    }

    private var isReport: Bool { if case .report = current { true } else { false } }
    private var unsynced: Int { model.overview?.unsyncedCount ?? 0 }
    private var syncWaiting: Bool { unsynced > 0 }
    private var syncIcon: String { syncWaiting ? "arrow.triangle.2.circlepath" : "checkmark" }
    private var syncLine: String {
        syncWaiting ? T.menuSyncWaiting(unsynced) : SupervisorShellTexts.menuSyncAllSent
    }
}

/// Settings (as Android): notifications on this phone, change password, delete my account, sign out; the version below.
struct SupervisorSettingsView: View {
    let model: FieldModel
    let deleteAccount: () -> Void
    let signOut: () -> Void
    private let push = SupervisorPush.shared

    var body: some View {
        List {
            if model.canReadNotifications {
                Section(PushStatus.title) {
                    Text(push.status.text)
                    if push.status.canTurnOn { Button(PushStatus.turnOn) { Task { await push.turnOn() } } }
                }
            }
            Section {
                ChangePasswordButton(session: model.session, isOnline: model.isOnline, showsFooter: true)
                Button(AccountDeletionText.action, role: .destructive, action: deleteAccount).accessibilityIdentifier("account.delete")
                Button(T.menuSignOut, action: signOut).accessibilityIdentifier("settings.signOut")
            } footer: {
                Text(SupervisorShellTexts.version(FieldServices.appVersion)).padding(.top, 12)
            }
        }
        .navigationTitle(T.menuSettings)
    }
}

struct SyncBadge: View {
    let model: FieldModel

    var body: some View {
        let unsynced = model.overview?.unsyncedCount ?? 0
        let attention = (model.overview?.counts[.failed] ?? 0) + (model.overview?.counts[.conflict] ?? 0)
        HStack(spacing: 4) {
            if model.isSyncing {
                ProgressView()
            } else {
                Image(systemName: attention > 0 ? "exclamationmark.arrow.triangle.2.circlepath"
                      : unsynced > 0 ? "arrow.triangle.2.circlepath" : "checkmark.icloud")
            }
            if unsynced > 0 { Text("\(unsynced)").font(.caption.bold()) }
        }
        .foregroundStyle(attention > 0 ? Palette.offline : Color.accentColor)
        .accessibilityLabel(unsynced == 0 ? "All synced" : "\(unsynced) items not synced")
    }
}

/// Warnings shown on Home: clock tamper, server skew, offline state.
struct FieldBanners: View {
    let model: FieldModel

    var body: some View {
        if case let .tamperSuspected(deviation) = model.clockStatus {
            Banner(icon: "clock.badge.exclamationmark", color: Palette.warning,
                   text: "This phone's clock is \(Self.describe(deviation)) compared with Asseta's server. Set the date and time to automatic. Readings still record the phone's own time.")
                .accessibilityIdentifier("banner.clock")
        } else if model.overview?.serverClockSkewAlert == true {
            Banner(icon: "clock.badge.exclamationmark", color: Palette.warning,
                   text: "The server reported that this phone's clock is wrong. Set the date and time to automatic.")
        }
        if !model.isOnline {
            Banner(icon: "wifi.slash", color: .secondary,
                   text: "Offline. You can keep working; everything is saved on this phone and syncs when you are back online.")
        } else if case let .offline(message)? = model.lastOutcome {
            Banner(icon: "wifi.exclamationmark", color: .secondary, text: "Sync failed: \(message). It will retry automatically.")
        } else if case let .serverUnavailable(message)? = model.lastOutcome {
            Banner(icon: "exclamationmark.icloud", color: .secondary, text: "Server problem: \(message). It will retry automatically.")
        }
    }

    static func describe(_ seconds: Double) -> String {
        let minutes = Int(abs(seconds) / 60)
        let amount = minutes >= 120 ? "\(minutes / 60) hours" : "\(minutes) minutes"
        return seconds > 0 ? "\(amount) fast" : "\(amount) slow"
    }
}

struct Banner: View {
    let icon: String
    let color: Color
    let text: String

    var body: some View {
        Label { Text(text).font(.footnote) } icon: { Image(systemName: icon).foregroundStyle(color) }
    }
}
#endif
