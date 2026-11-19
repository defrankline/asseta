#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

/// One machine report (design OwnerReportApproval, Android `ReportApprovalScreen`): the meter photo, readings with the
/// phone's reading and GPS, the split with each customer's hours before and after, the tracker cross-check, the
/// supervisor's note, then Approve / Reject (with a reason, confirmed) while it waits. Never the approver's own.
struct OwnerReportApprovalView: View {
    let model: OwnerModel
    let reportID: UUID
    @State private var loader = Loader<MachineReportDTO>()
    @State private var capture = Loader<ReportCaptureDTO>()
    @State private var reason = ""
    @State private var busy = false
    @State private var error: String?
    @State private var message: String?
    @State private var confirmReject = false
    @State private var showPhoto = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            ShellHeader(ReportTexts.screenTitle, action: { dismiss() })
            if let report = loader.value {
                content(report)
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: model.changeTick) { await reload() }
        .alert(ReportTexts.confirmReject, isPresented: $confirmReject) {
            Button(ReportTexts.reject, role: .destructive) { if let report = loader.value { Task { await decide(report, approve: false) } } }
            Button(ReportTexts.cancel, role: .cancel) {}
        } message: {
            Text(ReportTexts.confirmRejectText)
        }
        .sheet(isPresented: $showPhoto) {
            if let photo = photoID {
                EvidencePhotoView(model: model, title: ReportTexts.screenTitle, request: OwnerAPI.attachmentURL(photo))
            }
        }
    }

    private var photoID: UUID? { loader.value?.photoAttachmentID ?? capture.value?.photoAttachmentID }

    private func content(_ r: MachineReportDTO) -> some View {
        let customers = ReportPresentation.customerLines(r)
        let reasons = ReportPresentation.nonProductiveLines(r)
        return ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(ReportPresentation.machine(r)) machine report").font(.system(size: 18, weight: .bold))
                                .foregroundStyle(Shell.text)
                            Text(ReportPresentation.attentionDetail(r)).font(.system(size: 13)).foregroundStyle(Shell.muted)
                        }
                        Spacer(minLength: 8)
                        if r.state != .submitted {
                            ShellPill(ReportPresentation.statusLabel(r), tone: r.state == .approved ? .good : .bad)
                        }
                    }
                    if photoID != nil {
                        PhotoButton(label: ReportTexts.viewPhoto, isOnline: model.isOnline && !loader.isFromCache) { showPhoto = true }
                            .padding(.top, 8)
                    }
                    Text(ReportPresentation.readings(r)).font(.system(size: 24, weight: .bold)).foregroundStyle(Shell.text)
                        .padding(.top, 10)
                    Text(ReportPresentation.readLine(r, capture: capture.value)).font(.system(size: 14)).foregroundStyle(Shell.accent)
                    if let gps = ReportPresentation.gpsLine(capture.value) {
                        Text(gps).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    }
                    // Time since the machine's last visit, where this reading was taken and where the last visit was.
                    Text(ReportPresentation.sinceLastVisit(r)).font(.system(size: 14, weight: .semibold)).foregroundStyle(Shell.text)
                        .padding(.top, 6).accessibilityIdentifier("report.sinceLastVisit")
                    VisitWhereLine(visit: r.visit, identifier: "report.where")
                    LastVisitLine(visit: r.previousVisit, identifier: "report.lastVisit")
                }
                .padding(16).frame(maxWidth: .infinity, alignment: .leading)
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))

                if !customers.isEmpty {
                    SectionLabel("\(ReportTexts.customers) · \(OwnerFigures.hours(r.customerHours.value))").padding(.top, 10)
                    rows(customers) { line in
                        CardRow(line.customerName ?? "Customer", subtitle: ReportPresentation.beforeAfter(line), last: line.id == customers.last?.id) {
                            Text(OwnerFigures.hours(line.hours.value)).font(.system(size: 15, weight: .bold)).foregroundStyle(Shell.text)
                        }
                    }
                }
                if !reasons.isEmpty {
                    SectionLabel("\(ReportTexts.nonProductive) · \(OwnerFigures.hours(r.nonProductiveHours.value))").padding(.top, 10)
                    rows(reasons) { line in
                        CardRow(line.reasonName ?? ReportPresentation.reasonShort(line), subtitle: ReportPresentation.quoted(line.note),
                                last: line.id == reasons.last?.id) {
                            Text(OwnerFigures.hours(line.hours.value)).font(.system(size: 15, weight: .bold)).foregroundStyle(Shell.text)
                        }
                    }
                }
                Text(ReportPresentation.tracker(r)).font(.system(size: 14)).foregroundStyle(Shell.muted)
                    .padding(.horizontal, 4).padding(.vertical, 8)
                if let note = r.note, !note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    SectionLabel(ReportTexts.noteLabel)
                    ShellCard { Text(note).font(.system(size: 15)).foregroundStyle(Shell.text).frame(maxWidth: .infinity, alignment: .leading) }
                }
                if r.state != .submitted {
                    if let note = r.decisionNote, !note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        ShellCard {
                            Text([r.decidedByName, note].compactMap { $0 }.joined(separator: ": ")).font(.system(size: 14))
                                .foregroundStyle(Shell.muted).frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                } else {
                    decision(r)
                }
                if let message {
                    Text(message).font(.system(size: 14)).foregroundStyle(Shell.accent).accessibilityIdentifier("report.message")
                }
            }
            .padding(.horizontal, 16).padding(.top, 4).padding(.bottom, 24)
        }
        .refreshable { await reload() }
    }

    private func rows<Line: Identifiable, Row: View>(_ lines: [Line], @ViewBuilder row: @escaping (Line) -> Row) -> some View {
        VStack(spacing: 0) { ForEach(lines) { row($0) } }
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    @ViewBuilder private func decision(_ r: MachineReportDTO) -> some View {
        let decision = MachineReportApproval.decision(r, me: model.me.userID, permissions: Set(model.features.permissions))
        let blocked = model.mutationBlock(permitted: true, showingCachedData: loader.isFromCache)
        VStack(alignment: .leading, spacing: 12) {
            if let why = ReportPresentation.cannotDecide(decision) {
                Text(why).font(.system(size: 13)).foregroundStyle(Shell.muted)
            } else if let blocked {
                BlockedNote(block: blocked)
            } else {
                FieldBox(ReportTexts.reasonLabel) {
                    TextField(ReportTexts.reasonPlaceholder, text: $reason, axis: .vertical).lineLimit(2...4)
                        .onChange(of: reason) { _, text in if text.count > 1000 { reason = String(text.prefix(1000)) } }
                        .accessibilityIdentifier("report.rejectReason")
                }
                HStack(spacing: 10) {
                    OutlineButton(ReportTexts.reject, height: 54) { confirmReject = true }
                        .disabled(busy || !MachineReportApproval.rejectReasonValid(reason))
                        .accessibilityIdentifier("report.reject")
                    PrimaryButton(ReportTexts.approve, enabled: !busy, identifier: "report.approve") {
                        Task { await decide(r, approve: true) }
                    }
                }
            }
            if let error {
                Text(error).font(.system(size: 13)).foregroundStyle(Shell.badText).accessibilityIdentifier("report.error")
            }
        }
        .padding(.top, 12)
    }

    private func reload() async {
        await loader.load(model, .machineReport(reportID), OwnerAPI.machineReport(reportID))
        // The reading behind the report (OCR value, GPS fix): best effort, never fails the report.
        if model.features.meterEvidence, let id = loader.value?.captureID {
            await capture.load(model, .reportCapture(id), OwnerAPI.reportCapture(id))
        }
    }

    /// Approve (the reason is an optional note) or reject (the reason is required).
    private func decide(_ report: MachineReportDTO, approve: Bool) async {
        guard let repository = model.repository, !busy, approve || MachineReportApproval.rejectReasonValid(reason) else { return }
        busy = true
        error = nil
        defer { busy = false }
        do {
            let updated = try await repository.send(approve
                ? OwnerAPI.approveMachineReport(report.id, note: reason, idempotencyKey: UUID())
                : OwnerAPI.rejectMachineReport(report.id, reason: reason, idempotencyKey: UUID()))
            loader.replace(updated)
            message = ReportPresentation.decided(updated, approved: approve)
            reason = ""
            UIAccessibility.post(notification: .announcement, argument: message)
            if updated.lines.isEmpty { await reload() }
        } catch {
            let code = (error as? APIError)?.code
            self.error = ReportTexts.refusal(code, fallback: DecisionErrorText.message(for: error))
            model.handle(error)
            if code == "REPORT_NOT_PENDING" || DecisionErrorText.needsReload(error) { await reload() }
        }
    }
}
#endif
