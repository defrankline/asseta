#if os(iOS)
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

/// One job: details, the next allowed actions and the local timeline with sync states.
struct JobDetailView: View {
    let model: FieldModel
    let jobID: UUID
    @State private var capture: ReadingKind?
    @State private var showActivity = false
    @State private var showAcknowledgement = false
    @State private var confirmAction: JobAction?
    @State private var error: String?

    var body: some View {
        if let job = model.job(jobID) {
            let progress = model.progress(job)
            List {
                details(job, progress)
                actions(job, progress)
                timeline(job)
            }
            .navigationTitle(job.job.jobNumber)
            .sheet(item: $capture) { kind in
                if case let .allowed(snapshot) = model.gate(job) {
                    MeterCaptureView(model: model, job: job, kind: kind, snapshot: snapshot)
                }
            }
            .sheet(isPresented: $showActivity) { ActivityFormView(model: model, job: job) }
            .sheet(isPresented: $showAcknowledgement) { AcknowledgementFormView(model: model, job: job) }
            .confirmationDialog(confirmAction == .start ? "Start this job?" : "Complete this job?",
                                isPresented: Binding(get: { confirmAction != nil }, set: { if !$0 { confirmAction = nil } }),
                                titleVisibility: .visible) {
                Button(confirmAction == .start ? "Start job" : "Complete job") {
                    if let action = confirmAction { transition(job, action) }
                }
            } message: {
                Text("This is recorded now with the phone's time and synced when possible.")
            }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        } else {
            ContentUnavailableView("Job not available", systemImage: "questionmark.folder",
                                   description: Text("It is no longer assigned to you on this device."))
        }
    }

    private func details(_ job: FieldJob, _ progress: JobProgress) -> some View {
        Section {
            LabeledContent("Status") { StatusBadge(status: progress.displayStatus, pendingSync: progress.displayStatus != job.job.status) }
            if let machine = job.machine {
                LabeledContent("Machine", value: "\(machine.assetCode) · \(machine.name)")
                LabeledContent("Meter precision", value: machine.meterDecimalPlaces == 0 ? "Whole hours" : "\(machine.meterDecimalPlaces) decimal place(s)")
            }
            if let site = job.site { LabeledContent("Site", value: site.name) }
            if let customer = job.customer { LabeledContent("Customer", value: customer.name) }
            LabeledContent("Planned start", value: job.job.plannedStart.formatted(date: .abbreviated, time: .shortened))
        }
    }

    @ViewBuilder private func actions(_ job: FieldJob, _ progress: JobProgress) -> some View {
        Section {
            let gate = model.gate(job)
            if case let .blocked(reason) = gate, progress.canCaptureOpening || progress.canCaptureClosing {
                Label(reason.message, systemImage: "lock.trianglebadge.exclamationmark")
                    .foregroundStyle(.orange).font(.footnote)
                    .accessibilityIdentifier("capture.blocked")
            }
            if progress.canCaptureOpening {
                actionButton("Capture opening reading", "gauge.with.dots.needle.0percent", enabled: gate.isAllowed) { capture = .opening }
            }
            if progress.canStart {
                actionButton("Start job", "play.fill") { confirmAction = .start }
            }
            if progress.canLogActivity {
                actionButton("Add work log entry", "list.bullet.clipboard") { showActivity = true }
            }
            if progress.canCaptureClosing {
                actionButton("Capture closing reading", "gauge.with.dots.needle.100percent", enabled: gate.isAllowed) { capture = .closing }
            }
            if progress.canAcknowledge {
                actionButton("Customer acknowledgement", "signature") { showAcknowledgement = true }
            }
            if progress.canComplete {
                actionButton("Complete job", "checkmark.seal") { confirmAction = .complete }
            }
            if progress.isClosed {
                Text("No further actions on this job.").foregroundStyle(.secondary)
            }
        } header: { Text("Next steps") }
    }

    private func actionButton(_ title: String, _ icon: String, enabled: Bool = true, action: @escaping () -> Void) -> some View {
        Button(action: action) { Label(title, systemImage: icon) }
            .disabled(!enabled)
            .accessibilityIdentifier("action.\(title)")
    }

    @ViewBuilder private func timeline(_ job: FieldJob) -> some View {
        let operations = model.operations(for: job)
        if !operations.isEmpty {
            Section("Recorded on this phone") {
                ForEach(operations) { op in OperationRow(operation: op) }
            }
        }
    }

    private func transition(_ job: FieldJob, _ action: JobAction) {
        do {
            try model.perform { try $0.recordTransition(job: job.job, action: action) }
        } catch {
            self.error = Self.describe(error)
        }
    }

    static func describe(_ error: any Error) -> String {
        if case let FieldRecorderError.notAllowed(message) = error { return message }
        if case let FieldRecorderError.invalid(message) = error { return message }
        return String(describing: error)
    }
}

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
                Text("\(code): \(operation.lastError ?? "")").font(.caption).foregroundStyle(.red)
            }
        }
    }

    private var title: String {
        let payload = try? JSONValue.parse(operation.payloadJSON)
        switch OperationType(rawValue: operation.opType) {
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
        case nil: return operation.opType
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
        case .acked: .green
        case .failed, .conflict: .red
        case .quarantined: .orange
        default: .secondary
        }
    }
}
#endif
