#if os(iOS)
import AssetaModel
import SwiftUI

struct TenantPickerView: View {
    let me: MeResponse
    let model: SessionModel

    var body: some View {
        NavigationStack {
            List {
                if me.tenants.isEmpty {
                    ContentUnavailableView(
                        "No company access",
                        systemImage: "building.2",
                        description: Text("Your account is not a member of any company yet. Ask your administrator.")
                    )
                } else {
                    Section("Choose a company") {
                        ForEach(me.tenants) { tenant in
                            Button { model.selectTenant(tenant) } label: { TenantRow(tenant: tenant) }
                                .disabled(!tenant.accessState.allowsEntry)
                                .accessibilityIdentifier("tenant.\(tenant.tenantID.uuidString)")
                        }
                    }
                }
                if let message = model.errorMessage {
                    Section { Text(message).foregroundStyle(.red) }
                }
            }
            .navigationTitle("Hello, \(me.displayName)")
            .refreshable { await model.loadProfile() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Sign out") { Task { await model.signOut() } }
                }
            }
        }
    }
}

struct TenantRow: View {
    let tenant: TenantMembership

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(tenant.name).font(.headline)
                Text(tenant.status.rawValue.capitalized).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            AccessBadge(state: tenant.accessState)
        }
        .contentShape(Rectangle())
    }
}

struct AccessBadge: View {
    let state: TenantAccessState

    var body: some View {
        Text(label)
            .font(.caption.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.15), in: Capsule())
            .foregroundStyle(color)
    }

    private var label: String {
        switch state {
        case .full: "Full access"
        case .readOnly: "Read only"
        case .blocked: "Blocked"
        default: state.rawValue
        }
    }

    private var color: Color {
        switch state {
        case .full: .green
        case .readOnly: Brand.amber
        default: .red
        }
    }
}

/// Post-login landing screen. Lists the modules the server says this user may see; the
/// feature screens themselves arrive with their gates (jobs/meter in Gate 3-4, owner in Gate 7).
struct HomeView: View {
    let flavor: AppFlavor
    let me: MeResponse
    let tenant: TenantMembership
    let model: SessionModel

    var body: some View {
        NavigationStack {
            List {
                Section("Signed in") {
                    LabeledContent("Name", value: me.displayName)
                    LabeledContent("Email", value: me.email)
                }
                Section("Company") {
                    LabeledContent("Name", value: tenant.name)
                    LabeledContent("Access") { AccessBadge(state: tenant.accessState) }
                    if tenant.accessState == .readOnly {
                        Text("This company is read-only. Changes are disabled by the server.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
                Section {
                    if tenant.orderedMenus.isEmpty {
                        Text("No modules are assigned to your role.").foregroundStyle(.secondary)
                    } else {
                        ForEach(tenant.orderedMenus) { menu in
                            Text(menu.label).accessibilityIdentifier("menu.\(menu.key)")
                        }
                    }
                } header: {
                    Text("Modules granted to you")
                } footer: {
                    Text("Granted by your administrator in Asseta. Module screens are not part of this build yet.")
                }
            }
            .navigationTitle(flavor.appName)
            .refreshable { await model.loadProfile() }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    if me.tenants.count > 1 {
                        Button("Switch company") { model.clearTenantSelection() }
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Sign out") { Task { await model.signOut() } }
                }
            }
        }
    }
}
#endif
