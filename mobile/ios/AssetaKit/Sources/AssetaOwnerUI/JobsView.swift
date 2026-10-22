#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Jobs by status (read-only) with their financial summary.
struct JobsView: View {
    let model: OwnerModel
    @State private var status: JobStatus? = .inProgress
    @State private var loader = Loader<Page<JobDTO>>()

    private static let filters: [(String, JobStatus?)] = [
        ("In progress", .inProgress), ("Approved", .approved), ("Pending", .pendingApproval),
        ("Completed", .completed), ("All", nil),
    ]

    var body: some View {
        List {
            Section {
                Picker("Status", selection: $status) {
                    ForEach(Self.filters, id: \.0) { Text($0.0).tag($0.1) }
                }
                .pickerStyle(.menu)
            }
            if let page = loader.value {
                if page.items.isEmpty {
                    ContentUnavailableView("No jobs", systemImage: "list.clipboard",
                                           description: Text("Nothing matches this filter."))
                }
                ForEach(page.items) { job in
                    NavigationLink(value: OwnerRoute.job(job.id)) { JobRow(job: job) }
                }
                if page.total > page.items.count {
                    Text("Showing \(page.items.count) of \(page.total). Use the web console for the full list.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Jobs")
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick, filter: status?.rawValue)) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .jobs(status), OwnerAPI.jobs(status: status, pageSize: 100))
    }
}

struct ReloadKey: Hashable {
    let tick: Int
    let filter: String?
}

struct JobRow: View {
    let job: JobDTO

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(job.jobNumber).font(.headline)
                Spacer()
                Pill(text: job.status.label, color: job.status.color)
            }
            Text(dates).font(.subheadline).foregroundStyle(.secondary)
            if let rate = job.hourlyRate, let currency = job.currency {
                Text("\(OwnerFormat.money(rate, currency: currency)) / h").font(.caption).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private var dates: String {
        if let completed = job.completedAt { return "Completed \(completed.shortStamp)" }
        if let started = job.startedAt { return "Started \(started.shortStamp)" }
        return "Planned \(job.plannedStart.shortStamp)"
    }
}

struct JobDetailView: View {
    let model: OwnerModel
    let jobID: UUID
    @State private var loader = Loader<JobSummaryDTO>()

    var body: some View {
        List {
            if let summary = loader.value {
                let job = summary.job
                Section("Job") {
                    LabeledContent("Number", value: job.jobNumber)
                    LabeledContent("Status") { Pill(text: job.status.label, color: job.status.color) }
                    LabeledContent("Planned start", value: job.plannedStart.shortStamp)
                    if let started = job.startedAt { LabeledContent("Started", value: started.shortStamp) }
                    if let completed = job.completedAt { LabeledContent("Completed", value: completed.shortStamp) }
                    if model.features.fleet {
                        NavigationLink(value: OwnerRoute.machine(job.machineID)) { Text("Machine") }
                    }
                }
                Section("Hours") {
                    LabeledContent("Opening reading", value: summary.openingReading?.description ?? "—")
                    LabeledContent("Closing reading", value: summary.closingReading?.description ?? "—")
                    LabeledContent("Meter hours", value: OwnerFormat.hours(summary.meterHours))
                    LabeledContent("Non-billable", value: OwnerFormat.hours(summary.nonbillableHours))
                    if let standby = summary.standbyHours { LabeledContent("Standby", value: OwnerFormat.hours(standby)) }
                    LabeledContent("Billable", value: OwnerFormat.hours(summary.billableHours))
                }
                Section {
                    if let charges = summary.charges {
                        ForEach(Array(charges.lines.enumerated()), id: \.offset) { _, line in
                            LabeledContent(line.description,
                                           value: OwnerFormat.money(line.amount, currency: charges.currency))
                        }
                        LabeledContent("Discount", value: OwnerFormat.money(charges.discountTotal, currency: charges.currency))
                        LabeledContent("Tax", value: OwnerFormat.money(charges.taxTotal, currency: charges.currency))
                        LabeledContent("Total") {
                            Text(OwnerFormat.money(charges.total, currency: charges.currency)).bold()
                        }
                    } else {
                        Text("Charges appear once both readings are in.").foregroundStyle(.secondary)
                    }
                } header: {
                    Text("Charges")
                } footer: {
                    Text(summary.billingReady ? "Ready to invoice." :
                        "Not ready to invoice\(summary.blockingExceptions > 0 ? ": \(summary.blockingExceptions) blocking exception(s)" : "").")
                }
                if summary.openExceptions > 0 {
                    Section { Label("\(summary.openExceptions) open exception(s) need review in the console.",
                                    systemImage: "exclamationmark.bubble") }
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle(loader.value?.job.jobNumber ?? "Job")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async { await loader.load(model, .job(jobID), OwnerAPI.jobSummary(jobID)) }
}
#endif
