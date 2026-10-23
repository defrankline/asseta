#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

/// In-app destinations pushed on a tab's navigation stack (same screens as the Android routes).
enum FieldRoute: Hashable {
    case job(UUID), reading(UUID), machine(UUID), resetDetail(UUID), fuel(UUID), expense(UUID)
    case cash(UUID, collection: Bool), notification(UUID), syncStatus
}

/// Forms presented as sheets (Cancel / Save), as before.
enum FieldSheet: Identifiable {
    case expense(ExpensePolicySnapshot), collection, handover, fuel, reset(machineID: UUID, oldReading: String?)

    var id: String {
        switch self {
        case .expense: "expense"
        case .collection: "collection"
        case .handover: "handover"
        case .fuel: "fuel"
        case let .reset(machine, _): "reset-\(machine)"
        }
    }
}

/// Supervisor app: bottom tabs Jobs · Readings · Fuel · Money · Inbox, each with its own navigation
/// stack, the account menu and the sync badge in the header (same as Android `SupervisorHome`).
public struct FieldRootView: View {
    @State private var model: FieldModel
    @Environment(\.scenePhase) private var scenePhase
    @State private var confirmSignOut = false
    @State private var tab: SupervisorTab = .jobs
    @State private var paths: [SupervisorTab: [FieldRoute]] = [:]
    @State private var sheet: FieldSheet?
    @State private var blockedExpense: String?
    private let showsSwitchCompany: Bool

    public init(context: HomeContext) {
        _model = State(initialValue: FieldModel(session: context.session, tenant: context.tenant))
        showsSwitchCompany = context.me.tenants.count > 1
    }

    /// Convenience for `AssetaAppScene(home:)`.
    public static let home: HomeBuilder = { AnyView(FieldRootView(context: $0)) }

