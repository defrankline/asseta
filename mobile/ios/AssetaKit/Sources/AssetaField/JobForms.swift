#if os(iOS)
import AssetaCapture
import AssetaModel
import AssetaSync
import PencilKit
import SwiftUI
import UIKit

/// Supervisor work log entry (`JOB_ACTIVITY`, device-generated `client_id`).
struct ActivityFormView: View {
    let model: FieldModel
    let job: FieldJob
    @Environment(\.dismiss) private var dismiss
    @State private var type: ActivityType = .work
    @State private var startedAt = Date()
    @State private var hasEnd = false
    @State private var endedAt = Date()
    @State private var billable: Bool?
    @State private var note = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Picker("Type", selection: $type) {
                    ForEach(ActivityType.allCases, id: \.self) { Text($0.rawValue.capitalized).tag($0) }
                }
                DatePicker("Started", selection: $startedAt)
                Toggle("Has ended", isOn: $hasEnd)
                if hasEnd { DatePicker("Ended", selection: $endedAt, in: startedAt...) }
                Picker("Billable", selection: $billable) {
                    Text("Contract default").tag(Bool?.none)
                    Text("Yes").tag(Bool?.some(true))
                    Text("No").tag(Bool?.some(false))
                }
                Section("Note (downtime reason, issue…)") {
                    TextEditor(text: $note).frame(minHeight: 100)
                }
                if let error { Text(error).foregroundStyle(.red) }
            }
            .navigationTitle("Work log entry")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save", action: save) }
            }
        }
    }

    private func save() {
        do {
            try model.perform {
                try $0.recordActivity(job: job.job, type: type, startedAt: startedAt, endedAt: hasEnd ? endedAt : nil,
                                      billable: billable, note: note)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}

/// Customer acknowledgement: typed name confirmation, or a signature drawn on the phone (PNG
/// stored as evidence and uploaded with purpose SIGNATURE). No external customer app.
struct AcknowledgementFormView: View {
    let model: FieldModel
    let job: FieldJob
    @Environment(\.dismiss) private var dismiss
    @State private var method: AcknowledgementMethod = .signature
    @State private var signerName = ""
    @State private var signerPhone = ""
    @State private var hours = ""
    @State private var canvas = PKCanvasView()
    @State private var hasInk = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Picker("Method", selection: $method) {
                    Text("Signature").tag(AcknowledgementMethod.signature)
                    Text("Name confirmation").tag(AcknowledgementMethod.nameConfirmation)
                }
                .pickerStyle(.segmented)
                TextField("Customer representative's name", text: $signerName).textContentType(.name)
                TextField("Phone (optional)", text: $signerPhone).keyboardType(.phonePad)
                TextField("Hours acknowledged (optional)", text: $hours).keyboardType(.decimalPad)
                if method == .signature {
                    Section {
                        SignaturePad(canvas: $canvas, hasInk: $hasInk)
                            .frame(height: 200)
                            .accessibilityIdentifier("ack.signature")
                        Button("Clear", role: .destructive) { canvas.drawing = PKDrawing(); hasInk = false }
                    } header: { Text("Signature") } footer: { Text("Ask the customer to sign with a finger.") }
                }
                if let error { Text(error).foregroundStyle(.red) }
            }
            .navigationTitle("Acknowledgement")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save).disabled(signerName.trimmingCharacters(in: .whitespaces).isEmpty
                                                          || (method == .signature && !hasInk))
                }
            }
        }
    }

    private func save() {
        var hoursValue: String?
        if !hours.trimmingCharacters(in: .whitespaces).isEmpty {
            guard case let .success(value) = CaptureValidator.normalizeReading(hours, decimalPlaces: 2) else {
                error = "Hours must be a number with at most 2 decimals."
                return
            }
            hoursValue = value
        }
        do {
            var signature: StoredEvidence?
            if method == .signature {
                guard let png = SignaturePad.png(from: canvas) else { error = "The signature could not be saved."; return }
                signature = try model.storeEvidence(png, fileExtension: "png", contentType: "image/png")
            }
            try model.perform {
                try $0.recordAcknowledgement(job: job.job, method: method, signerName: signerName, signerPhone: signerPhone,
                                             signature: signature, acknowledgedHours: hoursValue)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}

/// PencilKit drawing surface (finger input allowed).
struct SignaturePad: UIViewRepresentable {
    @Binding var canvas: PKCanvasView
    @Binding var hasInk: Bool

    func makeUIView(context: Context) -> PKCanvasView {
        canvas.drawingPolicy = .anyInput
        canvas.tool = PKInkingTool(.pen, color: .black, width: 4)
        canvas.backgroundColor = .white
        canvas.overrideUserInterfaceStyle = .light
        canvas.delegate = context.coordinator
        return canvas
    }

    func updateUIView(_ view: PKCanvasView, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(hasInk: $hasInk) }

    final class Coordinator: NSObject, PKCanvasViewDelegate {
        let hasInk: Binding<Bool>
        init(hasInk: Binding<Bool>) { self.hasInk = hasInk }
        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            hasInk.wrappedValue = !canvasView.drawing.strokes.isEmpty
        }
    }

    /// Black ink on white, PNG.
    @MainActor static func png(from canvas: PKCanvasView) -> Data? {
        let bounds = canvas.bounds
        guard bounds.width > 0, bounds.height > 0, !canvas.drawing.strokes.isEmpty else { return nil }
        let ink = canvas.drawing.image(from: bounds, scale: 2)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 2
        let image = UIGraphicsImageRenderer(size: bounds.size, format: format).image { context in
            UIColor.white.setFill()
            context.fill(CGRect(origin: .zero, size: bounds.size))
            ink.draw(in: CGRect(origin: .zero, size: bounds.size))
        }
        return image.pngData()
    }
}
#endif
