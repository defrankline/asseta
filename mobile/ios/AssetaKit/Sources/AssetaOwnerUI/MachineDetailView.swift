#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import MapKit
import SwiftUI

/// Machine drilldown: status dimensions, last seen, current job, recent alerts and readings (with
/// evidence photos on demand) and the last 24 h track as a polyline.
struct MachineDetailView: View {
    let model: OwnerModel
    let machineID: UUID
    @State private var status = Loader<MachineMapDTO>()
    @State private var track = Loader<HistoryDTO>()
    @State private var alerts = Loader<Page<AlertDTO>>()
    @State private var readings = Loader<Page<MeterCaptureDTO>>()
    @State private var jobs = Loader<Page<JobDTO>>()

    var body: some View {
        List {
            if status.isFromCache {
                StaleBanner(fetchedAt: status.snapshot?.fetchedAt, isOnline: model.isOnline)
                    .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            }
            if let machine = status.value {
                statusSection(machine)
                trackSection(machine)
            } else if let error = status.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
            if model.features.jobs { jobSection }
            alertSection
            if model.features.meterEvidence { readingSection }
        }
        .navigationTitle(status.value.map { $0.assetCode } ?? "Machine")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async {
        let now = Date()
        async let a: Void = status.load(model, .machine(machineID), OwnerAPI.machine(machineID))
        async let b: Void = track.load(model, .machineTrack(machineID),
                                       OwnerAPI.history(machineID, from: now.addingTimeInterval(-86_400), to: now))
        async let c: Void = alerts.load(model, .machineAlerts(machineID), OwnerAPI.alerts(machineID: machineID, pageSize: 10))
        _ = await (a, b, c)
        if model.features.jobs {
            await jobs.load(model, .machineJobs(machineID),
                            OwnerAPI.jobs(status: .inProgress, machineID: machineID, pageSize: 5))
        }
        if model.features.meterEvidence {
            await readings.load(model, .machineReadings(machineID), OwnerAPI.meterCaptures(machineID: machineID))
        }
    }

    @ViewBuilder private func statusSection(_ machine: MachineMapDTO) -> some View {
        let style = FleetPresentation.style(for: machine, dataIsCached: status.isFromCache)
        Section {
            LabeledContent("Name", value: machine.name)
            LabeledContent("Connectivity") {
                Label(style.label, systemImage: style.systemImage).foregroundStyle(style.tone.color)
            }
            .accessibilityElement(children: .combine)
            LabeledContent("Reported work", value: humanize(machine.reportedWorkStatus))
            LabeledContent("Engine (observed)", value: machine.observedEngine.humanized)
            LabeledContent("Motion (observed)", value: machine.observedMotion.humanized)
            LabeledContent("Location", value: machine.locationCompliance.humanized)
            if let time = machine.positionTime {
                LabeledContent("Position time", value: time.shortStamp)
            }
            if let accuracy = machine.accuracyM {
                LabeledContent("Accuracy", value: "± \(Int(accuracy.rounded())) m")
            }
            if let supervisor = machine.supervisor { LabeledContent("Supervisor", value: supervisor) }
            if let op = machine.operator { LabeledContent("Operator", value: op) }
            LabeledContent("Machine status", value: humanize(machine.machineStatus))
        } header: {
            Text("Status")
        } footer: {
            Text("Engine and motion are observed from tracker telemetry; reported work comes from the field team.")
        }
    }

    @ViewBuilder private func trackSection(_ machine: MachineMapDTO) -> some View {
        Section {
            let points = (track.value?.points ?? []).map {
                CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude)
            }
            if points.isEmpty && !machine.hasPosition {
                Text("No positions in the last 24 hours.").foregroundStyle(.secondary)
            } else {
                Map(initialPosition: .automatic) {
                    if points.count > 1 { MapPolyline(coordinates: points).stroke(Brand.amber, lineWidth: 4) }
                    if let lat = machine.latitude, let lon = machine.longitude {
                        let style = FleetPresentation.style(for: machine, dataIsCached: status.isFromCache)
                        Annotation(machine.assetCode, coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon)) {
                            MachineMarker(style: style, alerts: 0)
                        }
                    }
                }
                .frame(height: 240)
                .listRowInsets(EdgeInsets())
                .accessibilityLabel("Map of the last 24 hours: \(points.count) positions")
            }
            if let history = track.value {
                LabeledContent("Distance (24 h)", value: OwnerFormat.kilometres(history.distanceKm))
                LabeledContent("Stops", value: "\(history.stops.count)")
                if history.truncated {
                    Text("Track shortened by the server; some points are not shown.").font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        } header: {
            Text("Last 24 hours")
        }
    }

    @ViewBuilder private var jobSection: some View {
        Section("Current job") {
            if let job = jobs.value?.items.first {
                NavigationLink(value: OwnerRoute.job(job.id)) { JobRow(job: job) }
            } else {
                Text(jobs.value == nil ? "—" : "No job in progress.").foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder private var alertSection: some View {
        Section("Recent alerts") {
            let items = alerts.value?.items ?? []
            if items.isEmpty {
                Text(alerts.value == nil ? "—" : "No alerts.").foregroundStyle(.secondary)
            }
            ForEach(items) { alert in
                NavigationLink(value: OwnerRoute.alert(alert.id)) { AlertRow(alert: alert) }
            }
        }
    }

    @ViewBuilder private var readingSection: some View {
        Section {
            let items = readings.value?.items ?? []
            if items.isEmpty {
                Text(readings.value == nil ? "—" : "No readings yet.").foregroundStyle(.secondary)
            }
            ForEach(items) { capture in ReadingRow(model: model, capture: capture) }
        } header: {
            Text("Recent meter readings")
        } footer: {
            Text("Evidence photos are downloaded only when you open them and are never saved on this phone.")
        }
    }

    private func humanize(_ raw: String) -> String {
        raw.split(separator: "_").map { $0.lowercased() }.joined(separator: " ").capitalizedFirst
    }
}

struct ReadingRow: View {
    let model: OwnerModel
    let capture: MeterCaptureDTO
    @State private var showPhoto = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("\(capture.kind == .opening ? "Opening" : "Closing") · \(capture.reading.description)")
                    .font(.headline)
                Spacer()
                Pill(text: capture.state.capitalized, color: capture.state == "ACCEPTED" ? .green : .orange)
            }
            Text("\(capture.capturedAt.shortStamp) · \(capture.captureMode.capitalized)"
                + (capture.manuallyCorrected ? " · corrected by hand" : "") + " · GPS \(capture.gpsStatus.rawValue)")
                .font(.caption).foregroundStyle(.secondary)
            if capture.photoAttachmentID != nil {
                Button { showPhoto = true } label: { Label("View evidence photo", systemImage: "photo") }
                    .font(.subheadline)
                    .disabled(!model.isOnline)
                    .accessibilityHint(model.isOnline ? "Downloads the photo" : "Needs a connection")
            }
        }
        .sheet(isPresented: $showPhoto) {
            if let id = capture.photoAttachmentID {
                EvidencePhotoView(model: model, attachmentID: id, title: "\(capture.kind.rawValue.capitalized) reading")
            }
        }
    }
}

/// Downloads an evidence photo through a fresh presigned URL into memory only (ephemeral session,
/// no URL cache, nothing written to disk).
struct EvidencePhotoView: View {
    let model: OwnerModel
    let attachmentID: UUID
    let title: String
    @State private var image: UIImage?
    @State private var error: String?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if let image {
                    ScrollView([.horizontal, .vertical]) {
                        Image(uiImage: image).resizable().scaledToFit()
                            .accessibilityLabel("Evidence photo of the meter reading")
                    }
                } else if let error {
                    ContentUnavailableView("Photo unavailable", systemImage: "photo", description: Text(error))
                } else {
                    ProgressView("Downloading…")
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
        .task { await load() }
    }

    private func load() async {
        guard let repository = model.repository else { return }
        do {
            let link = try await repository.send(OwnerAPI.attachmentURL(attachmentID))
            let (data, response) = try await URLSessionTransport.makeDefaultSession().data(from: link.url)
            guard (response as? HTTPURLResponse)?.statusCode == 200, let picture = UIImage(data: data) else {
                error = "The photo could not be read."
                return
            }
            image = picture
        } catch {
            self.error = DecisionErrorText.message(for: error)
        }
    }
}

extension String {
    var capitalizedFirst: String { prefix(1).uppercased() + dropFirst() }
}
#endif
