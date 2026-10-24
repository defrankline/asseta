#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

/// Readings tab: every reading of mine (newest first) with one combined status, and my meter reset
/// requests (same as Android `ReadingsScreen`).
struct ReadingsTabView: View {
    let model: FieldModel
    @State private var attentionOnly = false

    var body: some View {
        let readings = model.inbox.readings.filter { !attentionOnly || $0.status.needsAttention }
        let resets = model.inbox.resets.filter { !attentionOnly || $0.status.needsAttention }
        List {
            FilterChips(options: [(false, "All"), (true, "Needs attention")], selection: $attentionOnly)
            if readings.isEmpty && resets.isEmpty {
                if attentionOnly {
                    ContentUnavailableView("Nothing needs attention", systemImage: "checkmark.circle",
                                           description: Text("Flagged or rejected readings appear here."))
                } else {
                    ContentUnavailableView("No readings yet", systemImage: "gauge.with.dots.needle.33percent",
                                           description: Text("Readings you capture on your jobs appear here with the office's review."))
                }
            }
            if !readings.isEmpty {
                Section("My readings") {
                    ForEach(readings) { reading in
                        NavigationLink(value: FieldRoute.reading(reading.id)) { ReadingRow(inbox: model.inbox, reading: reading) }
                    }
                }
            }
            if !resets.isEmpty {
                Section("Meter reset requests") {
                    ForEach(resets) { reset in
                        NavigationLink(value: FieldRoute.resetDetail(reset.id)) { ResetRow(inbox: model.inbox, reset: reset) }
                    }
                }
            }
        }
        .refreshable { await model.sync(force: true) }
    }
}

struct ReadingRow: View {
    let inbox: InboxSnapshot
    let reading: ReadingItem

    var body: some View {
        let job = reading.jobID.flatMap { inbox.jobs[$0]?.jobNumber }
        let machine = inbox.machine(of: reading).flatMap { inbox.machines[$0]?.assetCode }
        InboxRow([job, InboxTexts.readingKind(reading.kind)].compactMap { $0 }.joined(separator: " · "), reading.status,
                 [reading.reading, machine].compactMap { $0 }.joined(separator: " · "),
                 reading.at.listText + (reading.openFindings > 0 ? " · \(reading.openFindings) open finding(s)" : ""))
    }
}

struct ResetRow: View {
    let inbox: InboxSnapshot
    let reset: ResetItem

    var body: some View {
        InboxRow(reset.machineID.flatMap { inbox.machines[$0]?.assetCode } ?? "Meter reset", reset.status,
                 "\(reset.oldReading) → \(reset.newReading)", reset.at.listText)
    }
}

/// One reading: photo, camera vs entered, GPS, findings with review, sync state; "Request meter reset".
struct ReadingDetailView: View {
    let model: FieldModel
    let id: UUID
    let requestReset: (UUID, String?) -> Void

    var body: some View {
        if let reading = model.inbox.readings.first(where: { $0.id == id }) {
            content(reading).navigationTitle("Reading")
        } else {
            ContentUnavailableView("Reading not available", systemImage: "questionmark.folder",
                                   description: Text("It is no longer on this phone."))
        }
    }

