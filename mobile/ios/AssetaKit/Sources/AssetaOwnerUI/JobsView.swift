#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Jobs by status (read-only) with their financial summary; filters and wording from `JobsPresentation`.
struct JobsView: View {
    let model: OwnerModel
    @State private var status: JobStatus? = JobsPresentation.defaultFilter
    @State private var loader = Loader<Page<JobDTO>>()

    var body: some View {
        List {
            FilterChips(options: JobsPresentation.filters, selection: $status)
                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            if let page = loader.value {
                Text(JobsPresentation.countLine(shown: page.items.count, total: page.total))
                    .font(.caption).foregroundStyle(.secondary)
                if page.items.isEmpty {
                    EmptyState(title: JobsPresentation.emptyTitle, message: JobsPresentation.emptyMessage,
                               systemImage: "list.clipboard")
                }
                ForEach(page.items) { job in
                    NavigationLink(value: OwnerRoute.job(job.id)) { JobRow(job: job) }
                }
                if page.total > page.items.count { FootNote(JobsPresentation.moreInConsole) }
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

/// Horizontally scrolling status chips (Android `FilterChip` row); tapping the selected chip keeps it.
struct FilterChips<Value: Hashable>: View {
    let options: [(Value, String)]
    @Binding var selection: Value

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(Array(options.enumerated()), id: \.offset) { _, option in
                    let on = selection == option.0
                    Button(option.1) { selection = option.0 }
                        .font(.footnote)
                        .buttonStyle(.bordered)
                        .tint(on ? Brand.amber : .secondary)
                        .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
            .padding(.horizontal).padding(.vertical, 6)
        }
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
            Text(JobsPresentation.datesLine(job)).font(.subheadline).foregroundStyle(.secondary)
            if let rate = job.hourlyRate, let currency = job.currency {
                Text("Rate \(OwnerFormat.money(rate, currency: currency)) / h").font(.caption).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Job drilldown: meter vs billable hours (server-computed), charges, readings with photos, work log, expenses and fuel
/// (when the role can read expenses), customer acknowledgement.
struct JobDetailView: View {
    let model: OwnerModel
    let jobID: UUID
    @State private var loader = Loader<JobSummaryDTO>()
    @State private var captures = Loader<[MeterCaptureDTO]>()
    @State private var acknowledgements = Loader<[AcknowledgementDTO]>()
    @State private var activities = Loader<[ActivityDTO]>()
    @State private var expenses = Loader<Page<ExpenseDTO>>()
    @State private var fuel = Loader<Page<FuelEventDTO>>()

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
                    if let rate = job.hourlyRate, let currency = job.currency {
                        LabeledContent("Hourly rate", value: OwnerFormat.money(rate, currency: currency))
                    }
                    if let minimum = job.minimumHours { LabeledContent("Minimum hours", value: OwnerFormat.hours(minimum)) }
                    if model.features.fleet {
                        NavigationLink(value: OwnerRoute.machine(job.machineID)) { Text("Open machine") }
                    }
                }
                Section("Hours") {
                    LabeledContent("Opening reading", value: summary.openingReading?.description ?? "—")
                    LabeledContent("Closing reading", value: summary.closingReading?.description ?? "—")
                    LabeledContent("Meter hours", value: OwnerFormat.hours(summary.meterHours))
                    LabeledContent("Non-billable hours", value: OwnerFormat.hours(summary.nonbillableHours))
                    if let standby = summary.standbyHours { LabeledContent("Standby hours", value: OwnerFormat.hours(standby)) }
                    LabeledContent("Billable hours", value: OwnerFormat.hours(summary.billableHours))
                }
                Section {
                    if let charges = summary.charges {
                        ForEach(Array(charges.lines.enumerated()), id: \.offset) { _, line in
                            LabeledContent("\(line.description) (\(line.quantity.description))",
                                           value: OwnerFormat.money(line.amount, currency: charges.currency))
                        }
                        LabeledContent("Subtotal", value: OwnerFormat.money(charges.subtotal, currency: charges.currency))
                        LabeledContent("Discount", value: OwnerFormat.money(charges.discountTotal, currency: charges.currency))
                        LabeledContent("Tax", value: OwnerFormat.money(charges.taxTotal, currency: charges.currency))
                        LabeledContent("Total") {
                            Text(OwnerFormat.money(charges.total, currency: charges.currency)).bold()
                        }
                    } else {
                        Text(JobDetailText.noCharges).foregroundStyle(.secondary)
                    }
                    if let exceptions = JobDetailText.exceptions(summary.openExceptions) {
                        if model.features.meterEvidence {
                            NavigationLink(value: OwnerRoute.exceptions(jobID: jobID)) {
                                Text(exceptions).font(.footnote).foregroundStyle(Palette.offline)
                            }
                        } else {
                            Text(exceptions).font(.footnote).foregroundStyle(Palette.offline)
                        }
                    }
                } header: {
                    Text("Charges")
                } footer: {
                    Text(JobDetailText.billing(summary))
                }
                Section("Readings") {
                    let items = captures.value ?? []
                    if items.isEmpty {
                        Text(captures.value == nil ? (captures.error ?? "Loading…") : "No readings yet.").foregroundStyle(.secondary)
                    }
                    ForEach(items) { ReadingRow(model: model, capture: $0) }
                }
                Section(WorkLogText.title) {
                    let items = activities.value ?? []
                    if items.isEmpty {
                        Text(activities.value == nil ? (activities.error ?? "Loading…") : WorkLogText.empty)
                            .foregroundStyle(.secondary)
                    }
                    ForEach(items) { RecordRowView(row: WorkLogText.row($0)) }
                }
                if model.features.expenses {
                    Section {
                        let items = expenses.value?.items ?? []
                        if items.isEmpty {
                            Text(expenses.value == nil ? (expenses.error ?? "Loading…") : SpendText.jobExpensesEmpty)
                                .foregroundStyle(.secondary)
                        }
                        ForEach(items) { RecordRowView(row: SpendText.expenseRow($0)) }
                    } header: {
                        Text(SpendText.expensesTitle)
                    } footer: {
                        let totals = SpendText.totalApproved(expenses.value?.items ?? [])
                        if !totals.isEmpty { Text(totals.joined(separator: "\n")) }
                    }
                    Section(SpendText.fuelTitle) {
                        let items = fuel.value?.items ?? []
                        if items.isEmpty {
                            Text(fuel.value == nil ? (fuel.error ?? "Loading…") : SpendText.jobFuelEmpty)
                                .foregroundStyle(.secondary)
                        }
                        ForEach(items) { RecordRowView(row: SpendText.fuelRow($0)) }
                    }
                }
                Section("Customer acknowledgement") {
                    let items = acknowledgements.value ?? []
                    if items.isEmpty {
                        Text(acknowledgements.value == nil ? (acknowledgements.error ?? "Loading…") : "Not acknowledged yet.")
                            .foregroundStyle(.secondary)
                    }
                    ForEach(items) { AcknowledgementRow(model: model, ack: $0) }
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Job")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    private func reload() async {
        async let a: Void = loader.load(model, .job(jobID), OwnerAPI.jobSummary(jobID))
        async let b: Void = captures.load(model, .jobCaptures(jobID), OwnerAPI.jobCaptures(jobID))
        async let c: Void = acknowledgements.load(model, .jobAcknowledgements(jobID), OwnerAPI.jobAcknowledgements(jobID))
        async let d: Void = activities.load(model, .jobActivities(jobID), OwnerAPI.jobActivities(jobID))
        async let e: Void = loadSpend()
        _ = await (a, b, c, d, e)
    }

    /// Expenses and fuel of the job, only for roles that can read expenses.
    private func loadSpend() async {
        guard model.features.expenses else { return }
        async let e: Void = expenses.load(model, .jobExpenses(jobID), OwnerAPI.expenses(jobID: jobID, pageSize: 100))
        async let f: Void = fuel.load(model, .jobFuel(jobID), OwnerAPI.fuelEvents(jobID: jobID, pageSize: 100))
        _ = await (e, f)
    }
}

struct AcknowledgementRow: View {
    let model: OwnerModel
    let ack: AcknowledgementDTO
    @State private var showSignature = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            LabeledContent("Signed by", value: ack.signerName)
            LabeledContent("Method", value: OwnerFormat.humanize(ack.method))
            LabeledContent("Hours acknowledged", value: OwnerFormat.hours(ack.acknowledgedHours))
            LabeledContent("When", value: ack.capturedAt.shortStamp)
            if ack.signatureAttachmentID != nil {
                PhotoButton(label: "signature", isOnline: model.isOnline) { showSignature = true }
            }
        }
        .sheet(isPresented: $showSignature) {
            if let id = ack.signatureAttachmentID {
                EvidencePhotoView(model: model, title: "Signature", request: OwnerAPI.attachmentURL(id))
            }
        }
    }
}
#endif
