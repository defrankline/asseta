#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

/// One job: details, a summary (readings, meter hours, work totals, findings), the next allowed
/// actions, my readings, the work log (server + this phone), the customer acknowledgement, expenses &
/// fuel, and the local timeline with sync states (same sections as Android `JobDetailScreen`).
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
                JobSummarySection(inbox: model.inbox, jobID: jobID)
                actions(job, progress)
                JobReadingsSection(inbox: model.inbox, jobID: jobID)
                workLog(job, canLog: progress.canLogActivity)
                AcknowledgementSection(model: model, jobID: jobID)
                JobMoneySection(inbox: model.inbox, jobID: jobID)
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
            if let request = job.request {
                LabeledContent("Status") { RequestBadge(state: request) }
                if case let .declined(reason?) = request { LabeledContent("Reason", value: reason) }
            } else {
                LabeledContent("Status") { StatusBadge(status: progress.displayStatus, pendingSync: progress.displayStatus != job.job.status) }
            }
            if let machine = job.machine {
                LabeledContent("Machine", value: "\(machine.assetCode) · \(machine.name)")
                LabeledContent("Meter precision", value: machine.meterDecimalPlaces == 0 ? "Whole hours" : "\(machine.meterDecimalPlaces) decimal place(s)")
            }
            if let site = job.site { LabeledContent("Site", value: site.name) }
            if let customer = job.customer { LabeledContent("Customer", value: customer.name) }
            LabeledContent("Planned start", value: job.job.plannedStart.formatted(date: .abbreviated, time: .shortened))
            if let end = job.job.plannedEnd {
                LabeledContent("Planned end", value: end.formatted(date: .abbreviated, time: .shortened))
            }
            if let note = job.job.requestNote { LabeledContent(JobRequestText.note, value: note) }
        }
    }

    @ViewBuilder private func actions(_ job: FieldJob, _ progress: JobProgress) -> some View {
        Section {
            let gate = model.gate(job)
            if case let .blocked(reason) = gate, progress.canCaptureOpening || progress.canCaptureClosing {
                Label(reason.message, systemImage: "lock.trianglebadge.exclamationmark")
                    .foregroundStyle(Palette.warning).font(.footnote)
                    .accessibilityIdentifier("capture.blocked")
            }
            if progress.canCaptureOpening {
                actionButton("Capture opening reading", "gauge.with.dots.needle.0percent", enabled: gate.isAllowed) { capture = .opening }
            }
            if progress.canStart {
                actionButton("Start job", "play.fill") { confirmAction = .start }
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

    /// Work log: timed entries (start/stop on this phone) and the form for earlier or untimed entries.
    @ViewBuilder private func workLog(_ job: FieldJob, canLog: Bool) -> some View {
        let entries = model.inbox.activities.filter { $0.jobID == job.id }
        if !entries.isEmpty || canLog {
            Section {
                ForEach(entries) { entry in
                    HStack {
                        Text(Self.describe(entry)).font(.subheadline)
                        Spacer()
                        if !entry.running { StatusPill(status: entry.status) }
                    }
                }
                if canLog { workLogActions(job) }
            } header: { Text("Work log") } footer: {
                if !entries.isEmpty { Text("Entries recorded on this phone and those the server has.") }
            }
        }
    }

    @ViewBuilder private func workLogActions(_ job: FieldJob) -> some View {
        Group {
            if let running = model.runningEntry(for: job) {
                actionButton("Stop \(running.activityType.rawValue.lowercased())", "stop.circle") {
                    record { try $0.stopEntry(job: job.job) }
                }
            } else {
                actionButton("Start work", "play.circle") { startEntry(job, .work) }
                actionButton("Standby", "pause.circle") { startEntry(job, .standby) }
                actionButton("Downtime", "wrench.and.screwdriver") { startEntry(job, .downtime) }
            }
            actionButton("Add work log entry", "list.bullet.clipboard") { showActivity = true }
        }
    }

    /// "Work 08:00 → 10:30 (2 h 30 min) · note" (or "→ running" while the entry is open).
    static func describe(_ entry: ActivityItem) -> String {
        let time = Date.FormatStyle(date: .omitted, time: .shortened)
        var text = "\(InboxTexts.activityType(entry.activityType)) \(entry.start.formatted(time))"
        if let end = entry.end {
            text += " → \(end.formatted(time)) (\(JobFigures.duration(minutes: Int(end.timeIntervalSince(entry.start)) / 60)))"
        } else if entry.running { text += " → running" }
        if let note = entry.note { text += " · \(note)" }
        return text
    }

    private func startEntry(_ job: FieldJob, _ type: ActivityType) {
        record { try $0.startEntry(job: job.job, type: type, startedAt: Date(), note: nil) }
    }

    /// "Work 08:00 → 10:30 · note" (or "→ running" while the entry is open).
    static func describe(_ line: WorkLogLine) -> String {
        let time = Date.FormatStyle(date: .omitted, time: .shortened)
        var text = "\(line.type.rawValue.capitalized) \(line.startedAt.formatted(time))"
        if let end = line.endedAt { text += " → \(end.formatted(time))" } else if line.isRunning { text += " → running" }
        if let note = line.note { text += " · \(note)" }
        return text
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
        record { try $0.recordTransition(job: job.job, action: action) }
    }

    private func record(_ action: (FieldRecorder) throws -> Void) {
        do {
            try model.perform(action)
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
                Text("\(code): \(operation.lastError ?? "")").font(.caption).foregroundStyle(Palette.offline)
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
             .meterBaseline, .meterCorrection, nil: return operation.opType
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
