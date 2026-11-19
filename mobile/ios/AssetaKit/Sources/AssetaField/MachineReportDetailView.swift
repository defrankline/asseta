#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

private typealias T = MachineReportTexts

/// One of my machine reports, read-only (from the synced "my machine reports"): reading, photo, split, the time since
/// the machine's last visit and where both readings were taken. A rejected report is final: it shows the approver's
/// reason and "Send a new report for this machine." (no correction).
struct MachineReportDetailView: View {
    let model: FieldModel
    let reportID: UUID

    var body: some View {
        if let report = model.myReports.first(where: { $0.id == reportID }) {
            content(report).navigationTitle(report.reportNumber)
        } else {
            ContentUnavailableView(T.dashMyReports, systemImage: "doc.text", description: Text(T.detailMissing))
        }
    }

    private func content(_ r: MachineReportDTO) -> some View {
        let places = model.reportStates.first { $0.machineID == r.machineID }?.meterDecimalPlaces ?? 1
        func reading(_ value: Decimal) -> String { MachineReportRules.readingText(value, decimalPlaces: places) }
        let online = model.online
        return List {
            Section {
                LabeledContent(T.detailMachine, value: [r.machineCode, r.machineName].compactMap { $0 }.joined(separator: " · "))
                LabeledContent(T.detailStatus) {
                    ShellPill(SupervisorShellTexts.reportStatus(r.status), tone: tone(r.state))
                }
                LabeledContent(T.detailReadings, value: T.readingRange(reading(r.startReading.value), reading(r.endReading.value)))
                LabeledContent(T.detailPeriod, value: "\(MachineReportRules.dayTime(r.startAt)) → \(MachineReportRules.dayTime(r.endAt))")
                if !r.isOpening { LabeledContent(T.detailHours, value: "\(MachineReportRules.hoursText(r.hours.value)) h") }
            }
            if r.state == .rejected {
                Section {
                    Text(T.rejected(r.decisionNote)).foregroundStyle(Shell.badText)
                        .accessibilityIdentifier("myReport.rejected")
                }
            }
            Section(T.detailVisit) {
                Text(VisitTexts.sinceLastVisit(seconds: r.sincePreviousVisitSeconds))
                    .accessibilityIdentifier("myReport.sinceLastVisit")
                VisitWhereLine(visit: r.visit, identifier: "myReport.where")
                LastVisitLine(visit: r.previousVisit, identifier: "myReport.lastVisit")
            }
            Section(T.detailPhoto) {
                if let photo = r.photoAttachmentID {
                    EvidenceImage(description: T.detailPhoto, local: nil, remote: { await online?.attachmentURL(photo) })
                } else {
                    Text(T.detailNoPhoto).font(.footnote).foregroundStyle(.secondary)
                }
            }
            if !r.lines.isEmpty {
                Section(T.detailSplit) {
                    ForEach(r.lines.sorted { $0.lineNo < $1.lineNo }) { line in
                        VStack(alignment: .leading, spacing: 2) {
                            LabeledContent(line.lineKind == .customer ? line.customerName ?? T.customer : line.reasonName ?? T.reason,
                                           value: "\(MachineReportRules.hoursText(line.hours.value)) h")
                            if let note = line.note, !note.isEmpty {
                                Text(note).font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            if let note = r.note, !note.isEmpty {
                Section { Text(T.detailNote(note)) }
            }
        }
    }

    private func tone(_ state: MachineReportState?) -> ShellPill.Tone {
        switch state {
        case .approved: .good
        case .rejected: .bad
        default: .waiting
        }
    }
}
#endif
