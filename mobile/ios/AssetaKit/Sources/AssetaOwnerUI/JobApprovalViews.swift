#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

/// "Request" section of a field-requested job: who asked and what the customer asked for.
struct JobRequestSection: View {
    let job: JobDTO

    var body: some View {
        if job.isFieldRequest || !(job.requestNote ?? "").isEmpty {
            Section(JobApprovalText.requestTitle) {
                if let requested = JobApprovalText.requestedBy(job) { Text(requested) }
                if let note = job.requestNote, !note.isEmpty { LabeledContent(JobApprovalText.customerAsked, value: note) }
            }
        }
    }
}

/// A job waiting for approval in the Approvals list: number, who requested it from the field, and the note.
struct PendingJobRow: View {
    let job: JobDTO

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(job.jobNumber).font(.headline)
            if let requested = JobApprovalText.requestedBy(job) {
                Text(requested).font(.subheadline).foregroundStyle(.secondary)
            }
            Text(JobsPresentation.datesLine(job)).font(.caption).foregroundStyle(.secondary)
            if let note = job.requestNote, !note.isEmpty {
                Text(note).font(.caption).foregroundStyle(.secondary).lineLimit(3)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

/// The decision on a job waiting for approval (job detail): Approve, asking for the hourly rate when no rate card
/// applies, or Decline with a required reason (the supervisor sees it). Gated like other owner actions.
struct JobDecisionSection: View {
    let model: OwnerModel
    let job: JobDTO
    let showingCachedData: Bool
    let decided: (JobDTO) async -> Void
    @State private var sheet: Mode?
    @State private var message: String?

    enum Mode: String, Identifiable { case approve, decline; var id: String { rawValue } }

    var body: some View {
        Section(JobApprovalText.decisionTitle) {
            if let block = model.mutationBlock(permitted: model.features.approveJobs, showingCachedData: showingCachedData) {
                BlockedNote(block: block)
            } else {
                HStack {
                    Button(JobApprovalText.approve) { sheet = .approve }
                        .buttonStyle(.borderedProminent).tint(Palette.live)
                        .accessibilityIdentifier("job.approve")
                    Spacer()
                    Button(JobApprovalText.decline, role: .destructive) { sheet = .decline }
                        .buttonStyle(.bordered)
                        .accessibilityIdentifier("job.decline")
                }
            }
            if let message { Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("job.decision.message") }
        }
        .sheet(item: $sheet) { mode in
            JobDecisionSheet(model: model, job: job, mode: mode) { updated, text in
                message = text
                UIAccessibility.post(notification: .announcement, argument: text)
                await decided(updated)
            }
        }
    }
}

struct JobDecisionSheet: View {
    let model: OwnerModel
    let job: JobDTO
    let mode: JobDecisionSection.Mode
    let done: (JobDTO, String) async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var rate = ""
    @State private var reason = ""
    @State private var working = false
    @State private var error: String?
    @State private var idempotencyKey = UUID()

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    LabeledContent("Job", value: job.jobNumber)
                    if let requested = JobApprovalText.requestedBy(job) { Text(requested).foregroundStyle(.secondary) }
                }
                if mode == .approve {
                    Section {
                        if job.needsPrice {
                            TextField(JobApprovalText.hourlyRateLabel(currency: job.currency), text: $rate)
                                .keyboardType(.decimalPad)
                                .accessibilityIdentifier("job.approve.rate")
                        } else if let current = job.hourlyRate {
                            LabeledContent(JobApprovalText.hourlyRateLabel(currency: job.currency),
                                           value: OwnerFormat.money(current, currency: job.currency ?? ""))
                        }
                    } footer: {
                        if job.needsPrice { Text(JobApprovalText.pendingPriceHelper) }
                    }
                } else {
                    Section {
                        TextField(JobApprovalText.reason, text: $reason, axis: .vertical)
                            .lineLimit(2...5)
                            .accessibilityIdentifier("job.decline.reason")
                    }
                }
                if let error {
                    Text(error).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("job.decision.error")
                }
            }
            .navigationTitle(mode == .approve ? JobApprovalText.approveTitle : JobApprovalText.declineTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(mode == .approve ? JobApprovalText.approve : JobApprovalText.decline) { Task { await submit() } }
                        .disabled(working || !allowed)
                }
            }
        }
    }

    private var allowed: Bool {
        mode == .approve ? JobApprovalText.canApprove(job: job, rateText: rate) : JobApprovalText.canDecline(reason: reason)
    }

    private func submit() async {
        guard let repository = model.repository, allowed else { return }
        working = true
        defer { working = false }
        do {
            let request = mode == .approve
                ? try OwnerAPI.approveJob(job.id, hourlyRate: JobApprovalText.rateToSend(job: job, text: rate) ?? nil,
                                          idempotencyKey: idempotencyKey)
                : try OwnerAPI.declineJob(job.id, reason: reason, idempotencyKey: idempotencyKey)
            let updated = try await repository.send(request)
            dismiss()
            await done(updated, mode == .approve ? JobApprovalText.approved : JobApprovalText.declined)
        } catch {
            self.error = JobApprovalText.message(for: error)
            idempotencyKey = UUID() // a corrected retry is a new request
            model.handle(error)
            if JobApprovalText.needsReload(error) {
                dismiss()
                await done(job, JobApprovalText.alreadyDecided)
            }
        }
    }
}
#endif
