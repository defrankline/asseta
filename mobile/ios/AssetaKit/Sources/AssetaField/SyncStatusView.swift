#if os(iOS)
import AssetaAppShell
import AssetaStore
import AssetaSync
import SwiftUI

/// Everything not yet synced: pending, rejected (with error code), conflicts (with the server's
/// state) and items held because the subscription is read-only.
struct SyncStatusView: View {
    let model: FieldModel

    var body: some View {
        List {
            summary
            group("Needs attention: rejected", .failed, footer: "The server refused these. The original evidence stays on this phone. Retry after fixing the cause, or ask your administrator.")
            group("Needs attention: conflicts", .conflict, footer: "The job changed on the server (for example it was cancelled or reassigned). Nothing was overwritten; your record is kept for review.")
            group("Held: subscription read-only", .quarantined, footer: "Your company's subscription is read-only. These are kept by the server and re-sent automatically after reactivation.")
            group("Waiting to sync", .pending, footer: nil)
            group("Sending", .sent, footer: nil)
            ForEach(model.overview?.heldAccounts ?? [], id: \.subject) { held in
                Section {
                    Text("\(held.count) item(s) not synced yet").font(.subheadline)
                } header: {
                    Text(Self.heldTitle(held.label))
                } footer: {
                    Text("Saved on this phone by another account. They stay encrypted here and are sent only when that account signs in again.")
                }
            }
            if let failed = model.overview?.failedUploads, !failed.isEmpty {
                Section("Evidence files that cannot be uploaded") {
                    ForEach(failed) { file in
                        VStack(alignment: .leading) {
                            Text(file.purpose == "SIGNATURE" ? "Signature" : file.purpose == "EXPENSE_RECEIPT" ? "Receipt photo" : "Meter photo")
                            Text(file.lastError ?? "").font(.caption).foregroundStyle(Palette.offline)
                        }
                    }
                }
            }
            Section {
                Text("Asseta syncs when the app is open and when the connection comes back. iOS may also let it sync occasionally in the background, but that is not guaranteed — open the app to be sure.")
                    .font(.footnote).foregroundStyle(.secondary)
                if let device = model.deviceID {
                    LabeledContent("Device ID", value: String(device.prefix(8))).font(.footnote)
                }
            }
        }
        .navigationTitle("Sync status")
        .refreshable { await model.sync(force: true) }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Sync now") { Task { await model.sync(force: true) } }.disabled(model.isSyncing)
                    .accessibilityIdentifier("sync.now")
            }
        }
    }

    /// Another account's unsynced work (identical wording on Android); `label` nil when not known.
    static func heldTitle(_ label: String?) -> String { "Waiting for \(label ?? "a previous account") to sign in again" }

    @ViewBuilder private var summary: some View {
        Section {
            if model.isSyncing { ProgressView("Syncing…") }
            let counts = model.overview?.counts ?? [:]
            LabeledContent("Synced", value: "\(counts[.acked] ?? 0)")
            LabeledContent("Not yet synced", value: "\(model.overview?.unsyncedCount ?? 0)")
            LabeledContent("Files waiting to upload", value: "\(model.overview?.pendingUploads ?? 0)")
            if let last = model.overview?.lastSuccessAt {
                LabeledContent("Last successful sync", value: last.formatted(date: .abbreviated, time: .shortened))
            } else {
                LabeledContent("Last successful sync", value: "Never")
            }
            if let next = model.overview?.nextAttemptAt, next > Date() {
                LabeledContent("Next automatic retry", value: next.formatted(date: .omitted, time: .standard))
            }
            if let grant = model.overview?.offlineGrantUntil {
                LabeledContent("Offline use allowed until", value: grant.formatted(date: .abbreviated, time: .shortened))
            }
        }
    }

    @ViewBuilder private func group(_ title: String, _ status: ClientOperationStatus, footer: String?) -> some View {
        let items = model.overview?.items.filter { $0.operation.status == status } ?? []
        if !items.isEmpty {
            Section {
                ForEach(items) { item in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack {
                            Text(item.title).font(.subheadline)
                            Spacer()
                            SyncStateLabel(status: item.operation.status)
                        }
                        if let job = item.jobID.flatMap(model.job) { Text(job.job.jobNumber).font(.caption) }
                        Text(item.operation.createdAtDevice.formatted(date: .abbreviated, time: .standard))
                            .font(.caption).foregroundStyle(.secondary)
                        if let code = item.operation.errorCode, status != .pending {
                            // Plain words for the accountability conflicts (strings doc `field.conflict.*`).
                            Text(FieldAccountabilityTexts.conflictText(code) ?? "\(code): \(item.operation.lastError ?? "")")
                                .font(.caption).foregroundStyle(Palette.offline)
                        }
                        if let state = item.serverState { Text("Server state: \(state)").font(.caption.monospaced()) }
                        if let waiting = item.waitingFor { Text(waiting).font(.caption).foregroundStyle(.secondary) }
                        if status == .pending, let next = item.operation.nextAttemptAt, next > Date() {
                            Text("Retry after \(next.formatted(date: .omitted, time: .standard))").font(.caption)
                        }
                        if status == .failed {
                            Button("Retry") { model.retry(item.operation) }.font(.caption.bold())
                        }
                    }
                }
            } header: { Text("\(title) (\(items.count))") } footer: { footer.map(Text.init) }
        }
    }
}
#endif
