#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

// DEC-032 Phase 3 Owner screens: a variance's investigation on the decision screen and the partial reason of a remittance.

private typealias T = VarianceTexts

/// One evidence photo opened in a sheet.
private struct VarianceEvidenceRef: Identifiable { let id: UUID }

/// Assignee, explanation, evidence and history of one variance.
struct VarianceExtras: View {
    let model: OwnerModel
    let variance: CashVarianceDTO
    @State private var photo: VarianceEvidenceRef?
    @State private var history = Loader<[VarianceEventDTO]>()

    var body: some View {
        let rows = VariancePresentation.investigation(variance)
        Group {
            if !rows.isEmpty {
                Section(T.explanation) {
                    ForEach(rows, id: \.self) { row in
                        LabeledContent(row.label) { Text(row.value).multilineTextAlignment(.trailing) }
                    }
                }
            }
            if !variance.evidence.isEmpty {
                Section(T.evidence) {
                    ForEach(Array(variance.evidence.enumerated()), id: \.offset) { index, id in
                        PhotoButton(label: "\(T.evidence.lowercased()) \(index + 1)", isOnline: model.isOnline) {
                            photo = VarianceEvidenceRef(id: id)
                        }
                    }
                }
            }
            // Best effort: hidden when it cannot be read.
            if let events = history.value, !events.isEmpty {
                Section(T.history) {
                    ForEach(events) { Text(VariancePresentation.historyRow($0)).font(.subheadline) }
                }
            }
        }
        .sheet(item: $photo) { EvidencePhotoView(model: model, title: T.evidence, request: OwnerAPI.attachmentURL($0.id)) }
        .task(id: model.changeTick) { await history.load(model, .varianceHistory(variance.id), OwnerAPI.cashVarianceHistory(variance.id)) }
    }
}

/// Why part of a remittance stayed with the custodian, and a link to decide it while it waits.
struct PartialReasonSection: View {
    let model: OwnerModel
    let handover: CashHandoverDTO

    var body: some View {
        let rows = HandoverText.partialRows(handover)
        if !rows.isEmpty {
            Section(T.remitPartialReason) {
                ForEach(rows, id: \.self) { row in
                    LabeledContent(row.label) { Text(row.value).multilineTextAlignment(.trailing) }
                }
                if handover.partialApproval?.status == VarianceStatuses.pendingReason, model.features.canDecide(.partialRemittance),
                   model.features.allows(.decision(.partialRemittance, handover.id)) {
                    NavigationLink(value: OwnerRoute.decision(.partialRemittance, handover.id)) {
                        Text(T.remitPartialReview).foregroundStyle(Color.accentColor)
                    }
                    .accessibilityIdentifier("handover.reviewReason")
                }
            }
        }
    }
}
#endif
