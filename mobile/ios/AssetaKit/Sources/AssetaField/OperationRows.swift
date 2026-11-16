#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

extension ReadingKind: Identifiable {
    public var id: String { rawValue }
}

extension CaptureGate {
    var isAllowed: Bool { if case .allowed = self { true } else { false } }
}

/// A local operation with its sync state.
struct OperationRow: View {
    let operation: ClientOperation

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(title).font(.subheadline)
                Spacer()
                SyncStateLabel(status: operation.status)
            }
            Text(operation.createdAtDevice.formatted(date: .abbreviated, time: .standard))
                .font(.caption).foregroundStyle(.secondary)
            if let code = operation.errorCode, operation.status != .pending {
                Text(FieldAccountabilityTexts.conflictText(code) ?? "\(code): \(operation.lastError ?? "")").font(.caption).foregroundStyle(Palette.offline)
            }
        }
    }

    private var title: String {
        let payload = try? JSONValue.parse(operation.payloadJSON)
        let type = OperationType(rawValue: operation.opType)
        if let type, let title = FieldAccountabilityTexts.operationTitle(type, payload: payload) { return title }
        switch type {
        case .meterCapture:
            let kind = payload?["kind"]?.stringValue == "OPENING" ? "Opening" : "Closing"
            return "\(kind) reading \(payload?["reading"]?.stringValue ?? "")"
        case .jobActivity: return "Work log: \(payload?["activity_type"]?.stringValue?.capitalized ?? "")"
        case .jobAcknowledgement: return "Acknowledged by \(payload?["signer_name"]?.stringValue ?? "")"
        case .jobTransition: return payload?["action"]?.stringValue == "START" ? "Job started" : "Job completed"
        case .expense: return "Expense \(payload?["amount"]?.stringValue ?? "")"
        case .fuelEvent:
            return "Fuel \(payload?["event_type"]?.stringValue?.lowercased() ?? ""): \(payload?["litres"]?.stringValue ?? "") L"
        case .cashCollection: return "Cash collection \(payload?["amount"]?.stringValue ?? "")"
        case .cashHandover: return "Cash handover \(payload?["amount"]?.stringValue ?? "")"
        case .meterResetRequest: return "Meter reset request"
        case .jobRequest: return JobRequestText.operation
        case .hoursPurchase, .hoursTransferRequest, .cashTransfer, .cashTransferAcknowledgement, .cashFloatAcknowledgement,
             .meterBaseline, .meterCorrection, .cashRetentionRequest, .siteCheckin, .dailyReport,
             .pettyCashAcknowledgement, .pettyCashTopUpRequest, .pettyCashReturn, .pettyCashCount,
             .pettyCashHolderChangeAcknowledgement, .pettyCashAdvanceClearance, .pettyCashAdvance,
             .machineReport, .creditInvoicePayment, nil: return operation.opType
        }
    }
}

struct SyncStateLabel: View {
    let status: ClientOperationStatus

    var body: some View {
        Label(text, systemImage: icon).labelStyle(.titleAndIcon).font(.caption.bold()).foregroundStyle(color)
    }

    private var text: String {
        switch status {
        case .pending: "Waiting to sync"
        case .sent: "Sending"
        case .acked: "Synced"
        case .failed: "Rejected"
        case .conflict: "Conflict"
        case .quarantined: "Held"
        }
    }

    private var icon: String {
        switch status {
        case .pending, .sent: "clock"
        case .acked: "checkmark.circle"
        case .failed: "xmark.octagon"
        case .conflict: "exclamationmark.triangle"
        case .quarantined: "pause.circle"
        }
    }

    private var color: Color {
        switch status {
        case .acked: Palette.live
        case .failed, .conflict: Palette.offline
        case .quarantined: Palette.warning
        default: .secondary
        }
    }
}
#endif
