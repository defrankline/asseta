#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Home dashboard: fleet, work, money and risk KPIs with per-section freshness. The figures, labels and links come
/// from `OverviewPresentation`, which the Android Owner app mirrors.
struct OverviewView: View {
    let model: OwnerModel
    let open: (OwnerRoute) -> Void
    @State private var loader = Loader<TenantOverviewDTO>()
    private let columns = [GridItem(.adaptive(minimum: 150), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if loader.isFromCache {
                    StaleBanner(fetchedAt: loader.snapshot?.fetchedAt, isOnline: model.isOnline)
                }
                if let banner = model.setupProgress.bannerText {
                    SetupBannerView(text: banner) { open(.setupChecklist) }
                }
                if let overview = loader.value {
                    let sections = OverviewPresentation.sections(overview, cached: loader.isFromCache)
                    ForEach(sections, id: \.title) { section($0) }
                    if sections.isEmpty { Text(OverviewPresentation.noSections).foregroundStyle(.secondary) }
                    Text(OverviewPresentation.asOf(overview)).font(.caption).foregroundStyle(.secondary)
                } else if let error = loader.error {
                    LoadFailure(message: error) { await reload() }
                } else {
                    ProgressView("Loading overview…").frame(maxWidth: .infinity, minHeight: 200)
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle(model.tenant.name)
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .modifier(NotificationBell(model: model) { open(.notifications) })
    }

    private func reload() async { await loader.load(model, .overview, OwnerAPI.overview()) }

    @ViewBuilder private func section(_ section: OverviewSection) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(section.title).font(.title3.bold())
            Text(section.freshness).font(.caption).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
        if let empty = section.emptyText { Text(empty).foregroundStyle(.secondary) }
        ForEach(Array(section.groups.enumerated()), id: \.offset) { _, group in
            VStack(alignment: .leading, spacing: 8) {
                if let heading = group.heading { Text(heading).font(.headline) }
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(group.rows, id: \.label) { tile($0) }
                }
            }
        }
        ForEach(section.actions.filter { model.features.allows($0.route) }, id: \.label) { action in
            Button(action.label) { open(action.route) }.font(.subheadline)
        }
    }

    @ViewBuilder private func tile(_ row: OverviewRow) -> some View {
        let kpi = KPITile(title: row.label, value: row.value, detail: row.detail, tint: row.tone.color)
        if let route = row.route, model.features.allows(route) {
            Button { open(route) } label: { kpi }
                .buttonStyle(.plain)
                .accessibilityHint("Opens \(row.label.lowercased()).")
        } else {
            kpi
        }
    }
}
#endif
