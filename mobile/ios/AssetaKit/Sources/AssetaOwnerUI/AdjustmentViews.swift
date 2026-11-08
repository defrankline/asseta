#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

// DEC-032 Phase 2 Owner screens: the extras of an adjustment request on the decision screen ("If approved" / "What it
// did", evidence) and the proposer's Withdraw card.

private typealias T = AdjustmentTexts

/// One evidence photo opened in a sheet.
private struct EvidenceRef: Identifiable { let id: UUID }

/// "If approved" / "What it did" and the evidence of one request.
struct AdjustmentRequestExtras: View {
    let model: OwnerModel
    let request: AdjustmentRequestDTO
    @State private var photo: EvidenceRef?

    var body: some View {
        let effects = AdjustmentPresentation.effects(request)
        Group {
            if !effects.isEmpty {
                Section(effects.title) {
                    if let refused = effects.refused { Text(refused).font(.footnote).foregroundStyle(Palette.warning) }
                    ForEach(effects.rows, id: \.self) { field in
                        LabeledContent(field.label) { Text(field.value).multilineTextAlignment(.trailing) }
                    }
                }
            }
            if !request.evidenceAttachmentIDs.isEmpty {
                Section(T.evidence) {
                    ForEach(Array(request.evidenceAttachmentIDs.enumerated()), id: \.offset) { index, id in
                        PhotoButton(label: "\(T.evidence.lowercased()) \(index + 1)", isOnline: model.isOnline) { photo = EvidenceRef(id: id) }
                    }
                }
            }
        }
        .sheet(item: $photo) { EvidencePhotoView(model: model, title: T.evidence, request: OwnerAPI.attachmentURL($0.id)) }
    }
}

/// The proposer takes a waiting request back, with a reason.
struct AdjustmentWithdrawSection: View {
    let model: OwnerModel
    let requestID: UUID
    let showingCachedData: Bool
    let onDone: (JSONValue) async -> Void
    @State private var reason = ""
    @State private var working = false
    @State private var error: String?
    @State private var confirm = false

    var body: some View {
        let block = model.mutationBlock(permitted: true, showingCachedData: showingCachedData)
        Section {
            if let block {
                BlockedNote(block: block)
            } else {
                TextField(T.withdrawLabel, text: Binding(get: { reason }, set: { reason = String($0.prefix(AdjustmentRules.withdrawMax)) }), axis: .vertical)
                    .lineLimit(2...5).accessibilityIdentifier("adjustment.withdrawReason")
                Button(T.withdraw, role: .destructive) { confirm = true }
                    .buttonStyle(.bordered).disabled(working || !AdjustmentRules.canWithdraw(reason: reason))
                    .accessibilityIdentifier("adjustment.withdraw")
                if let error { Text(error).font(.footnote).foregroundStyle(Palette.offline).accessibilityIdentifier("adjustment.error") }
            }
        } header: { Text(T.withdrawTitle) } footer: { Text(T.withdrawFooter) }
        .confirmationDialog(T.withdrawConfirm, isPresented: $confirm, titleVisibility: .visible) {
            Button(T.withdraw, role: .destructive) { Task { await withdraw() } }
        }
    }

    private func withdraw() async {
        guard let repository = model.repository, AdjustmentRules.canWithdraw(reason: reason), !working else { return }
        working = true
        defer { working = false }
        do {
            let result = try await repository.send(OwnerAPI.withdrawAdjustment(requestID, reason: reason, idempotencyKey: UUID()))
            error = nil
            reason = ""
            await onDone(result)
        } catch {
            self.error = AdjustmentRules.message(for: error)
            model.handle(error)
        }
    }
}
#endif
