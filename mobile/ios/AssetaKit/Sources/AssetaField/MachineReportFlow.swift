#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaSync
import SwiftUI
import UIKit

private typealias T = MachineReportTexts

/// A searchable picker in the shell's input-box style (backend lists are never a plain dropdown).
struct ShellPicker: View {
    let label: String
    let options: [PickerOption]
    @Binding var selection: UUID?
    var placeholder = "Choose…"
    var emptyMessage = "Nothing has been synced to this phone yet."
    var identifier: String
    @State private var presented = false

    var body: some View {
        Button { presented = true } label: {
            FieldBox(label) {
                HStack {
                    let chosen = options.first { $0.id == selection }
                    Text(chosen.map { [$0.title, $0.subtitle].compactMap { $0 }.joined(separator: " · ") } ?? placeholder)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(chosen == nil ? Shell.muted : Shell.text)
                        .lineLimit(1)
                    Spacer()
                    Image(systemName: "chevron.down").font(.footnote).foregroundStyle(Shell.muted)
                }
            }
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(identifier)
        .sheet(isPresented: $presented) {
            SearchablePickerSheet(title: label, options: options, selection: $selection, noneTitle: nil, emptyMessage: emptyMessage)
        }
    }
}

/// Machine report in 3 steps (designs MachineReading, Reconcile, ReviewSubmit): the new reading (photo, on-phone
/// reading, GPS) → account for the hours (customers from hours they bought, non-productive with reason and note) →
/// review & submit. Saved on the phone and sent by sync (`MACHINE_REPORT`).
struct MachineReportFlow: View {
    let model: FieldModel
    let close: () -> Void
    /// Opens the machine's readings and meter reset requests (the existing reset flow).
    var openMachine: (UUID) -> Void = { _ in }
    @State private var machineID: UUID?
    @State private var step = 1
    @State private var capture: MeterCaptureModel?
    @State private var showCamera = false
    @State private var cameraDenied = false
    @State private var lines: [ReportLineDraft] = []
    @State private var note = ""
    @State private var editing: ReportLineDraft?
    @State private var error: String?
    @State private var reportID = UUID()
    /// A submit is under way (the button reads "Submitting…" and cannot be pressed twice).
    @State private var saving = false
    /// The area of this report's reading (reverse geocoded once the GPS fix is in, while online; sent as `place_name`).
    @State private var capturePlace: String?
    /// The area of the machine's last visit when the server has none (display only, never sent or saved).
    @State private var lastVisitPlace: String?
    /// Leaving was asked with entered work: "Discard this report?" is shown.
    @State private var confirmDiscard = false
    @Environment(\.openURL) private var openURL

    init(model: FieldModel, machineID: UUID?, close: @escaping () -> Void, openMachine: @escaping (UUID) -> Void = { _ in }) {
        self.model = model
        self.close = close
        self.openMachine = openMachine
        _machineID = State(initialValue: machineID)
    }

    private var entry: (state: MachineReportStatusDTO, standing: MachineReportStanding)? {
        model.machineStandings.first { $0.state.machineID == machineID }
    }

    private var decimals: Int { entry?.state.meterDecimalPlaces ?? 1 }
    private var previous: Decimal? { entry?.state.previousReading?.value }
    private var newReading: Decimal? {
        capture.flatMap { MachineReportRules.reading($0.draft.readingText, decimalPlaces: decimals) }
    }
    private var difference: Decimal? {
        guard let previous, let newReading else { return nil }
        return MachineReportRules.difference(previous: previous, reading: newReading)
    }
    private var code: String { entry?.state.machineCode ?? model.machineCode(machineID ?? UUID()) }