    private func content(_ r: ReadingItem) -> some View {
        let s = r.server
        let p = r.localPayload
        let machine = model.inbox.machine(of: r).flatMap { model.inbox.machines[$0] }
        let ocr = s?.ocrValue ?? p?["ocr_value"]?.stringValue
        let gps = p?["gps"]
        let files = r.op.map { model.evidenceFiles(of: $0) } ?? []
        let online = model.online
        return List {
            Section {
                LabeledContent("Status") { StatusPill(status: r.status) }
                LabeledContent(InboxTexts.readingKind(r.kind), value: r.reading)
                if let jobID = r.jobID, let job = model.inbox.jobs[jobID] { LabeledContent("Job", value: job.jobNumber) }
                if let machine { LabeledContent("Machine", value: InboxTexts.machine(machine.assetCode, machine.name)) }
                LabeledContent("Captured", value: r.at.listText)
                LabeledContent("Capture mode", value: InboxTexts.captureMode(r.captureMode))
            }
            Section("Photo") {
                if files.isEmpty && s?.photoAttachmentID == nil {
                    Text("No photo with this reading.").font(.footnote).foregroundStyle(.secondary)
                } else {
                    EvidenceImage(description: "Meter photo",
                                  local: files.isEmpty ? nil : { files.lazy.compactMap { model.localEvidence($0) }.first },
                                  remote: s?.photoAttachmentID.map { id in { await online?.attachmentURL(id) } })
                }
            }
            Section {
                LabeledContent("Read by camera", value: ocr ?? "—")
                if let confidence = InboxTexts.confidence(s?.ocrConfidence ?? p?["ocr_confidence"]?.doubleValue) {
                    LabeledContent("Confidence", value: confidence)
                }
                LabeledContent("Entered", value: r.reading)
                if s?.manuallyCorrected == true || (ocr != nil && ocr != r.reading) {
                    LabeledContent("Corrected by hand") { Text("Yes").foregroundStyle(Palette.warning) }
                }
            } header: { Text("Camera reading") } footer: {
                if ocr == nil { Text("Typed in; the camera did not read this meter.") }
            }
            Section("GPS") {
                if let status = s?.gpsStatus ?? gps?["status"]?.stringValue {
                    Text(InboxTexts.gps(status: status, latitude: s?.latitude ?? gps?["latitude"]?.doubleValue,
                                        longitude: s?.longitude ?? gps?["longitude"]?.doubleValue,
                                        accuracyM: s?.accuracyM ?? gps?["accuracy_m"]?.doubleValue))
                        .font(.subheadline)
                }
            }
            Section {
                if s == nil {
                    Text("The office's review appears here after the reading is synced.").font(.footnote).foregroundStyle(.secondary)
                }
                ForEach(r.findings) { f in
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Text(FindingTexts.type(f.exceptionType)).font(.headline)
                            Spacer()
                            Pill(text: FindingTexts.review(f.status), color: f.status == "OPEN" ? Palette.warning : Palette.recent)
                        }
                        Text("Severity: \(FindingTexts.severity(f.severity))" + (f.blocking ? " · Blocking" : ""))
                            .font(.footnote).foregroundStyle(f.blocking ? Palette.offline : .secondary)
                        if let note = f.reviewNote { Text("Office note: \(note)").font(.subheadline) }
                        if let at = f.reviewedAt { Text("Reviewed \(at.listText)").font(.caption).foregroundStyle(.secondary) }
                    }
                }
            } header: { Text("Review") } footer: { Text(InboxTexts.reviewOutcome(s?.reviewStatus, findings: r.findings.count)) }
            SyncSection(operation: r.op)
            if let machine {
                Section {
                    Button("Request meter reset", systemImage: "wrench.and.screwdriver") { requestReset(machine.id, r.reading) }
                    NavigationLink(value: FieldRoute.machine(machine.id)) { Label("Machine \(machine.assetCode)", systemImage: "gauge.with.dots.needle.33percent") }
                }
            }
        }
    }
}

/// A machine of mine: latest reading, active job, my readings and reset requests; "Request meter reset".
struct MachineDetailView: View {
    let model: FieldModel
    let machineID: UUID
    let requestReset: (UUID, String?) -> Void

    var body: some View {
        if let machine = model.inbox.machines[machineID] {
            let inbox = model.inbox
            let readings = inbox.readings.filter { inbox.machine(of: $0) == machineID }
            let latest = inbox.latestReadingByMachine()[machineID]
            let jobs = inbox.jobs.values.filter { $0.machineID == machineID && [.inProgress, .approved].contains($0.status) }
            let resets = inbox.resets.filter { $0.machineID == machineID }
            List {
                Section {
                    LabeledContent("Machine", value: InboxTexts.machine(machine.assetCode, machine.name))
                    LabeledContent("Latest reading", value: latest.map { "\($0.reading) · \($0.at.listText)" } ?? "No readings yet")
                    LabeledContent("Meter precision", value: machine.meterDecimalPlaces == 0 ? "Whole hours"
                                   : "\(machine.meterDecimalPlaces) decimal place(s)")
                }
                if !jobs.isEmpty {
                    Section("Active job") {
                        ForEach(jobs, id: \.id) { job in
                            NavigationLink(value: FieldRoute.job(job.id)) {
                                LabeledContent(job.jobNumber, value: job.status == .inProgress ? "In progress" : "Approved")
                            }
                        }
                    }
                }
                Section {
                    Button("Request meter reset", systemImage: "wrench.and.screwdriver") { requestReset(machineID, latest?.reading) }
                }
                if !readings.isEmpty {
                    Section("My readings") {
                        ForEach(readings) { r in NavigationLink(value: FieldRoute.reading(r.id)) { ReadingRow(inbox: inbox, reading: r) } }
                    }
                }
                if !resets.isEmpty {
                    Section("Meter reset requests") {
                        ForEach(resets) { r in NavigationLink(value: FieldRoute.resetDetail(r.id)) { ResetRow(inbox: inbox, reset: r) } }
                    }
                }
            }
            .navigationTitle(machine.assetCode)
        } else {
            ContentUnavailableView("Machine not available", systemImage: "questionmark.folder",
                                   description: Text("It is no longer assigned to you on this device."))
        }
    }
}

/// One meter reset request: readings, reason, evidence, the office's decision and sync state.
struct ResetDetailView: View {
    let model: FieldModel
    let id: UUID

