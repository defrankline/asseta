#if os(iOS)
import AssetaAppShell
import SwiftUI

/// Horizontally scrolling status chips (Android `FilterChip` row); tapping the selected chip keeps it.
struct FilterChips<Value: Hashable>: View {
    let options: [(Value, String)]
    @Binding var selection: Value

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(Array(options.enumerated()), id: \.offset) { _, option in
                    let on = selection == option.0
                    Button(option.1) { selection = option.0 }
                        .font(.footnote)
                        .buttonStyle(.bordered)
                        .tint(on ? Brand.amber : .secondary)
                        .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
            .padding(.horizontal).padding(.vertical, 6)
        }
    }
}

struct ReloadKey: Hashable {
    let tick: Int
    let filter: String?
}
#endif
