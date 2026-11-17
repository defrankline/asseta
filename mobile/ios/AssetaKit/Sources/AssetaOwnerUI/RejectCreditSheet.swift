#if os(iOS)
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Reject credit (owner decision; Android `RejectCreditDialog`): the reason is required (at least 3 characters) and the
/// seller is told it. The credit invoice is cancelled and the credit hours never become usable; paid parts stay.
struct RejectCreditSheet: View {
    let sale: CreditSale
    let onReject: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var reason = ""

    var body: some View {
        let order = sale.purchase
        NavigationStack {
            Form {
                Section {
                    Text(ApprovalsTexts.rejectCreditMessage(
                        order.customerName ?? order.purchaseNumber,
                        OwnerFigures.money(order.creditAmount?.value ?? 0, currency: order.currency)
                            .trimmingCharacters(in: .whitespaces)))
                        .font(.system(size: 15))
                }
                Section {
                    TextField(ApprovalsTexts.rejectReasonLabel, text: $reason, axis: .vertical)
                        .lineLimit(2...5)
                        .accessibilityIdentifier("approvals.credit.rejectReason")
                } footer: {
                    Text(ApprovalsTexts.rejectReasonHint)
                }
            }
            .navigationTitle(ApprovalsTexts.rejectCreditTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(ApprovalsTexts.cancel) { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(ApprovalsTexts.rejectConfirm, role: .destructive) {
                        let text = reason.trimmingCharacters(in: .whitespacesAndNewlines)
                        dismiss()
                        onReject(text)
                    }
                    .disabled(!ApprovalsTexts.rejectReasonValid(reason))
                    .accessibilityIdentifier("approvals.credit.rejectConfirm")
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}
#endif
