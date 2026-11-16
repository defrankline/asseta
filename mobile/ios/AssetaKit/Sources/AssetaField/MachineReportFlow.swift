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
    /// Redo of a rejected report: its reading and number.
    @State private var redo: MachineReportDTO?
    @Environment(\.openURL) private var openURL

    init(model: FieldModel, machineID: UUID?, close: @escaping () -> Void) {
        self.model = model
        self.close = close
        _machineID = State(initialValue: machineID)
    }

    private var entry: (state: MachineReportStatusDTO, standing: MachineReportStanding)? {
        model.machineStandings.first { $0.state.machineID == machineID }
    }

    private var decimals: Int { entry?.state.meterDecimalPlaces ?? 1 }
    private var previous: Decimal? { redo?.startReading.value ?? entry?.state.previousReading?.value }
    private var newReading: Decimal? {
        if let redo { return redo.endReading.value }
        return capture.flatMap { MachineReportRules.reading($0.draft.readingText, decimalPlaces: decimals) }
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
            StepBar(step: step).padding(.horizontal, 16).padding(.top, 6).padding(.bottom, 14)
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
        .sheet(item: $editing) { line in
            ReportLineEditor(model: model, line: line, caps: caps, reasons: model.reportReasons, decimals: decimals,
                             left: left(excluding: line.id)) { saved in
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
        value.map { $0.formatted(.number.precision(.fractionLength(0...decimals))) } ?? "—"
    }

    private var caps: [UUID: (name: String, hours: Decimal)] { machineID.map { model.reportCaps(machineID: $0) } ?? [:] }

    private func left(excluding id: UUID? = nil) -> Decimal {
        (difference ?? 0) - MachineReportRules.accounted(lines.filter { $0.id != id }, decimalPlaces: decimals)
    }

    private func back() {
        if step > 1 { step -= 1; return }
        capture?.cancel(model: model)
        close()
    }

    /// A new machine: a fresh capture under its rules (photo, OCR, GPS start now).
    private func prepare(_ id: UUID?) {
        capture?.cancel(model: model)
        capture = nil
        lines = []
        redo = nil
        reportID = UUID()
        guard let id, let machine = model.reportMachine(id) else { return }
        if case let .allowed(snapshot) = model.gate(machineID: id) {
            let c = MeterCaptureModel(target: .daily(machine), snapshot: snapshot)
            capture = c
            Task { await c.locate(using: model.locator) }
        }
    }

    // MARK: Step 1

    private var machineOptions: [PickerOption] {
        model.reportStates.map { PickerOption(id: $0.machineID, title: $0.machineCode ?? "", subtitle: $0.machineName) }
    }

    @ViewBuilder private var readingStep: some View {
        ScrollView {
            VStack(spacing: 12) {
                Text(T.step(1, T.stepReading)).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if machineOptions.isEmpty {
                    ShellCard { Text(T.noMachines).foregroundStyle(Shell.muted) }
                }
                ShellPicker(label: T.machine, options: machineOptions, selection: $machineID, placeholder: T.chooseMachine,
                            emptyMessage: T.noMachines, identifier: "report.machine")
                if let entry {
                    switch entry.standing {
                    case .awaitingApproval:
                        ShellCard { Text(T.awaitingExplain).foregroundStyle(Shell.muted) }
                    case let .rejected(reportID):
                        rejectedCard(reportID)
                    default:
                        lastReadingCard(entry.state)
                        if case .blocked(let reason) = model.gate(machineID: entry.state.machineID) {
                            ShellCard { Text(reason.message).foregroundStyle(Shell.warnText) }
                        } else {
                            photoArea
                            readingField
                            if entry.standing == .opening {
                                ShellCard(fill: Shell.raised) { Text(T.openingExplain).font(.system(size: 14)).foregroundStyle(Shell.text) }
                            } else {
                                toAccountCard
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
        }
        bottom {
            if let entry {
                switch entry.standing {
                case .awaitingApproval, .rejected: EmptyView()
                case .opening:
                    PrimaryButton(T.submitOpening, enabled: readingProblem == nil, identifier: "report.submitOpening") { submitOpening() }
                    footnote(readingProblem ?? T.nothingFooter)
                default:
                    PrimaryButton(T.next(MachineReportRules.hoursText(max(0, difference ?? 0))), enabled: readingProblem == nil,
                                  identifier: "report.next") { step = 2 }
                    footnote(readingProblem ?? T.nothingFooter)
                }
            }
        }
    }

    /// Why step 1 cannot go on (nil = it can).
    private var readingProblem: String? {
        guard let capture else { return T.errReading }
        if capture.isReadingPhoto { return T.readingPhoto }
        if let issue = capture.issues.first { return issue.description }
        guard let reading = newReading else { return T.errReadingInvalid }
        if entry?.standing == .opening { return nil }
        guard let previous else { return T.errReading }
        if reading == previous { return T.errNothingToReport }
        if reading < previous { return T.errNotHigher(MachineReportRules.readingText(previous, decimalPlaces: decimals)) }
        return nil
    }

    private func lastReadingCard(_ state: MachineReportStatusDTO) -> some View {
        ShellCard(padding: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(T.lastReading).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    Text(state.previousReading.map { MachineReportRules.readingText($0.value, decimalPlaces: decimals) + " h" }
                         ?? T.noPreviousReading)
                        .font(.system(size: 22, weight: .bold)).foregroundStyle(Shell.text)
                }
                Spacer()
                if let at = state.previousAt {
                    Text(T.lastReadingWhen(at.formatted(.dateTime.day().month(.abbreviated).hour().minute()),
                                           approved: state.previousSource == "REPORT"))
                        .font(.system(size: 13)).foregroundStyle(Shell.muted).multilineTextAlignment(.trailing)
                }
            }
        }
    }

    @ViewBuilder private var photoArea: some View {
        VStack(spacing: 10) {
            if let capture, let data = capture.photoData, let image = UIImage(data: data) {
                Image(uiImage: image).resizable().scaledToFill().frame(height: 110).clipped()
                    .clipShape(RoundedRectangle(cornerRadius: 10)).padding(.horizontal, 14)
                    .accessibilityLabel("Meter photo")
                if let value = capture.draft.ocr?.value {
                    Text(value).font(.system(size: 30, weight: .bold, design: .monospaced)).tracking(3)
                        .foregroundStyle(Color(red: 0x0B / 255, green: 0x17 / 255, blue: 0x22 / 255))
                        .padding(.horizontal, 16).padding(.vertical, 6)
                        .background(Color(red: 0xF3 / 255, green: 0xF6 / 255, blue: 0xF9 / 255), in: RoundedRectangle(cornerRadius: 6))
                }
            }
            if let capture, capture.isReadingPhoto { ProgressView() }
            Text(gpsLine).font(.system(size: 13)).foregroundStyle(Shell.muted)
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

    private var gpsLine: String {
        guard let capture, case let .done(gps) = capture.gpsState else { return T.photoLine }
        if gps.status == .fix, let accuracy = gps.accuracyM { return T.photoGps(Int(accuracy.rounded())) }
        return T.photoNoGps
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
                Text("\(MachineReportRules.hoursText(max(0, difference ?? 0))) h").font(.system(size: 28, weight: .bold))
                    .foregroundStyle(Shell.accent).monospacedDigit()
            }
        }
    }

    @ViewBuilder private func rejectedCard(_ reportID: UUID) -> some View {
        let report = model.myReports.first { $0.id == reportID }
        ShellCard {
            VStack(alignment: .leading, spacing: 8) {
                ShellPill(T.pillRejected, tone: .bad)
                Text(T.rejectedExplain).foregroundStyle(Shell.text)
                if let reason = report?.decisionNote { Text(T.rejectedReason(reason)).foregroundStyle(Shell.muted) }
                if let report {
                    Text(T.readingRange(MachineReportRules.readingText(report.startReading.value, decimalPlaces: decimals),
                                        MachineReportRules.readingText(report.endReading.value, decimalPlaces: decimals)))
                        .font(.system(size: 15, weight: .semibold)).foregroundStyle(Shell.text)
                    PrimaryButton(T.redoSplit, identifier: "report.redo") {
                        redo = report
                        lines = MachineReportRules.drafts(from: report)
                        note = report.note ?? ""
                        step = 2
                    }
                }
            }
        }
    }

    // MARK: Step 2

    @ViewBuilder private var reconcileStep: some View {
        let diff = difference ?? 0
        let accounted = MachineReportRules.accounted(lines, decimalPlaces: decimals)
        let problems = MachineReportRules.problems(lines, difference: diff, decimalPlaces: decimals, available: caps)
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
                        Text(accounted == diff ? T.allAccounted : T.leftToAccount(diff - accounted))
                            .font(.system(size: 13)).foregroundStyle(accounted == diff ? Shell.goodText : Shell.warnText)
                    }
                }
                SectionLabel(T.customersHeader).padding(.top, 16).padding(.bottom, 8)
                lineList(.customer)
                SectionLabel(T.nonProductiveHeader).padding(.top, 16).padding(.bottom, 8)
                lineList(.nonProductive)
                HStack(spacing: 10) {
                    OutlineButton(T.addCustomer) {
                        editing = ReportLineDraft(kind: .customer, hoursText: AccountabilityRules.plain(max(0, left())))
                    }
                    .accessibilityIdentifier("report.addCustomer")
                    OutlineButton(T.addNonProductive) {
                        editing = ReportLineDraft(kind: .nonProductive, hoursText: AccountabilityRules.plain(max(0, left())))
                    }
                    .accessibilityIdentifier("report.addNonProductive")
                }
                .padding(.top, 12)
                if caps.values.allSatisfy({ $0.hours <= 0 }) {
                    Text(T.noCustomersWithHours).font(.system(size: 13)).foregroundStyle(Shell.muted).padding(.top, 10)
                }
                let others = problems.filter { $0 != T.leftToAccount(diff - accounted) }
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
            PrimaryButton(problems.isEmpty ? T.review : (accounted != diff ? T.reviewLeft(MachineReportRules.hoursText(diff - accounted))
                                                         : T.review),
                          enabled: problems.isEmpty, identifier: "report.review") { step = 3 }
            footnote(T.reconcileFooter)
        }
    }

    private func fraction(_ line: ReportLineDraft, of total: Decimal) -> Double {
        guard total > 0, let h = MachineReportRules.hours(line.hoursText, decimalPlaces: decimals) else { return 0 }
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
        let hours = MachineReportRules.hours(line.hoursText, decimalPlaces: decimals)
        let subtitle: String
        if line.kind == .customer {
            let available = line.customerID.flatMap { caps[$0]?.hours } ?? 0
            let used = lines.filter { $0.customerID == line.customerID && $0.kind == .customer }
                .reduce(Decimal(0)) { $0 + (MachineReportRules.hours($1.hoursText, decimalPlaces: decimals) ?? 0) }
            subtitle = T.availableAfter(MachineReportRules.hoursText(available), MachineReportRules.hoursText(available - used))
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
                }
                Spacer()
                Text("\(hours.map(MachineReportRules.hoursText) ?? "—") h").font(.system(size: 17, weight: .bold))
                    .foregroundStyle(Shell.text).monospacedDigit()
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            if !last { Divider().overlay(Shell.border) }
        }
        .contentShape(Rectangle())
    }

    // MARK: Step 3

    @ViewBuilder private var reviewStep: some View {
        let diff = difference ?? 0
        let split = MachineReportRules.productive(lines, decimalPlaces: decimals)
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
                }
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
            PrimaryButton(T.submit, enabled: true, identifier: "report.submit") { submit() }
        }
    }

    private var periodStart: String {
        let at = redo?.startAt ?? entry?.state.previousAt
        return at?.formatted(.dateTime.day().month(.abbreviated).hour().minute()) ?? "—"
    }

    private var periodEnd: String {
        let at = redo?.endAt ?? capture?.photoTakenAt ?? Date()
        return at.formatted(.dateTime.day().month(.abbreviated).hour().minute())
    }

    @ViewBuilder private func reviewGroup(_ title: String, _ items: [ReportLineDraft]) -> some View {
        if !items.isEmpty {
            Text(title).font(.system(size: 13, weight: .semibold)).foregroundStyle(Shell.muted)
                .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 6)
            ForEach(items) { line in
                HStack {
                    Text(line.kind == .customer ? line.customerName : line.reasonName)
                    Spacer()
                    Text("\(MachineReportRules.hoursText(MachineReportRules.hours(line.hoursText, decimalPlaces: decimals) ?? 0)) h")
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
                                snapshot: capture.snapshot)
    }

    private func submitOpening() {
        guard let machineID, let reading = reading() else { error = T.errReading; return }
        do {
            try model.submitReport(machineID: machineID, reading: reading, existingCaptureID: nil, correctsReportID: nil,
                                   report: nil, opening: true, reportID: reportID)
            close()
        } catch {
            self.error = FieldErrors.describe(error)
        }
    }

    private func submit() {
        guard let machineID, let diff = difference else { return }
        let checked: CheckedReport
        switch MachineReportRules.check(lines, difference: diff, decimalPlaces: decimals, available: caps, note: note) {
        case let .failure(problems): error = problems.text; return
        case let .success(value): checked = value
        }
        do {
            if let redo {
                try model.submitReport(machineID: machineID, reading: nil, existingCaptureID: redo.captureID,
                                       correctsReportID: redo.id, report: checked, opening: false, reportID: reportID)
            } else {
                guard let reading = reading() else { error = T.errReading; return }
                try model.submitReport(machineID: machineID, reading: reading, existingCaptureID: nil, correctsReportID: nil,
                                       report: checked, opening: false, reportID: reportID)
            }
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
    let decimals: Int
    let left: Decimal
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
                    if left > 0 {
                        Button(T.fillRest + " (\(MachineReportRules.hoursText(left)) h)") {
                            line.hoursText = AccountabilityRules.plain(left)
                        }
                    }
                } header: { Text(T.hours) }
                if line.kind == .nonProductive {
                    Section(T.note) {
                        TextField(T.notePlaceholder, text: $line.note, axis: .vertical).lineLimit(2...5)
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
        guard MachineReportRules.hours(line.hoursText, decimalPlaces: decimals) != nil else { return false }
        if line.kind == .customer { return line.customerID != nil }
        return line.reasonID != nil && !line.note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}
#endif
