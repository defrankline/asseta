#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import Observation
import SwiftUI

/// Loads one server read for a screen: paints the cached snapshot first (if any), then asks the
/// server; when offline the repository returns the cached snapshot marked stale.
@MainActor
@Observable
final class Loader<Value: Codable & Sendable> {
    private(set) var snapshot: Snapshot<Value>?
    private(set) var error: String?
    private(set) var isLoading = false

    var value: Value? { snapshot?.value }
    var isFromCache: Bool { snapshot?.isFromCache ?? false }

    func load(_ model: OwnerModel, _ key: SnapshotKey, _ request: APIRequest<Value>) async {
        guard let repository = model.repository else { error = "This build is missing its configuration."; return }
        if snapshot == nil { snapshot = repository.cached(key) }
        isLoading = true
        defer { isLoading = false }
        do {
            snapshot = try await repository.load(key, request)
            error = nil
        } catch is CancellationError {
        } catch {
            if case .transport? = error as? APIError, snapshot != nil {
                // Keep showing the painted snapshot; it is already marked stale.
            } else {
                self.error = DecisionErrorText.message(for: error)
            }
            model.handle(error)
        }
    }

    /// Replaces the value after a successful mutation (fresh from the server).
    func replace(_ value: Value) {
        snapshot = Snapshot(value: value, fetchedAt: Date(), source: .server)
    }
}

/// "Offline — data from 14:05 (stale)" above any screen showing cached data.
struct StaleBanner: View {
    let fetchedAt: Date?
    let isOnline: Bool

    var body: some View {
        if let fetchedAt {
            Label(OwnerFormat.staleBanner(fetchedAt: fetchedAt, isOnline: isOnline), systemImage: "icloud.slash")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Brand.slate)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 8).padding(.horizontal, 12)
                .background(Brand.amber, in: RoundedRectangle(cornerRadius: 10))
                .accessibilityIdentifier("offline.banner")
                .accessibilityAddTraits(.isStaticText)
        }
    }
}

extension View {
    /// Adds the stale banner as a list section header when `snapshot` came from the cache.
    func staleBanner<V>(_ loader: Loader<V>, model: OwnerModel) -> some View {
        safeAreaInset(edge: .top) {
            if loader.isFromCache {
                StaleBanner(fetchedAt: loader.snapshot?.fetchedAt, isOnline: model.isOnline)
                    .padding(.horizontal).padding(.top, 4)
            }
        }
    }
}

/// Error line with retry, used when nothing (not even cache) can be shown.
struct LoadFailure: View {
    let message: String
    let retry: () async -> Void

    var body: some View {
        ContentUnavailableView {
            Label("Can't load this", systemImage: "exclamationmark.icloud")
        } description: {
            Text(message)
        } actions: {
            Button("Try again") { Task { await retry() } }.buttonStyle(.borderedProminent)
        }
    }
}

extension MarkerTone {
    var color: Color {
        switch self {
        case .live: .green
        case .recent: .teal
        case .stale: Brand.amber
        case .offline: .red
        case .unknown: .gray
        }
    }
}

extension AlertSeverity {
    var color: Color {
        switch self {
        case .critical: .red
        case .info: .blue
        default: .orange
        }
    }

    var label: String { humanized }
}

/// Coloured capsule label.
struct Pill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption.bold())
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.15), in: Capsule())
            .foregroundStyle(color)
    }
}

/// One KPI: big number, caption, optional tint.
struct KPITile: View {
    let title: String
    let value: String
    var tint: Color = .primary
    var systemImage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                if let systemImage { Image(systemName: systemImage).foregroundStyle(tint).accessibilityHidden(true) }
                Text(title).font(.caption).foregroundStyle(.secondary)
            }
            Text(value).font(.title3.bold()).foregroundStyle(tint == .primary ? Color.primary : tint)
                .minimumScaleFactor(0.6).lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
    }
}

/// Explains why an action is disabled.
struct BlockedNote: View {
    let block: MutationBlock

    var body: some View {
        Label(block.message, systemImage: "lock")
            .font(.footnote).foregroundStyle(.secondary)
    }
}

extension JobStatus {
    var label: String {
        switch self {
        case .approved: "Approved"
        case .inProgress: "In progress"
        case .completed: "Completed"
        case .cancelled: "Cancelled"
        case .draft: "Draft"
        case .pendingApproval: "Pending approval"
        }
    }

    var color: Color {
        switch self {
        case .inProgress: .blue
        case .approved: .green
        case .cancelled: .red
        case .pendingApproval: .orange
        default: .secondary
        }
    }
}

extension Date {
    var shortStamp: String { OwnerFormat.timestamp(self) }
}
#endif