    var body: some View {
        VStack(spacing: 0) {
            ShellHeader(step == 2 ? T.reconcileTitle(code, readingShort(previous), readingShort(newReading))
                        : step == 3 ? T.reviewTitle : T.title,
                        action: back)
            StepBar(step: step).padding(.horizontal, 16).padding(.top, 6)
            Text(T.step(step, step == 2 ? T.stepSplit : step == 3 ? T.stepReview : T.stepReading))
                .font(.system(size: 13)).foregroundStyle(Shell.muted)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16).padding(.top, 6).padding(.bottom, 14)
            switch step {
            case 1: readingStep
            case 2: reconcileStep
            default: reviewStep
            }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .onChange(of: machineID, initial: true) { _, id in prepare(id) }
        .fullScreenCover(isPresented: $showCamera) {
            CameraCaptureView { data in
                showCamera = false
                if let data, let capture { Task { await capture.photoTaken(data, model: model) } }
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
        // Swipe-back would leave without asking (or skip the steps): off once there is something to lose.
        .navigationBarBackButtonHidden(entered || step > 1)
        .alert(FormLeave.reportTitle, isPresented: $confirmDiscard) {
            Button(FormLeave.keepEditing, role: .cancel) {}
            Button(FormLeave.discard, role: .destructive) { leave() }
        } message: { Text(FormLeave.reportBody) }
        .sheet(item: $editing) { line in
            ReportLineEditor(model: model, line: line, caps: caps, reasons: model.reportReasons) { saved in
                if let saved {
                    if let i = lines.firstIndex(where: { $0.id == saved.id }) { lines[i] = saved } else { lines.append(saved) }
                } else {
                    lines.removeAll { $0.id == line.id }
                }
                editing = nil
            }
        }
    }

    private func readingShort(_ value: Decimal?) -> String {
        value.map(MachineReportRules.hoursText) ?? "—"
    }

    private var caps: [UUID: (name: String, hours: Decimal)] { machineID.map { model.reportCaps(machineID: $0) } ?? [:] }

    /// A new line starts with the hours still to account for (empty when none are left).
    private var suggestedHours: String { left() > 0 ? AccountabilityRules.plain(left()) : "" }

    /// Customer lines are offered only while customer hours are on; otherwise only non-productive lines.
    private var customerLines: Bool { model.access.customerHoursOn }

    private func left(excluding id: UUID? = nil) -> Decimal {
        (difference ?? 0) - MachineReportRules.accounted(lines.filter { $0.id != id })
    }

    /// The header's Back: steps back first; then, with a photo or anything entered, asks "Discard this report?"
    /// instead of leaving. Never while the report is being saved.
    private func back() {
        if saving { return }
        if step > 1 { step -= 1; return }
        switch FormLeave.decide(saving: saving, saved: false, entered: entered) {
        case .stay: return
        case .ask: confirmDiscard = true
        case .leave: leave()
        }
    }

    private func leave() {
        capture?.cancel(model: model)
        close()
    }

    /// A photo, a typed reading, a note or changed lines: leaving would throw them away.
    private var entered: Bool {
        FormLeave.reportEntered(hasPhoto: capture?.photo != nil, typedReading: capture?.draft.readingText ?? "",
                                lines: lines, startingLines: [], note: note)
    }

    /// A new machine: a fresh capture under its rules (photo, OCR, GPS start now). Every report has its own new reading
    /// (a rejected report is final). Once the fix is in and the phone is online, its area is looked up (never waited on).
    private func prepare(_ id: UUID?) {
        capture?.cancel(model: model)
        capture = nil
        lines = []
        note = ""
        capturePlace = nil
        lastVisitPlace = nil
        reportID = UUID()
        guard let id else { return }
        lookUpLastVisitPlace(id)
        guard let machine = model.reportMachine(id) else { return }
        if case let .allowed(snapshot) = model.gate(machineID: id) {
            let c = MeterCaptureModel(target: .daily(machine), snapshot: snapshot)
            capture = c
            Task {
                await c.locate(using: model.locator)
                guard model.isOnline, let gps = c.draft.gps, gps.status == .fix, let lat = gps.latitude, let lng = gps.longitude
                else { return }
                let place = await PlaceGeocoder.place(latitude: lat, longitude: lng)
                if capture?.captureID == c.captureID { capturePlace = place }
            }
        }
    }

    /// The last visit's area for display when the server has none and the phone is online.
    private func lookUpLastVisitPlace(_ id: UUID) {
        guard model.isOnline, let visit = model.reportStates.first(where: { $0.machineID == id })?.lastVisit,
              visit.place == nil, let point = visit.coordinate else { return }
        Task {
            let place = await PlaceGeocoder.place(latitude: point.latitude, longitude: point.longitude)
            if machineID == id { lastVisitPlace = place }
        }
    }

    /// The machine's last visit as shown (the server's place, else the one looked up on this phone).
    private func lastVisit(_ state: MachineReportStatusDTO) -> VisitPoint? {
        guard let visit = state.lastVisit else { return nil }
        return visit.place == nil && lastVisitPlace != nil ? visit.with(place: lastVisitPlace) : visit
    }

    // MARK: Step 1

    private var machineOptions: [PickerOption] {
        model.reportStates.map { PickerOption(id: $0.machineID, title: $0.machineCode ?? "", subtitle: $0.machineName) }
    }

    @ViewBuilder private var readingStep: some View {
        ScrollView {
            VStack(spacing: 12) {
                if machineOptions.isEmpty {
                    ShellCard { Text(T.noMachines).foregroundStyle(Shell.muted) }
                } else {
                    ShellPicker(label: T.machine, options: machineOptions, selection: $machineID, placeholder: T.chooseMachine,
                                emptyMessage: T.noMachines, identifier: "report.machine")
                }
                if let entry {
                    switch entry.standing {
                    case let .awaitingApproval(notSent):
                        ShellCard {
                            VStack(alignment: .leading, spacing: 8) {
                                ShellPill(T.pillAwaiting, tone: .waiting)
                                if let line = entry.state.pendingReportNumber ?? (notSent ? T.queued : nil) {
                                    Text(line).foregroundStyle(Shell.muted)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    default:
                        if entry.standing == .opening {
                            openingCard
                        } else {
                            lastReadingCard(entry.state)
                        }
                        if model.inbox.machines[entry.state.machineID] != nil {
                            Button(T.readingsAndReset) { openMachine(entry.state.machineID) }
                                .font(.system(size: 13, weight: .semibold)).foregroundStyle(Shell.accent)
                                .frame(maxWidth: .infinity, alignment: .trailing)
                                .accessibilityIdentifier("report.readings")
                        }
                        if case .blocked(let reason) = model.gate(machineID: entry.state.machineID) {
                            ShellCard { Text(reason.message).foregroundStyle(Shell.warnText) }
                        } else if capture != nil {
                            photoArea
                            gpsFailure
                            readingField
                        }
                        if entry.standing != .opening, let difference, difference > 0, readingIssues.isEmpty {
                            toAccountCard
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
        }
        bottom {
            if let entry {
                let issues = readingIssues
                let typed = capture?.photoData != nil || !(capture?.draft.readingText.isEmpty ?? true)
                switch entry.standing {
                case .awaitingApproval: EmptyView()
                case .opening:
                    if !issues.isEmpty && typed { issueList(issues) }
                    PrimaryButton(saving ? T.submitting : T.submitOpening, enabled: issues.isEmpty && !saving,
                                  identifier: "report.submitOpening") { submitOpening() }
                default:
                    if !issues.isEmpty && typed { issueList(issues) }
                    PrimaryButton(difference.flatMap { $0 > 0 ? T.next(MachineReportRules.hoursText($0)) : nil } ?? T.nextPlain,
                                  enabled: issues.isEmpty, identifier: "report.next") { step = 2 }
                    footnote(T.nothingFooter)
                }
            }
        }
    }

    /// What still blocks step 1 (capture evidence, then the reading against the last one); empty = it can go on.
    private var readingIssues: [String] {
        guard let entry else { return [T.chooseMachine] }
        if case .awaitingApproval = entry.standing { return [T.pillAwaiting] }
        if case .blocked(let reason) = model.gate(machineID: entry.state.machineID) { return [reason.message] }
        guard let capture else { return [T.chooseMachine] }
        if capture.isReadingPhoto { return [T.readingPhoto] }
        let issues = capture.issues.map(\.description)
        if !issues.isEmpty { return issues }
        return [MachineReportRules.readingProblem(previous: previous, reading: newReading)].compactMap { $0 }
    }

    private func issueList(_ issues: [String]) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(issues, id: \.self) { Text($0) }
        }
        .font(.system(size: 13)).foregroundStyle(Shell.warnText).frame(maxWidth: .infinity, alignment: .leading)
    }

    private var openingCard: some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 4) {
                Text(T.openingTitle).font(.system(size: 17, weight: .semibold)).foregroundStyle(Shell.text)
                Text(T.openingBody).font(.system(size: 14)).foregroundStyle(Shell.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// The last-visit card: "Last reading 1,210.0 h · 12 Nov, 17:30 · approved" (baseline / meter reset by where the
    /// reading comes from), "Time since last visit: 1 day 3 h (last visit 17 Nov, 15:26)" (from the capture time, else
    /// now; cached machine state offline) and the last visit's Where line (opens Apple Maps).
    private func lastReadingCard(_ state: MachineReportStatusDTO) -> some View {
        ShellCard(padding: 14) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(T.lastReading).font(.system(size: 13)).foregroundStyle(Shell.muted)
                        Text(previous.map { MachineReportRules.readingText($0, decimalPlaces: decimals) + " h" } ?? "—")
                            .font(.system(size: 22, weight: .bold)).foregroundStyle(Shell.text)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        if let at = state.previousAt {
                            Text(MachineReportRules.dayTime(at)).font(.system(size: 13)).foregroundStyle(Shell.muted)
                        }
                        Text(T.source(state.previousSource)).font(.system(size: 13)).foregroundStyle(Shell.goodText)
                    }
                }
                Text(VisitTexts.timeSinceLastVisit(state.lastVisit?.at, now: capture?.photoTakenAt ?? Date()))
                    .font(.system(size: 13)).foregroundStyle(Shell.text)
                    .accessibilityIdentifier("report.sinceLastVisit")
                VisitWhereLine(visit: lastVisit(state), identifier: "report.lastVisitWhere")
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    @ViewBuilder private var photoArea: some View {
        VStack(spacing: 10) {
            if let capture, let data = capture.photoData, let image = UIImage(data: data) {
                Image(uiImage: image).resizable().scaledToFill().frame(height: 110).clipped()
                    .clipShape(RoundedRectangle(cornerRadius: 10)).padding(.horizontal, 14)
                    .accessibilityLabel(T.photoCaption(readByPhone: false, gps: nil))
                if let value = capture.draft.ocr?.value {
                    Text(value).font(.system(size: 30, weight: .bold, design: .monospaced)).tracking(3)
                        .foregroundStyle(Color(red: 0x0B / 255, green: 0x17 / 255, blue: 0x22 / 255))
                        .padding(.horizontal, 16).padding(.vertical, 6)
                        .background(Color(red: 0xF3 / 255, green: 0xF6 / 255, blue: 0xF9 / 255), in: RoundedRectangle(cornerRadius: 6))
                }
                Text(photoCaption(capture)).font(.system(size: 13)).foregroundStyle(Shell.muted)
            }
            if let capture, capture.isReadingPhoto { ProgressView(T.readingPhoto) }
            Button { Task { if await CameraAccess.request() { showCamera = true } else { cameraDenied = true } } } label: {
                Text(capture?.photoData == nil ? T.takePhoto : T.retakePhoto)
                    .font(.system(size: 13, weight: .medium)).foregroundStyle(Shell.text)
                    .padding(.horizontal, 14).frame(height: 36)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Shell.outline))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("report.photo")
        }
        .padding(.vertical, 16)
        .frame(maxWidth: .infinity, minHeight: 200)
        .background(Shell.sunken, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(Shell.outline, style: StrokeStyle(lineWidth: 1, dash: [5])))
    }

    /// "Meter photo · read by the phone · GPS ±6 m".
    private func photoCaption(_ capture: MeterCaptureModel) -> String {
        var gps: String?
        if case let .done(result) = capture.gpsState, result.status == .fix { gps = T.gpsAccuracy(result.accuracyM) }
        return T.photoCaption(readByPhone: capture.draft.mode == .automatic && capture.draft.ocr?.value != nil, gps: gps)
    }

    /// Why there is no location fix (the reading is still saved, flagged for review).
    @ViewBuilder private var gpsFailure: some View {
        if let capture, case let .done(result) = capture.gpsState, result.status != .fix {
            Text(MeterCaptureView.describe(result.status)).font(.system(size: 13)).foregroundStyle(Shell.warnText)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    @ViewBuilder private var readingField: some View {
        if let capture {
            FieldBox(T.newReading) {
                TextField("0.0", text: Binding(get: { capture.draft.readingText }, set: { capture.draft.readingText = $0 }))
                    .keyboardType(.decimalPad).font(.system(size: 20, weight: .bold)).monospacedDigit()
                    .accessibilityIdentifier("report.reading")
            }
        }
    }

    private var toAccountCard: some View {
        ShellCard(fill: Shell.raised) {
            HStack {
                Text(T.hoursToAccount).font(.system(size: 15)).foregroundStyle(Shell.text)
                Spacer()
                Text("\(MachineReportRules.readingText(max(0, difference ?? 0), decimalPlaces: decimals)) h").font(.system(size: 28, weight: .bold))
                    .foregroundStyle(Shell.accent).monospacedDigit()
            }
        }
    }


    // MARK: Step 2

    @ViewBuilder private var reconcileStep: some View {
        let diff = difference ?? 0
        let accounted = MachineReportRules.accounted(lines)
        let problems = MachineReportRules.problems(lines, difference: diff, available: caps)
        let complete = MachineReportRules.allAccounted(lines, difference: diff)
        ScrollView {
            VStack(spacing: 0) {
                ShellCard(padding: 14) {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(T.accountedFor).font(.system(size: 15, weight: .semibold))
                            Spacer()
                            Text(MachineReportRules.hoursText(accounted)).font(.system(size: 20, weight: .bold))
                                + Text(" " + T.ofHours(MachineReportRules.hoursText(diff))).font(.system(size: 14)).foregroundColor(Shell.muted)
                        }
                        .foregroundStyle(Shell.text)
                        SplitBar(lines.enumerated().map { i, line in
                            (fraction(line, of: diff), color(line, index: i))
                        })
                        // "All hours accounted for" only when every line is valid and they add up to the difference.
                        Text(complete ? T.allAccounted : accounted == diff ? T.errLineHours : T.leftToAccount(diff - accounted))
                            .font(.system(size: 13)).foregroundStyle(complete ? Shell.goodText : Shell.warnText)
                    }
                }
                if customerLines {
                    SectionLabel(T.customersHeader).padding(.top, 16).padding(.bottom, 8)
                    lineList(.customer)
                }
                SectionLabel(T.nonProductiveHeader).padding(.top, 16).padding(.bottom, 8)
                lineList(.nonProductive)
                HStack(spacing: 10) {
                    if customerLines {
                        OutlineButton(T.addCustomer) {
                            editing = ReportLineDraft(kind: .customer, hoursText: suggestedHours)
                        }
                        .accessibilityIdentifier("report.addCustomer")
                    }
                    OutlineButton(T.addNonProductive) {
                        editing = ReportLineDraft(kind: .nonProductive, hoursText: suggestedHours)
                    }
                    .accessibilityIdentifier("report.addNonProductive")
                }
                .padding(.top, 12)
                let others = problems.filter { diff - accounted <= 0 || $0 != T.leftToAccount(diff - accounted) }
                if !others.isEmpty && !lines.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(others, id: \.self) { Text($0) }
                    }
                    .font(.system(size: 13)).foregroundStyle(Shell.badText).frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 10)
                }
            }
            .padding(.horizontal, 16)
        }
        bottom {
            PrimaryButton(diff - accounted > 0 ? T.reviewLeft(MachineReportRules.hoursText(diff - accounted)) : T.review,
                          enabled: problems.isEmpty, identifier: "report.review") { step = 3 }
            footnote(T.reconcileFooter)
        }
    }

    private func fraction(_ line: ReportLineDraft, of total: Decimal) -> Double {
        guard total > 0, let h = MachineReportRules.hours(line.hoursText) else { return 0 }
        return NSDecimalNumber(decimal: h / total).doubleValue
    }

    private func color(_ line: ReportLineDraft, index: Int) -> Color {
        let customers = lines.filter { $0.kind == .customer }
        let others = lines.filter { $0.kind == .nonProductive }
        if line.kind == .customer {
            let i = customers.firstIndex { $0.id == line.id } ?? 0
            return i % 2 == 0 ? Shell.series[0] : Shell.series[1]
        }
        let i = others.firstIndex { $0.id == line.id } ?? 0
        return i % 2 == 0 ? Shell.series[2] : Shell.series[3]
    }

    @ViewBuilder private func lineList(_ kind: ReportLineKind) -> some View {
        let items = lines.filter { $0.kind == kind }
        if !items.isEmpty {
            VStack(spacing: 0) {
                ForEach(Array(items.enumerated()), id: \.element.id) { index, line in
                    Button { editing = line } label: { lineRow(line, last: index == items.count - 1) }.buttonStyle(.plain)
                }
            }
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
        }
    }

    private func lineRow(_ line: ReportLineDraft, last: Bool) -> some View {
        let hours = MachineReportRules.hours(line.hoursText)
        let subtitle: String
        if line.kind == .customer {
            // "after this" counts only the customer's valid lines.
            let available = line.customerID.flatMap { caps[$0]?.hours } ?? 0
            let after = MachineReportRules.customerAfter(lines, customerID: line.customerID, available: available)
            subtitle = T.availableAfter(MachineReportRules.hoursText(available), MachineReportRules.hoursText(after))
        } else {
            subtitle = line.note
        }
        return VStack(spacing: 0) {
            HStack(spacing: 12) {
                RoundedRectangle(cornerRadius: 4).fill(color(line, index: 0)).frame(width: 10, height: 36)
                VStack(alignment: .leading, spacing: 2) {
                    Text(line.kind == .customer ? line.customerName : line.reasonName).font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(Shell.text)
                    Text(subtitle).font(.system(size: 12)).foregroundStyle(Shell.muted).lineLimit(2)
                    // An invalid line is marked on its hours and does not count.
                    if hours == nil {
                        Text(T.errLineHours).font(.system(size: 12)).foregroundStyle(Shell.badText)
                            .accessibilityIdentifier("report.lineHoursError")
                    }
                }
                Spacer()
                Text("\(hours.map(MachineReportRules.hoursText) ?? (line.hoursText.isEmpty ? "—" : line.hoursText)) h")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(hours == nil ? Shell.badText : Shell.text).monospacedDigit()
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            if !last { Divider().overlay(Shell.border) }
        }
        .contentShape(Rectangle())
    }

    // MARK: Step 3

    @ViewBuilder private var reviewStep: some View {
        let diff = difference ?? 0
        let split = MachineReportRules.productive(lines)
        ScrollView {
            VStack(spacing: 12) {
                ShellCard {
                    VStack(alignment: .leading, spacing: 6) {
                        Text([code, entry?.state.machineName].compactMap { $0 }.joined(separator: " · "))
                            .font(.system(size: 13)).foregroundStyle(Shell.muted)
                        Text(T.readingRange(previous.map { MachineReportRules.readingText($0, decimalPlaces: decimals) } ?? "—",
                                            newReading.map { MachineReportRules.readingText($0, decimalPlaces: decimals) } ?? "—"))
                            .font(.system(size: 18, weight: .bold)).foregroundStyle(Shell.text)
                        Text(T.periodLine(periodStart, periodEnd)).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                if let entry { lastReadingCard(entry.state) }
                VStack(spacing: 0) {
                    reviewGroup(T.productiveHeader(MachineReportRules.hoursText(split.customers)), lines.filter { $0.kind == .customer })
                    reviewGroup(T.nonProductiveHeaderTotal(MachineReportRules.hoursText(split.nonProductive)),
                                lines.filter { $0.kind == .nonProductive })
                    HStack {
                        Text(T.total)
                        Spacer()
                        Text(T.matchesMeter(MachineReportRules.hoursText(diff))).foregroundStyle(Shell.goodText)
                    }
                    .font(.system(size: 16, weight: .bold)).foregroundStyle(Shell.text)
                    .padding(.horizontal, 16).padding(.vertical, 14)
                }
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
                Text(T.reviewInfo(MachineReportRules.hoursText(split.customers)))
                    .font(.system(size: 13)).lineSpacing(3).foregroundStyle(Shell.goodInfo)
                    .padding(.horizontal, 14).padding(.vertical, 12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Shell.goodFill, in: RoundedRectangle(cornerRadius: 14))
                FieldBox(T.approverNote) {
                    TextField("", text: $note, axis: .vertical).font(.system(size: 15, weight: .medium)).lineLimit(1...4)
                        .accessibilityIdentifier("report.note")
                }
            }
            .padding(.horizontal, 16)
        }
        bottom {
            PrimaryButton(saving ? T.submitting : T.submit, enabled: !saving, identifier: "report.submit") { submit() }
        }
    }

    private var periodStart: String? {
        entry?.state.previousAt.map { MachineReportRules.dayTime($0) }
    }

    private var periodEnd: String {
        MachineReportRules.dayTime(capture?.photoTakenAt ?? Date())
    }

    @ViewBuilder private func reviewGroup(_ title: String, _ items: [ReportLineDraft]) -> some View {
        if !items.isEmpty {
            Text(title).font(.system(size: 13, weight: .semibold)).foregroundStyle(Shell.muted)
                .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 6)
            ForEach(items) { line in
                HStack {
                    Text(line.kind == .customer ? line.customerName : line.reasonName)
                    Spacer()
                    Text("\(MachineReportRules.hoursText(MachineReportRules.hours(line.hoursText) ?? 0)) h")
                        .fontWeight(.semibold)
                }
                .foregroundStyle(Shell.text).padding(.horizontal, 16).padding(.vertical, 8)
            }
            Divider().overlay(Shell.border).padding(.top, 4)
        }
    }

    // MARK: Saving

    private func reading() -> NewReportReading? {
        guard let capture, let gps = capture.draft.gps,
              case let .success(value) = CaptureValidator.normalizeReading(
                  newReading.map { DecimalString($0).description } ?? "", decimalPlaces: decimals)
        else { return nil }
        return NewReportReading(captureID: capture.captureID, mode: capture.draft.mode, reading: value, ocr: capture.draft.ocr,
                                photo: capture.photo, gps: gps, capturedAt: capture.photoTakenAt ?? Date(),
                                snapshot: capture.snapshot, placeName: capturePlace)
    }

    /// Runs a submit once: the button reads "Submitting…" until the report is queued (then the flow closes) or refused.
    private func saveOnce(_ work: @escaping @MainActor () -> Void) {
        guard !saving else { return }
        saving = true
        Task { @MainActor in
            await Task.yield()
            work()
            saving = false
        }
    }

    private func submitOpening() { saveOnce(queueOpening) }

    private func queueOpening() {
        guard let machineID, let reading = reading() else { error = T.errReading; return }
        do {
            try model.submitReport(machineID: machineID, reading: reading, report: nil, opening: true, reportID: reportID)
            close()
        } catch {
            self.error = FieldErrors.describe(error)
        }
    }

    private func submit() { saveOnce(queueReport) }

    private func queueReport() {
        guard let machineID, let diff = difference else { return }
        let checked: CheckedReport
        switch MachineReportRules.check(lines, difference: diff, available: caps, note: note) {
        case let .failure(problems): error = problems.text; return
        case let .success(value): checked = value
        }
        guard let reading = reading() else { error = T.errReading; return }
        do {
            try model.submitReport(machineID: machineID, reading: reading, report: checked, opening: false, reportID: reportID)
            close()
        } catch {
            self.error = FieldErrors.describe(error)
        }
    }

    // MARK: Layout

    private func bottom(@ViewBuilder _ content: () -> some View) -> some View {
        VStack(spacing: 8) { content() }.padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 12)
    }

    private func footnote(_ text: String) -> some View {
        Text(text).font(.system(size: 12)).foregroundStyle(Shell.faint).multilineTextAlignment(.center)
    }
}

/// Adds or edits one line of the split: a customer (with the hours they have available) or a non-productive reason with
/// its note.
struct ReportLineEditor: View {
    let model: FieldModel
    @State var line: ReportLineDraft
    let caps: [UUID: (name: String, hours: Decimal)]
    let reasons: [MachineReportReasonDTO]
    let done: (ReportLineDraft?) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                if line.kind == .customer {
                    SearchablePickerField(label: T.customer, options: customerOptions, selection: Binding(
                        get: { line.customerID },
                        set: { id in
                            line.customerID = id
                            line.customerName = id.flatMap { caps[$0]?.name } ?? ""
                        }), emptyMessage: T.noCustomersWithHours, identifier: "line.customer")
                } else {
                    SearchablePickerField(label: T.reason, options: reasons.map { PickerOption(id: $0.id, title: $0.name, subtitle: nil) },
                                          selection: Binding(get: { line.reasonID }, set: { id in
                                              line.reasonID = id
                                              line.reasonName = reasons.first { $0.id == id }?.name ?? ""
                                          }), identifier: "line.reason")
                }
                Section {
                    TextField(T.hours, text: $line.hoursText).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                        .accessibilityIdentifier("line.hours")
                } header: { Text(T.hours) } footer: {
                    // Up to 2 decimals whatever the meter shows; a wrong value is marked on the field.
                    if !line.hoursText.isEmpty && !MachineReportRules.lineValid(line) {
                        Text(T.errLineHours).foregroundStyle(Shell.badText).accessibilityIdentifier("line.hoursError")
                    }
                }
                if line.kind == .nonProductive {
                    Section(T.whatHappened) {
                        TextField("", text: $line.note, axis: .vertical).lineLimit(2...5)
                            .accessibilityIdentifier("line.note")
                    }
                }
                Section {
                    Button(T.removeLine, role: .destructive) { done(nil) }
                }
            }
            .navigationTitle(line.kind == .customer ? T.addCustomer.replacingOccurrences(of: "+ ", with: "")
                             : T.addNonProductive.replacingOccurrences(of: "+ ", with: ""))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(T.lineDone) { done(line) }.disabled(!valid).accessibilityIdentifier("line.done")
                }
            }
        }
        .presentationDetents([.medium, .large])
    }

    private var customerOptions: [PickerOption] {
        caps.filter { $0.value.hours > 0 }.sorted { $0.value.name < $1.value.name }.map {
            PickerOption(id: $0.key, title: $0.value.name, subtitle: "\(MachineReportRules.hoursText($0.value.hours)) h available")
        }
    }

    private var valid: Bool {
        guard MachineReportRules.lineValid(line) else { return false }
        if line.kind == .customer { return line.customerID != nil }
        return line.reasonID != nil && !line.note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}
#endif
