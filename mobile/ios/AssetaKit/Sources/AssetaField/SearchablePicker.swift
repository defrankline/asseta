#if os(iOS)
import SwiftUI

/// One row of synced data offered for selection.
struct PickerOption: Identifiable, Hashable, Sendable {
    let id: UUID
    let title: String
    let subtitle: String?

    func matches(_ query: String) -> Bool {
        let needle = query.trimmingCharacters(in: .whitespaces)
        guard !needle.isEmpty else { return true }
        return title.localizedCaseInsensitiveContains(needle) || (subtitle?.localizedCaseInsensitiveContains(needle) ?? false)
    }
}

/// A form row that opens a searchable list (text filter) of synced records. Used for every picker
/// over backend data instead of a plain dropdown.
struct SearchablePickerField: View {
    let label: String
    let options: [PickerOption]
    @Binding var selection: UUID?
    var noneTitle: String?
    var emptyMessage = "Nothing has been synced to this phone yet. Pull down on the home screen to sync."
    var identifier: String
    @State private var presented = false

    var body: some View {
        Button { presented = true } label: {
            LabeledContent(label) {
                if let chosen = options.first(where: { $0.id == selection }) {
                    VStack(alignment: .trailing) {
                        Text(chosen.title).foregroundStyle(.primary)
                        if let subtitle = chosen.subtitle, !subtitle.isEmpty {
                            Text(subtitle).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                } else {
                    Text(noneTitle ?? "Choose…").foregroundStyle(.secondary)
                }
            }
        }
        .accessibilityIdentifier(identifier)
        .sheet(isPresented: $presented) {
            SearchablePickerSheet(title: label, options: options, selection: $selection, noneTitle: noneTitle,
                                  emptyMessage: emptyMessage)
        }
    }
}

struct SearchablePickerSheet: View {
    let title: String
    let options: [PickerOption]
    @Binding var selection: UUID?
    let noneTitle: String?
    let emptyMessage: String
    @State private var query = ""
    @Environment(\.dismiss) private var dismiss

    private var filtered: [PickerOption] { options.filter { $0.matches(query) } }

    var body: some View {
        NavigationStack {
            List {
                if let noneTitle, query.isEmpty {
                    row(title: noneTitle, subtitle: nil, selected: selection == nil) { selection = nil }
                }
                ForEach(filtered) { option in
                    row(title: option.title, subtitle: option.subtitle, selected: option.id == selection) {
                        selection = option.id
                    }
                }
            }
            .overlay {
                if options.isEmpty {
                    ContentUnavailableView("Nothing to choose", systemImage: "tray", description: Text(emptyMessage))
                } else if filtered.isEmpty {
                    ContentUnavailableView.search(text: query)
                }
            }
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Search")
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        }
    }

    private func row(title: String, subtitle: String?, selected: Bool, choose: @escaping () -> Void) -> some View {
        Button {
            choose()
            dismiss()
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).foregroundStyle(.primary)
                    if let subtitle, !subtitle.isEmpty { Text(subtitle).font(.caption).foregroundStyle(.secondary) }
                }
                Spacer()
                if selected { Image(systemName: "checkmark").foregroundStyle(Color.accentColor) }
            }
        }
    }
}
#endif