    var body: some View {
        if let r = model.inbox.resets.first(where: { $0.id == id }) {
            let machine = r.machineID.flatMap { model.inbox.machines[$0] }
            let files = r.op.map { model.evidenceFiles(of: $0) } ?? []
            let online = model.online
            List {
                Section {
                    LabeledContent("Status") { StatusPill(status: r.status) }
                    LabeledContent("Machine", value: machine.map { InboxTexts.machine($0.assetCode, $0.name) } ?? "Machine")
                    LabeledContent("Reading before", value: r.oldReading)
                    LabeledContent("Reading after", value: r.newReading)
                    LabeledContent("Effective", value: r.effectiveAt.listText)
                    if let decided = r.decidedAt { LabeledContent("Decided", value: decided.listText) }
                }
                Section("Reason") { Text(r.reason).font(.subheadline) }
                if r.hasEvidence {
                    Section("Evidence photo") {
                        EvidenceImage(description: "Meter reset evidence",
                                      local: files.isEmpty ? nil : { files.lazy.compactMap { model.localEvidence($0) }.first },
                                      remote: r.server?.evidenceAttachmentID.map { id in { await online?.attachmentURL(id) } })
                    }
                }
                SyncSection(operation: r.op)
                if let machine {
                    Section {
                        NavigationLink(value: FieldRoute.machine(machine.id)) {
                            Label("Machine \(machine.assetCode)", systemImage: "gauge.with.dots.needle.33percent")
                        }
                    }
                }
            }
            .navigationTitle("Meter reset")
        } else {
            ContentUnavailableView("Reset request not available", systemImage: "questionmark.folder",
                                   description: Text("It is no longer on this phone."))
        }
    }
}

/// Request a meter reset (`METER_RESET_REQUEST`): readings before/after, reason and an evidence photo.
struct ResetRequestFormView: View {
    let model: FieldModel
    let machineID: UUID
    @State private var oldReading: String
    @State private var newReading = ""
    @State private var reason = ""
    @State private var photo: StoredEvidence?
    @State private var photoData: Data?
    @State private var clientID = UUID()
    @State private var showCamera = false
    @State private var cameraDenied = false
    @State private var error: String?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    init(model: FieldModel, machineID: UUID, oldReading: String?) {
        self.model = model
        self.machineID = machineID
        _oldReading = State(initialValue: oldReading ?? "")
    }

    var body: some View {
        let unavailable = model.meterResetUnavailable()
        let machine = model.inbox.machines[machineID]
        NavigationStack {
            Form {
                if let unavailable {
                    ContentUnavailableView("Meter reset not available", systemImage: "exclamationmark.triangle",
                                           description: Text(unavailable))
                }
                Section {
                    LabeledContent("Machine", value: machine.map { InboxTexts.machine($0.assetCode, $0.name) } ?? "Machine")
                } footer: { Text("The office approves or rejects the reset. Until then readings continue from the old meter.") }
                Section("Readings") {
                    TextField("Reading before the reset", text: $oldReading).keyboardType(.decimalPad)
                    TextField("Reading after the reset", text: $newReading).keyboardType(.decimalPad)
                }
                Section {
                    TextField("Reason", text: $reason, axis: .vertical)
                } header: { Text("Reason") } footer: { Text("At least 10 characters, e.g. \"Meter replaced by the workshop\".") }
                Section {
                    if let photoData, let image = UIImage(data: photoData) {
                        HStack {
                            Image(uiImage: image).resizable().scaledToFit().frame(height: 160)
                            Spacer()
                            Button("Remove", role: .destructive) { removePhoto() }.buttonStyle(.borderless)
                        }
                    } else {
                        Button("Photograph meter", systemImage: "camera") {
                            Task { if await CameraAccess.request() { showCamera = true } else { cameraDenied = true } }
                        }
                    }
                } header: { Text("Evidence photo (required)") } footer: {
                    Text("Stored encrypted on this phone and uploaded before the request is sent.")
                }
            }
            .disabled(unavailable != nil)
            .navigationTitle("Request meter reset")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { removePhoto(); dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save") { save() }.disabled(unavailable != nil) }
            }
            .fullScreenCover(isPresented: $showCamera) {
                CameraCaptureView { data in
                    showCamera = false
                    if let data { photoTaken(data) }
                }
                .ignoresSafeArea()
            }
            .alert("Camera access needed", isPresented: $cameraDenied) {
                Button("Open Settings") { if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) } }
                Button("Cancel", role: .cancel) {}
            } message: { Text("Allow camera access in Settings to photograph the meter.") }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        }
        .interactiveDismissDisabled()
    }

    private func photoTaken(_ data: Data) {
        do {
            removePhoto()
            photo = try model.storeEvidence(data, fileExtension: "jpg", contentType: "image/jpeg")
            photoData = data
        } catch {
            self.error = "The photo could not be saved: \(error)"
        }
    }

    private func removePhoto() {
        if let photo { model.discardEvidence(photo) }
        photo = nil
        photoData = nil
    }

    private func save() {
        let issues = ResetRules.validate(oldReading: oldReading, newReading: newReading, reason: reason, hasPhoto: photo != nil)
        if !issues.isEmpty {
            error = issues.joined(separator: "\n")
            return
        }
        do {
            try model.perform {
                try $0.requestMeterReset(machineID: machineID, oldReading: oldReading, newReading: newReading, reason: reason,
                                         photo: photo, effectiveAt: Date(), clientID: clientID)
            }
            photo = nil // now owned by the queued request
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}

extension FieldModel {
    /// Why reset requests cannot be recorded (server without the capability, never synced), or nil.
    func meterResetUnavailable() -> String? { services?.recorder.meterResetUnavailable() }
}
#endif
