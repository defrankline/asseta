#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

extension Tone {
    /// Colour of a status tone (same mapping as Android `toneColor`).
    var color: Color {
        switch self {
        case .neutral: Palette.neutral
        case .good: Palette.live
        case .warning: Palette.warning
        case .bad: Palette.offline
        case .info: Palette.recent
        }
    }
}

/// Capsule label tinted with `color`: text in the colour on a 15 % wash (Android `Pill`).
struct Pill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption.bold()).lineLimit(1)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.15), in: Capsule())
            .foregroundStyle(color)
    }
}

/// The one combined status pill of a record.
struct StatusPill: View {
    let status: InboxStatus
    var body: some View { Pill(text: status.label, color: status.tone.color) }
}

/// A list row: title and status pill on the first line, grey detail lines below (Android `InboxRow`).
struct InboxRow: View {
    let title: String
    let status: InboxStatus?
    let lines: [String?]

    init(_ title: String, _ status: InboxStatus?, _ lines: String?...) {
        self.title = title
        self.status = status
        self.lines = lines
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 8) {
                Text(title).font(.headline).lineLimit(2)
                Spacer()
                if let status { StatusPill(status: status) }
            }
            ForEach(Array(lines.compactMap { $0 }.filter { !$0.isEmpty }.enumerated()), id: \.offset) { _, line in
                Text(line).font(.subheadline).foregroundStyle(.secondary).lineLimit(3)
            }
        }
        .padding(.vertical, 2)
    }
}

/// Horizontally scrolling bordered filter buttons, tinted when selected (Android `FilterChipRow`).
struct FilterChips<Value: Hashable>: View {
    let options: [(Value, String)]
    @Binding var selection: Value

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(options, id: \.0) { value, label in
                    Button(label) { selection = value }
                        .buttonStyle(.bordered)
                        .tint(selection == value ? Color.accentColor : .secondary)
                        .font(.footnote)
                        .accessibilityAddTraits(selection == value ? .isSelected : [])
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 6)
        }
        .listRowInsets(EdgeInsets())
        .listRowBackground(Color.clear)
    }
}

/// Evidence photo: the local encrypted copy when this phone has it, else the server copy when online
/// and allowed (a short-lived URL, loaded into memory only).
struct EvidenceImage: View {
    let description: String
    let local: (() -> Data?)?
    let remote: (() async -> URL?)?
    @State private var image: UIImage?
    @State private var done = false

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 320)
                    .accessibilityLabel(description)
            } else if !done {
                ProgressView()
            } else {
                Text("The photo is not on this phone. Connect to view it.").font(.footnote).foregroundStyle(.secondary)
            }
        }
        .task {
            if let data = local?(), let picture = UIImage(data: data) {
                image = picture
            } else if let url = await remote?(),
                      let (data, _) = try? await URLSession.shared.data(from: url), data.count <= 15 * 1024 * 1024 {
                image = UIImage(data: data)
            }
            done = true
        }
    }
}

/// Sync state of a local record, with the server's refusal when there is one.
struct SyncSection: View {
    let operation: ClientOperation?

    var body: some View {
        if let operation {
            Section("Sync") {
                LabeledContent("On this phone") { SyncStateLabel(status: operation.status) }
                if let code = operation.errorCode {
                    Text("\(code): \(operation.lastError ?? "")").font(.caption).foregroundStyle(Palette.offline)
                }
            }
        }
    }
}

extension Date {
    /// Abbreviated date + short time, as every list shows it.
    var listText: String { formatted(date: .abbreviated, time: .shortened) }
}
#endif