    public var body: some View {
        Group {
            switch model.phase {
            case .loading:
                ProgressView("Opening your jobs…").frame(maxWidth: .infinity, maxHeight: .infinity)
            case let .failed(message):
                ContentUnavailableView("Can't open local data", systemImage: "externaldrive.badge.exclamationmark",
                                       description: Text(message))
            case .ready:
                tabs
            }
        }
        .task { await model.start() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await model.sync(force: true) } }
            if phase == .background { BackgroundSync.schedule() }
        }
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
            }
        }
        .alert("Can't record an expense now", isPresented: Binding(get: { blockedExpense != nil },
                                                                 set: { if !$0 { blockedExpense = nil } })) {
            Button("OK") { blockedExpense = nil }
        } message: { Text(blockedExpense ?? "") }
    }

    private var tabs: some View {
        let badge = InboxTexts.inboxBadge(unread: model.unreadNotifications, attention: model.inbox.attention.count)
        return TabView(selection: tabSelection) {
            ForEach(SupervisorTab.allCases, id: \.self) { item in
                NavigationStack(path: path(item)) {
                    root(item)
                        .toolbar { toolbar(item) }
                        .navigationDestination(for: FieldRoute.self) { route in
                            destination(route).navigationBarTitleDisplayMode(.inline)
                        }
                }
                .tabItem { Label(item.label, systemImage: Self.icon(item)) }
                .badge(item == .inbox && badge > 0 ? Text(badge > 99 ? "99+" : "\(badge)") : nil)
                .tag(item)
            }
        }
    }

    /// Selecting the current tab again returns to its first screen (as on Android).
    private var tabSelection: Binding<SupervisorTab> {
        Binding(get: { tab }, set: { new in
            if new == tab { paths[new] = [] }
            tab = new
        })
    }

    private func path(_ item: SupervisorTab) -> Binding<[FieldRoute]> {
        Binding(get: { paths[item] ?? [] }, set: { paths[item] = $0 })
    }

    /// Pushes a screen on the current tab's stack.
    func open(_ route: FieldRoute) { paths[tab, default: []].append(route) }

    @ViewBuilder private func root(_ item: SupervisorTab) -> some View {
        switch item {
        case .jobs: JobsTabView(model: model, open: open).navigationTitle(model.tenant.name)
        case .readings: ReadingsTabView(model: model).navigationTitle("Readings")
        case .fuel: FuelTabView(model: model).navigationTitle("Fuel")
        case .money: MoneyTabView(model: model).navigationTitle("Money")
        case .inbox: InboxTabView(model: model, open: openNotification, attention: openAttention).navigationTitle("Inbox")
        }
    }

    @ViewBuilder private func destination(_ route: FieldRoute) -> some View {
        switch route {
        case let .job(id): JobDetailView(model: model, jobID: id)
        case let .reading(id): ReadingDetailView(model: model, id: id, requestReset: requestReset)
        case let .machine(id): MachineDetailView(model: model, machineID: id, requestReset: requestReset)
        case let .resetDetail(id): ResetDetailView(model: model, id: id)
        case let .fuel(id): FuelDetailView(model: model, id: id)
        case let .expense(id): ExpenseDetailView(model: model, id: id, recordExpense: recordExpense)
        case let .cash(id, collection): CashDetailView(model: model, id: id, collection: collection, record: { sheet = $0 })
        case let .notification(id): NotificationDetailView(notification: model.notifications.first { $0.id == id })
        case .syncStatus: SyncStatusView(model: model)
        }
    }

    @ToolbarContentBuilder private func toolbar(_ item: SupervisorTab) -> some ToolbarContent {
        ToolbarItemGroup(placement: .topBarTrailing) {
            switch item {
            case .fuel:
                if model.canRecordExpenses {
                    Button("Record fuel event", systemImage: "plus") { sheet = .fuel }.accessibilityIdentifier("fuel.add")
                }
            case .money:
                if model.canRecordExpenses || model.canRecordCash {
                    Menu {
                        if model.canRecordExpenses { Button("Record expense", systemImage: "doc.text.viewfinder") { recordExpense() } }
                        if model.canRecordCash {
                            Button("Record cash collection", systemImage: "banknote") { sheet = .collection }
                            Button("Hand over cash", systemImage: "arrow.up.forward.circle") { sheet = .handover }
                        }
                    } label: { Image(systemName: "plus") }
                    .accessibilityLabel("Record").accessibilityIdentifier("money.add")
                }
            default: EmptyView()
            }
            NavigationLink(value: FieldRoute.syncStatus) { SyncBadge(model: model) }
                .accessibilityIdentifier("sync.status")
        }
        ToolbarItem(placement: .topBarLeading) {
            Menu {
                if showsSwitchCompany { Button("Switch company") { model.stop(); model.session.clearTenantSelection() } }
                ChangePasswordButton(session: model.session, isOnline: model.isOnline, showsFooter: true)
                Button("Sign out", role: .destructive) { confirmSignOut = true }
            } label: { Image(systemName: "person.crop.circle") }
        }
    }

    private func recordExpense() {
        switch model.expenseGate() {
        case let .allowed(snapshot): sheet = .expense(snapshot)
        case let .blocked(reason): blockedExpense = reason.expenseMessage
        }
    }

    private func requestReset(_ machineID: UUID, _ oldReading: String?) { sheet = .reset(machineID: machineID, oldReading: oldReading) }

    /// Opens what a notification is about (marking it read), or its own detail when it points nowhere on the phone.
    private func openNotification(_ notification: NotificationDTO) {
        Task { await model.markRead(notification) }
        switch InboxLink.from(entity: notification.target?.entity, id: notification.target?.id) {
        case let .job(id): open(.job(id))
        case let .expense(id): open(.expense(model.inbox.expenses.first { $0.serverID == id }?.id ?? id))
        case .money: tab = .money
        case .none: open(.notification(notification.id))
        }
    }

    private func openAttention(_ item: AttentionItem) {
        switch item.kind {
        case .reading: open(.reading(item.refID))
        case .reset: open(.resetDetail(item.refID))
        case .expense: open(.expense(item.refID))
        case .fuel: open(.fuel(item.refID))
        case .collection: open(.cash(item.refID, collection: true))
        case .handover: open(.cash(item.refID, collection: false))
        case .operation, .upload: open(.syncStatus)
        }
    }

    static func icon(_ tab: SupervisorTab) -> String {
        switch tab {
        case .jobs: "list.bullet.clipboard"
        case .readings: "gauge.with.dots.needle.33percent"
        case .fuel: "fuelpump"
        case .money: "wallet.pass"
        case .inbox: "tray"
        }
    }

    private var signOutMessage: String {
        let unsynced = model.overview?.unsyncedCount ?? 0
        return unsynced == 0 ? "You can sign in again at any time."
            : "\(unsynced) item(s) are not synced yet. They stay encrypted on this phone and sync after you sign in again."
    }
}

