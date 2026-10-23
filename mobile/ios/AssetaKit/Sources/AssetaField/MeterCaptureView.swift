#if os(iOS)
import AssetaCapture
import AssetaModel
import AssetaSync
import AVFoundation
import SwiftUI
import UIKit

/// Meter reading capture. The mode (AUTOMATIC camera + on-device OCR, or MANUAL entry) is set by
/// the policy snapshot and cannot be changed here.
struct MeterCaptureView: View {
    let model: FieldModel
    @State private var capture: MeterCaptureModel
    @State private var showCamera = false
    @State private var cameraDenied = false
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    init(model: FieldModel, job: FieldJob, kind: ReadingKind, snapshot: MeterPolicySnapshot) {
        self.model = model
        _capture = State(initialValue: MeterCaptureModel(job: job, kind: kind, snapshot: snapshot))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    LabeledContent("Machine", value: capture.job.machine.map { "\($0.assetCode) · \($0.name)" } ?? "—")
                    LabeledContent("Method", value: capture.draft.mode == .automatic ? "Camera + automatic reading" : "Manual entry")
                } footer: {
                    Text("Set by your company's capture rules (\(capture.snapshot.versionStamp)).")
                }
                photoSection
                readingSection
                gpsSection
                if !capture.issues.isEmpty && (capture.draft.hasPhoto || !capture.draft.readingText.isEmpty) {
                    Section {
                        ForEach(capture.issues, id: \.description) { Text($0.description).foregroundStyle(.orange) }
                    }
                }
            }
            .navigationTitle(capture.kind == .opening ? "Opening reading" : "Closing reading")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { capture.cancel(model: model); dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { if capture.save(model: model) { dismiss() } }
                        .disabled(!capture.issues.isEmpty || capture.isReadingPhoto)
                        .accessibilityIdentifier("capture.save")
                }
            }
            .task { await capture.locate(using: model.locator) }
            .fullScreenCover(isPresented: $showCamera) {
                CameraCaptureView { data in
                    showCamera = false
                    if let data { Task { await capture.photoTaken(data, model: model) } }
                }
                .ignoresSafeArea()
            }
            .alert("Camera access needed", isPresented: $cameraDenied) {
                Button("Open Settings") { if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) } }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Allow camera access in Settings to photograph the meter.")
            }
            .alert("Not saved", isPresented: Binding(get: { capture.errorMessage != nil },
                                                     set: { if !$0 { capture.errorMessage = nil } })) {
                Button("OK") { capture.errorMessage = nil }
            } message: { Text(capture.errorMessage ?? "") }
        }
        .interactiveDismissDisabled()
    }

    @ViewBuilder private var photoSection: some View {
        if capture.requirements.photoRequired || capture.draft.mode == .manual {
            Section {
                if let data = capture.photoData, let image = UIImage(data: data) {
                    Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 220)
                }
                if capture.isReadingPhoto {
                    ProgressView("Reading the meter on this phone…")
                } else if !(capture.draft.mode == .automatic && capture.decision.map(Self.isFinal) == true) {
                    Button(capture.draft.hasPhoto ? "Retake photo" : "Take photo", systemImage: "camera") { openCamera() }
                        .accessibilityIdentifier("capture.photo")
                }
                if case let .recapture(remaining)? = capture.decision {
                    Text("The reading could not be recognized reliably. Retake the photo (\(remaining) more after this).")
                        .foregroundStyle(.orange)
                }
            } header: {
                Text(capture.requirements.photoRequired ? "Meter photo (required)" : "Meter photo (optional)")
            }
        }
    }

    static func isFinal(_ decision: AutomaticDecision) -> Bool {
        if case .recapture = decision { false } else { true }
    }

    @ViewBuilder private var readingSection: some View {
        let showField = capture.draft.mode == .manual || capture.decision.map(Self.isFinal) == true
        if showField {
            Section {
                if case let .confirm(value, confidence)? = capture.decision {
                    LabeledContent("Recognized", value: value)
                    LabeledContent("Confidence", value: confidence.formatted(.percent.precision(.fractionLength(0))))
                    Text("Check the value against the meter. Correct it if it is wrong.").font(.footnote)
                }
                if case .manualEntry? = capture.decision {
                    Text("Automatic reading was not reliable after several photos. Type the reading; the photo is kept as evidence.")
                        .font(.footnote).foregroundStyle(.orange)
                }
                TextField(placeholder, text: $capture.draft.readingText)
                    .keyboardType(capture.requirements.decimalPlaces == 0 ? .numberPad : .decimalPad)
                    .font(.title2.monospacedDigit())
                    .accessibilityIdentifier("capture.reading")
                if capture.isCorrection {
                    Text("You changed the recognized value. It will be sent as a manual correction.").font(.footnote)
                }
                if capture.draft.mode == .automatic, case .confirm? = capture.decision {
                    Button("Retake photo", systemImage: "camera") { openCamera() }
                }
            } header: { Text("Reading (hours)") }
        }
    }

    private var placeholder: String {
        capture.requirements.decimalPlaces == 0 ? "e.g. 4521" : "e.g. 4521." + String(repeating: "0", count: capture.requirements.decimalPlaces)
    }

    @ViewBuilder private var gpsSection: some View {
        Section {
            switch capture.gpsState {
            case .locating:
                ProgressView("Getting a fresh location fix…")
            case let .done(result):
                if result.status == .fix, let lat = result.latitude, let lon = result.longitude {
                    LabeledContent("Location", value: String(format: "%.5f, %.5f", lat, lon))
                    LabeledContent("Accuracy", value: String(format: "± %.0f m", result.accuracyM ?? 0))
                } else {
                    Label(Self.describe(result.status), systemImage: "location.slash").foregroundStyle(.orange)
                    Text("The reading can still be saved; it is recorded with this location result for review.")
                        .font(.footnote)
                }
                Button("Try location again", systemImage: "location") { Task { await capture.locate(using: model.locator) } }
            }
        } header: { Text("GPS") }
    }

    static func describe(_ status: GpsStatus) -> String {
        switch status {
        case .fix: "Fix"
        case .noFix: "No GPS fix could be obtained"
        case .timeout: "No GPS fix within 20 seconds"
        case .permissionDenied: "Location permission denied"
        case .disabled: "Location services are turned off"
        }
    }

    private func openCamera() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: showCamera = true
        case .notDetermined:
            Task {
                if await AVCaptureDevice.requestAccess(for: .video) { showCamera = true } else { cameraDenied = true }
            }
        default: cameraDenied = true
        }
    }
}
#endif
