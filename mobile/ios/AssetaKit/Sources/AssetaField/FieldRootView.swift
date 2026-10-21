#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

/// Supervisor home: assigned jobs (from the offline cache), sync state and warnings.
public struct FieldRootView: View {
    @State private var model: FieldModel
    @Environment(\.scenePhase) private var scenePhase
    @State private var confirmSignOut = false
    private let showsSwitchCompany: Bool

    public init(context: HomeContext) {
        _model = State(initialValue: FieldModel(session: context.session, tenant: context.tenant))
        showsSwitchCompany = context.me.tenants.count > 1
    }

    /// Convenience for `AssetaAppScene(home:)`.
    public static let home: HomeBuilder = { AnyView(FieldRootView(context: $0)) }

    public var body: some View {
        NavigationStack {
            content
                .navigationTitle(model.tenant.name)
                .toolbar { toolbar }
                .refreshable { await model.sync(force: true) }
                .navigationDestination(for: UUID.self) { id in JobDetailView(model: model, jobID: id) }
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
    }

    private var signOutMessage: String {
        let unsynced = model.overview?.unsyncedCount ?? 0
        return unsynced == 0 ? "You can sign in again at any time."
            : "\(unsynced) item(s) are not synced yet. They stay encrypted on this phone and sync after you sign in again."
    }

    @ViewBuilder private var content: some View {
        switch model.phase {
        case .loading:
            ProgressView("Opening your jobs…").frame(maxWidth: .infinity, maxHeight: .infinity)
        case let .failed(message):
            ContentUnavailableView("Can't open local data", systemImage: "externaldrive.badge.exclamationmark",
                                   description: Text(message))
        case .ready:
            List {
                FieldBanners(model: model)
                FinanceSection(model: model)
                if model.jobs.isEmpty {
                    ContentUnavailableView("No assigned jobs", systemImage: "tray",
                                           description: Text(model.isSyncing ? "Syncing…" : "Pull down to sync when you are online."))
                } else {
                    jobSection("In progress", model.jobs.filter { model.progress($0).displayStatus == .inProgress })
                    jobSection("Ready to start", model.jobs.filter { model.progress($0).displayStatus == .approved })
                    jobSection("Other", model.jobs.filter {
                        ![.inProgress, .approved].contains(model.progress($0).displayStatus)
                    })
                }
            }
        }
    }

    @ViewBuilder private func jobSection(_ title: String, _ jobs: [FieldJob]) -> some View {
        if !jobs.isEmpty {
            Section(title) {
                ForEach(jobs) { job in
                    NavigationLink(value: job.id) { JobRow(job: job, progress: model.progress(job)) }
                        .accessibilityIdentifier("job.\(job.job.jobNumber)")
                }
            }
        }
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            NavigationLink { SyncStatusView(model: model) } label: { SyncBadge(model: model) }
                .accessibilityIdentifier("sync.status")
        }
        ToolbarItem(placement: .topBarLeading) {
            Menu {
                if showsSwitchCompany { Button("Switch company") { model.stop(); model.session.clearTenantSelection() } }
                Button("Sign out", role: .destructive) { confirmSignOut = true }
            } label: { Image(systemName: "person.crop.circle") }
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
        case .inProgress: .blue
        case .approved: .green
        case .cancelled: .red
        default: .secondary
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
        .foregroundStyle(attention > 0 ? Color.red : Color.accentColor)
        .accessibilityLabel(unsynced == 0 ? "All synced" : "\(unsynced) items not synced")
    }
}

/// Warnings shown above the job list: clock tamper, server skew, offline state.
struct FieldBanners: View {
    let model: FieldModel

    var body: some View {
        if case let .tamperSuspected(deviation) = model.clockStatus {
            Banner(icon: "clock.badge.exclamationmark", color: .orange,
                   text: "This phone's clock is \(Self.describe(deviation)) compared with Asseta's server. Set the date and time to automatic. Readings still record the phone's own time.")
                .accessibilityIdentifier("banner.clock")
        } else if model.overview?.serverClockSkewAlert == true {
            Banner(icon: "clock.badge.exclamationmark", color: .orange,
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
