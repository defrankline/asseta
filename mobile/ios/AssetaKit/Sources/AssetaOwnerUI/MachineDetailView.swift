#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import MapKit
import SwiftUI

/// Machine drilldown: status dimensions, last seen, current job, recent alerts and readings (with
/// evidence photos on demand) and the last 24 h track as a polyline. Rows and wording follow `MachineText`,
/// shared with the Android Owner app.
struct MachineDetailView: View {
    let model: OwnerModel
    let machineID: UUID
    @State private var status = Loader<MachineMapDTO>()
    @State private var info = Loader<OwnerMachineDTO>()
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
        .navigationTitle("Machine")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async {
        let now = Date()
        async let a: Void = status.load(model, .machine(machineID), OwnerAPI.machine(machineID))
        async let b: Void = track.load(model, .machineTrack(machineID),
                                       OwnerAPI.history(machineID, from: now.addingTimeInterval(-86_400), to: now))
        async let c: Void = alerts.load(model, .machineAlerts(machineID), OwnerAPI.alerts(machineID: machineID, pageSize: 5))
        async let d: Void = info.load(model, .machineInfo(machineID), OwnerAPI.machineInfo(machineID))
        _ = await (a, b, c, d)
        if model.features.jobs {
            await jobs.load(model, .machineJobs(machineID),
                            OwnerAPI.jobs(status: .inProgress, machineID: machineID, pageSize: 5))
        }
        if model.features.meterEvidence {
            await readings.load(model, .machineReadings(machineID), OwnerAPI.meterCaptures(machineID: machineID, pageSize: 5))
        }
    }

    @ViewBuilder private func statusSection(_ machine: MachineMapDTO) -> some View {
        let style = FleetPresentation.style(for: machine, dataIsCached: status.isFromCache)
        Section {
            LabeledContent("Connectivity") {
                Pill(text: FleetPresentation.statusLabel(machine, dataIsCached: status.isFromCache), color: style.tone.color)
            }
            .accessibilityElement(children: .combine)
            ForEach(Array(MachineText.statusRows(machine, info: info.value, dataIsCached: status.isFromCache).enumerated()),
                    id: \.offset) { _, row in
                LabeledContent(row.0, value: row.1)
            }
        } header: {
            Text("Status")
        } footer: {
            Text(MachineText.statusFooter)
        }
    }

    @ViewBuilder private func trackSection(_ machine: MachineMapDTO) -> some View {
        Section {
            let points = (track.value?.points ?? []).map {
                CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude)
            }
            if points.isEmpty && !machine.hasPosition {
                Text(MachineText.noTrack).foregroundStyle(.secondary)
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
                LabeledContent("Positions", value: "\(history.points.count)")
                LabeledContent("Distance (24 h)", value: MachineText.distance(history.distanceKm))
                LabeledContent("Stops", value: "\(history.stops.count)")
                if history.truncated { FootNote(MachineText.truncated) }
                ForEach(Array(history.stops.suffix(10).enumerated()), id: \.offset) { _, stop in
                    Text(MachineText.stopLine(stop.start, durationSeconds: stop.durationSeconds)).font(.caption)
                }
                ForEach(Array(history.siteVisits.suffix(10).enumerated()), id: \.offset) { _, visit in
                    Text(MachineText.visitLine(visit)).font(.caption)
                }
            } else if let error = track.error {
                Text(error).font(.footnote).foregroundStyle(Palette.offline)
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
                Text(jobs.value == nil ? (jobs.error ?? "Loading…") : "No job in progress.").foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder private var alertSection: some View {
        Section("Recent alerts") {
            let items = alerts.value?.items ?? []
            if items.isEmpty {
                Text(alerts.value == nil ? (alerts.error ?? "Loading…") : "No alerts.").foregroundStyle(.secondary)
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
                Text(readings.value == nil ? (readings.error ?? "Loading…") : "No readings yet.").foregroundStyle(.secondary)
            }
            ForEach(items) { capture in ReadingRow(model: model, capture: capture) }
        } header: {
            Text("Recent meter readings")
        } footer: {
            Text(ReadingText.photoFooter)
        }
    }
}

/// One meter reading with its state and an on-demand evidence photo (same lines as Android's `ReadingRow`).
struct ReadingRow: View {
    let model: OwnerModel
    let capture: MeterCaptureDTO
    @State private var showPhoto = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(ReadingText.title(capture)).font(.headline)
                Spacer()
                Pill(text: OwnerFormat.humanize(capture.state), color: capture.state == "ACCEPTED" ? Palette.live : Palette.warning)
            }
            Text(ReadingText.detail(capture)).font(.caption).foregroundStyle(.secondary)
            if capture.photoAttachmentID != nil {
                PhotoButton(label: "evidence photo", isOnline: model.isOnline) { showPhoto = true }
            }
        }
        .sheet(isPresented: $showPhoto) {
            if let id = capture.photoAttachmentID {
                EvidencePhotoView(model: model, title: "\(OwnerFormat.humanize(capture.kind.rawValue)) reading",
                                  request: OwnerAPI.attachmentURL(id))
            }
        }
    }
}

/// "View evidence photo", or "Evidence photo (online only)" while offline (Android `EvidencePhoto` wording).
struct PhotoButton: View {
    let label: String
    let isOnline: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Label(isOnline ? "View \(label)" : "\(label.prefix(1).uppercased() + label.dropFirst()) (online only)",
                  systemImage: "photo")
        }
        .font(.subheadline)
        .buttonStyle(.borderless)
        .disabled(!isOnline)
        .accessibilityHint(isOnline ? "Downloads the photo" : "Needs a connection")
    }
}

/// Downloads an evidence photo through a fresh presigned URL into memory only (ephemeral session,
/// no URL cache, nothing written to disk).
struct EvidencePhotoView: View {
    let model: OwnerModel
    let title: String
    let request: APIRequest<PhotoURLDTO>
    @State private var image: UIImage?
    @State private var error: String?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if let image {
                    ScrollView([.horizontal, .vertical]) {
                        Image(uiImage: image).resizable().scaledToFit()
                            .accessibilityLabel(title)
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
            let link = try await repository.send(request)
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
