#if os(iOS)
import AssetaAuth
import AssetaModel
import AuthenticationServices
import SwiftUI

/// Root of both apps: routes between login, profile loading, tenant picker and home.
public struct RootView: View {
    private let flavor: AppFlavor
    private let home: HomeBuilder?
    @Bindable private var model: SessionModel

    public init(flavor: AppFlavor, model: SessionModel, home: HomeBuilder? = nil) {
        self.flavor = flavor
        self.model = model
        self.home = home
    }

    public var body: some View {
        Group {
            switch model.phase {
            case .signedOut, .signingIn:
                LoginView(flavor: flavor, model: model)
            case .loadingProfile:
                ProgressView("Loading your account…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            case .profileUnavailable:
                ProfileUnavailableView(model: model)
            case let .ready(me):
                if let tenant = model.selectedTenant {
                    if let home {
                        home(HomeContext(session: model, me: me, tenant: tenant))
                            .id(tenant.tenantID)
                    } else {
                        HomeView(flavor: flavor, me: me, tenant: tenant, model: model)
                    }
                } else {
                    TenantPickerView(me: me, model: model)
                }
            }
        }
        .tint(Brand.amber)
        .modifier(PasswordChangeAlerts(session: model))
        .task { await model.start() }
    }
}

struct LoginView: View {
    let flavor: AppFlavor
    let model: SessionModel
    @Environment(\.webAuthenticationSession) private var webAuthenticationSession

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            // Same brand mark and wordmark as the Android sign-in screen.
            BrandMark()
                .frame(width: 112, height: 112)
            VStack(spacing: 8) {
                Text("Asseta").font(.largeTitle.bold()).foregroundStyle(Brand.offWhite)
                Text(flavor.roleName).font(.title3.weight(.semibold)).foregroundStyle(Brand.amber)
                Text(flavor.tagline).font(.subheadline).foregroundStyle(Brand.offWhite.opacity(0.8))
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel(flavor.appName)
            Spacer()
            if let message = model.errorMessage {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(Brand.offWhite)
                    .multilineTextAlignment(.center)
                    .accessibilityIdentifier("login.error")
            }
            Button {
                Task { await model.signIn(using: authenticate) }
            } label: {
                Group {
                    if model.phase == .signingIn {
                        HStack(spacing: 8) {
                            ProgressView().tint(Brand.slate)
                            Text("Signing in…").font(.headline)
                        }
                    } else {
                        Text("Sign in").font(.headline)
                    }
                }
                .frame(maxWidth: .infinity, minHeight: 50)
            }
            .buttonStyle(.borderedProminent)
            .tint(Brand.amber)
            .foregroundStyle(Brand.slate)
            .disabled(model.phase == .signingIn)
            .accessibilityIdentifier("login.signIn")
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Brand.slate.ignoresSafeArea())
    }

    private func authenticate(url: URL, callbackScheme: String) async throws -> URL {
        try await webAuthenticationSession.ephemeralAuthenticate(url: url, callbackScheme: callbackScheme)
    }
}

struct ProfileUnavailableView: View {
    let model: SessionModel

    var body: some View {
        ContentUnavailableView {
            Label("Can't load your account", systemImage: "wifi.exclamationmark")
        } description: {
            Text(model.errorMessage ?? "Check your connection and try again.")
        } actions: {
            Button("Retry") { Task { await model.loadProfile() } }
                .buttonStyle(.borderedProminent)
            Button("Sign out", role: .destructive) { Task { await model.signOut() } }
        }
    }
}
#endif