/// Jobs tab: warnings, then my jobs by segment (in progress, ready to start, recently closed) from the
/// offline cache, or my machines with their latest reading and active job.
struct JobsTabView: View {
    let model: FieldModel
    let open: (FieldRoute) -> Void
    @State private var segment: JobSegment = .inProgress

    var body: some View {
        List {
            FieldBanners(model: model)
            FilterChips(options: JobSegment.allCases.map { ($0, $0.label) }, selection: $segment)
            if segment == .machines {
                let rows = machineRows
                if rows.isEmpty { empty }
                Section {
                    ForEach(rows, id: \.machine.id) { row in
                        NavigationLink(value: FieldRoute.machine(row.machine.id)) {
                            InboxRow(InboxTexts.machine(row.machine.assetCode, row.machine.name), nil,
                                     row.latest.map { "Latest reading \($0.reading) · \($0.at.listText)" } ?? "No readings yet",
                                     row.activeJob.map { "Active job \($0.job.jobNumber)" })
                        }
                    }
                }
            } else {
                let jobs = jobsInSegment
                if jobs.isEmpty { empty }
                Section {
                    ForEach(jobs) { job in
                        NavigationLink(value: FieldRoute.job(job.id)) { JobRow(job: job, progress: model.progress(job)) }
                            .accessibilityIdentifier("job.\(job.job.jobNumber)")
                    }
                }
            }
        }
        .refreshable { await model.sync(force: true) }
    }

    private var empty: some View {
        let text = InboxTexts.jobsEmpty(segment)
        return ContentUnavailableView(text.title, systemImage: "tray",
                                      description: Text(model.isSyncing ? "Syncing…" : text.message))
    }

    private var jobsInSegment: [FieldJob] {
        let jobs = model.jobs.filter { InboxTexts.segment(model.progress($0).displayStatus) == segment }
        return segment == .closed ? jobs.sorted { $0.job.plannedStart > $1.job.plannedStart } : jobs
    }

    /// A machine of mine: its latest reading from my captures and its active job.
    private var machineRows: [(machine: MachineDTO, latest: ReadingItem?, activeJob: FieldJob?)] {
        let latest = model.inbox.latestReadingByMachine()
        let active = model.jobs.filter { [.inProgress, .approved].contains(model.progress($0).displayStatus) }
            .sorted { (model.progress($0).displayStatus == .inProgress ? 0 : 1) < (model.progress($1).displayStatus == .inProgress ? 0 : 1) }
        return model.inbox.machines.values.sorted { $0.assetCode < $1.assetCode }.map { machine in
            (machine, latest[machine.id], active.first { $0.job.machineID == machine.id })
        }
    }
}

struct JobRow: View {
    let job: FieldJob
    let progress: JobProgress

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(job.job.jobNumber).font(.headline)
                Spacer()
                StatusBadge(status: progress.displayStatus, pendingSync: progress.displayStatus != job.job.status)
            }
            Text([job.machine.map { "\($0.assetCode) · \($0.name)" }, job.site?.name, job.customer?.name]
                .compactMap { $0 }.joined(separator: "\n"))
                .font(.subheadline).foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }
}

struct StatusBadge: View {
    let status: JobStatus
    var pendingSync = false

    var body: some View {
        Text(label + (pendingSync ? " · not synced" : ""))
            .font(.caption.bold())
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.15), in: Capsule())
            .foregroundStyle(color)
    }

    private var label: String {
        switch status {
        case .approved: "Approved"
        case .inProgress: "In progress"
        case .completed: "Completed"
        case .cancelled: "Cancelled"
        case .draft: "Draft"
        case .pendingApproval: "Pending approval"
        }
    }

    private var color: Color {
        switch status {
        case .inProgress: Palette.recent
        case .approved: Palette.live
        case .cancelled: Palette.offline
        default: Palette.neutral
        }
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

/// Warnings shown above the job list: clock tamper, server skew, offline state.
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
