#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Inbox. Live updates arrive over the WebSocket while the app is in the foreground; the list is
/// re-read on each new notification and on every reconnect (the inbox is the durable record).
struct NotificationsView: View {
    let model: OwnerModel
    @State private var loader = Loader<Page<NotificationDTO>>()
    @State private var unreadOnly = false

    var body: some View {
        List {
            Toggle("Unread only", isOn: $unreadOnly)
            if let page = loader.value {
                Button("Mark all read") { Task { await markAllRead() } }
                    .disabled(!model.isOnline || loader.isFromCache || !page.items.contains(where: \.isUnread))
                let items = InboxText.visible(page.items, unreadOnly: unreadOnly)
                if items.isEmpty {
                    EmptyState(title: InboxText.emptyTitle, systemImage: "bell.slash")
                }
                ForEach(items) { note in
                    NavigationLink(value: DeepLinkParser.route(for: note) == .notifications
                        ? OwnerRoute.notification(note.id) : DeepLinkParser.route(for: note)) {
                        NotificationRow(note: note)
                    }
                    .simultaneousGesture(TapGesture().onEnded { Task { await markRead(note) } })
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Notifications")
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick &+ model.inboxTick, filter: nil)) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .notifications, OwnerAPI.notifications(pageSize: 100))
    }

    private func markAllRead() async {
        guard let repository = model.repository, let request = try? OwnerAPI.markAllRead(idempotencyKey: UUID()) else { return }
        do {
            let result = try await repository.send(request)
            model.noteRead(remaining: result.unread)
            await reload()
        } catch {
            model.handle(error)
        }
    }

    private func markRead(_ note: NotificationDTO) async {
        await NotificationResolverView.markRead(note, model: model)
    }
}

struct NotificationRow: View {
    let note: NotificationDTO

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle().fill(note.isUnread ? Brand.amber : .clear).frame(width: 8, height: 8).padding(.top, 6)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(note.title).font(note.isUnread ? .headline : .body)
                    Spacer()
                    // INFO carries no pill; high priority is called out (as on Android).
                    if note.severity != .info { Pill(text: note.severity.label, color: note.severity.color) }
                    if note.priority == "HIGH" { Pill(text: "High priority", color: .red) }
                }
                Text(note.body).font(.subheadline).foregroundStyle(.secondary).lineLimit(3)
                Text(note.createdAt.shortStamp).font(.caption).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(note.isUnread ? "Unread. " : "")\(note.title). \(note.body)")
    }
}

/// Opens a notification by id (from a push tap): fetches it, marks it read and shows its target.
struct NotificationResolverView: View {
    let model: OwnerModel
    let notificationID: UUID
    @State private var note: NotificationDTO?
    @State private var error: String?

    var body: some View {
        Group {
            if let note {
                let route = DeepLinkParser.route(for: note)
                if route == .notifications || route == .notification(notificationID) {
                    List {
                        Section { NotificationRow(note: note) }
                        Section { Text(InboxText.noTarget).foregroundStyle(.secondary) }
                    }
                    .navigationTitle("Notification")
                } else {
                    RouteView(model: model, route: route)
                }
            } else if let error {
                ContentUnavailableView("Can't open notification", systemImage: "bell.slash", description: Text(error))
            } else {
                ProgressView()
            }
        }
        .task { await load() }
    }

    private func load() async {
        guard let repository = model.repository else { return }
        do {
            let fetched = try await repository.send(OwnerAPI.notification(notificationID))
            note = fetched
            await Self.markRead(fetched, model: model)
        } catch {
            self.error = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }

    /// Marks one notification read (the user's own inbox state; online only).
    static func markRead(_ note: NotificationDTO, model: OwnerModel) async {
        guard note.isUnread, model.isOnline, let repository = model.repository,
              let request = try? OwnerAPI.markRead([note.id], idempotencyKey: UUID()) else { return }
        let result = try? await repository.send(request)
        model.noteRead(remaining: result?.unread)
    }
}
#endif
