#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

// DEC-031 Phase 1 (Supervisor): the non-revenue status of work-log entries and the "Explain non-revenue time" form.
// Online only (no outbox operation); the server decides who may explain and approve.

private typealias T = FieldRevenueTexts

extension FieldModel {
    /// Re-reads the job's non-revenue entries (online, read holders, capability on). Offline the last read stays.
    func loadNonRevenue(jobID: UUID) async {
        guard access.nonRevenueStatus, isOnline, let online else { return }
        if let items = try? await online.nonRevenueActivities(jobID: jobID) {
            nonRevenueByJob[jobID] = NonRevenueRules.byActivity(items)
        }
    }

    /// The server's non-revenue entry behind a work-log line, when it lists one.
    func nonRevenue(_ entry: ActivityItem) -> NonRevenueActivityDTO? {
        guard access.nonRevenueStatus, let id = entry.serverID else { return nil }
        return nonRevenueByJob[entry.jobID]?[id]
    }
}

/// The status line under a work-log entry, with "Explain" for explain holders (NONE / REJECTED; disabled offline).
struct NonRevenueStatusLine: View {
    let model: FieldModel
    let activity: NonRevenueActivityDTO
    let explain: (NonRevenueActivityDTO) -> Void

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(T.status(activity.approvalStatus))
                .font(.caption)
                .foregroundStyle(color(NonRevenueRules.tone(activity.approvalStatus)))
            Spacer()
            if model.access.explainNonRevenue && NonRevenueRules.explainable(activity.approvalStatus) {
                Button(T.explain) { explain(activity) }
                    .font(.caption.bold())
                    .buttonStyle(.borderless)
                    .disabled(!model.isOnline)
                    .accessibilityHint(model.isOnline ? "" : T.offline)
                    .accessibilityIdentifier("nonrev.explain")
            }
        }
    }

    private func color(_ tone: NonRevenueTone) -> Color {
        switch tone {
        case .warning: Palette.warning
        case .accent: Color.accentColor
        case .live: Palette.live
        }
    }
}

/// "Explain non-revenue time": the entry, a reason from the tenant's list and a note; sent online.
struct NonRevenueExplainView: View {
    let model: FieldModel
    let activity: NonRevenueActivityDTO
    @Environment(\.dismiss) private var dismiss
    @State private var reasons: [RevenueReasonDTO]?
    @State private var reasonID: UUID?
    @State private var note = ""
    @State private var sending = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section(T.entry) {
                    Text(entryLine).font(.subheadline)
                    if let note = activity.note, !note.trimmingCharacters(in: .whitespaces).isEmpty {
                        Text(note).font(.footnote).foregroundStyle(.secondary)
                    }
                }
                if !model.isOnline {
                    ContentUnavailableView(T.title, systemImage: "wifi.slash", description: Text(T.offline))
                } else {
                    Section {
                        if let reasons, reasons.isEmpty {
                            Text(T.reasonsEmpty).font(.footnote).foregroundStyle(.secondary)
                        }
                        SearchablePickerField(label: T.chooseReason,
                                              options: (reasons ?? []).map { PickerOption(id: $0.id, title: $0.name, subtitle: $0.description) },
                                              selection: $reasonID, emptyMessage: T.reasonsEmpty, identifier: "nonrev.reason")
                        TextField(T.note, text: Binding(get: { note }, set: { note = String($0.prefix(NonRevenueRules.noteMax)) }),
                                  axis: .vertical).lineLimit(2...5)
                            .accessibilityIdentifier("nonrev.note")
                    } header: { Text(T.reason) } footer: { Text(T.footer) }
                    if let error { Section { Text(error).foregroundStyle(Palette.offline) } }
                }
            }
            .disabled(sending)
            .navigationTitle(T.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(T.send) { Task { await send() } }
                        .disabled(sending || !NonRevenueRules.canSend(reasonID: reasonID, note: note, online: model.isOnline))
                        .accessibilityIdentifier("nonrev.send")
                }
            }
            .task(id: model.isOnline) { await loadReasons() }
        }
    }

    private var entryLine: String {
        let time = Date.FormatStyle(date: .omitted, time: .shortened)
        let hours = activity.hours.value.formatted(.number.precision(.fractionLength(0...2)).grouping(.never)
            .locale(Locale(identifier: "en_US_POSIX")))
        return T.entryLine(type: InboxTexts.activityType(activity.activityType), start: activity.startedAt.formatted(time),
                           end: activity.endedAt.formatted(time), hours: hours)
    }

    private func loadReasons() async {
        guard reasons == nil, model.isOnline, let online = model.online else { return }
        do {
            reasons = try await online.revenueReasons()
        } catch {
            self.error = NonRevenueRules.message(for: error)
        }
    }

    private func send() async {
        guard let online = model.online, let reasonID else { return }
        sending = true
        defer { sending = false }
        do {
            _ = try await online.explainNonRevenue(activityID: activity.activityID, reasonID: reasonID, note: note)
            UIAccessibility.post(notification: .announcement, argument: T.sent)
            await model.loadNonRevenue(jobID: activity.jobID)
            dismiss()
        } catch {
            self.error = NonRevenueRules.message(for: error)
        }
    }
}
#endif
