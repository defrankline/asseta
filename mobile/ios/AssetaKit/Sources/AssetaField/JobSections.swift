#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaSync
import SwiftUI

/// Job summary: opening/closing reading, meter hours, work totals per type and open/blocking findings.
struct JobSummarySection: View {
    let inbox: InboxSnapshot
    let jobID: UUID

    var body: some View {
        let opening = inbox.jobReading(jobID, kind: "OPENING")
        let closing = inbox.jobReading(jobID, kind: "CLOSING")
        let readings = inbox.readings(ofJob: jobID)
        let totals = JobFigures.minutesByType(
            inbox.activities.filter { $0.jobID == jobID }.map { WorkSpan(activityType: $0.activityType, start: $0.start, end: $0.end) },
            now: Date())
        let open = readings.reduce(0) { $0 + $1.openFindings }
        let blocking = readings.reduce(0) { $0 + $1.blockingFindings }
        Section("Summary") {
            LabeledContent("Opening reading", value: opening?.reading ?? "Not captured")
            LabeledContent("Closing reading", value: closing?.reading ?? "Not captured")
            if let hours = JobFigures.meterHours(opening: opening?.reading, closing: closing?.reading) {
                LabeledContent("Meter hours", value: InboxTexts.hours(hours))
            }
            ForEach(totals, id: \.type) { total in
                LabeledContent(InboxTexts.activityType(total.type), value: JobFigures.duration(minutes: total.minutes))
            }
            LabeledContent("Open findings") { Text("\(open)").foregroundStyle(open > 0 ? Palette.warning : .secondary) }
            if blocking > 0 {
                LabeledContent("Blocking findings") { Text("\(blocking)").foregroundStyle(Palette.offline) }
            }
        }
    }
}

/// My readings of the job, newest first, each opening its detail.
struct JobReadingsSection: View {
    let inbox: InboxSnapshot
    let jobID: UUID

    var body: some View {
        let readings = inbox.readings(ofJob: jobID)
        if !readings.isEmpty {
            Section("Readings") {
                ForEach(readings) { reading in
                    NavigationLink(value: FieldRoute.reading(reading.id)) {
                        InboxRow("\(InboxTexts.readingKind(reading.kind)) \(reading.reading)", reading.status, reading.at.listText)
                    }
                }
            }
        }
    }
}

/// The customer acknowledgement of the job: signer, method, confirmed hours and the signature.
struct AcknowledgementSection: View {
    let model: FieldModel
    let jobID: UUID

    var body: some View {
        if let ack = model.inbox.acknowledgements.filter({ $0.jobID == jobID }).max(by: { $0.at < $1.at }) {
            Section("Acknowledgement") {
                LabeledContent("Status") { StatusPill(status: ack.status) }
                LabeledContent("Signer", value: ack.signerName)
                LabeledContent("Method", value: InboxTexts.ackMethod(ack.method))
                if let phone = ack.signerPhone { LabeledContent("Phone", value: phone) }
                if let hours = ack.hours { LabeledContent("Confirmed hours", value: hours) }
                LabeledContent("Recorded", value: ack.at.listText)
                if ack.method == "SIGNATURE" {
                    let files = ack.op.map { model.evidenceFiles(of: $0) } ?? []
                    let online = model.online
                    EvidenceImage(description: "Signature of \(ack.signerName)",
                                  local: files.isEmpty ? nil : { files.lazy.compactMap { model.localEvidence($0) }.first },
                                  remote: ack.signatureAttachmentID.map { id in { await online?.attachmentURL(id) } })
                }
            }
        }
    }
}

/// Expenses and fuel recorded for the job.
struct JobMoneySection: View {
    let inbox: InboxSnapshot
    let jobID: UUID

    var body: some View {
        let expenses = inbox.expenses.filter { $0.jobID == jobID }
        let fuel = inbox.fuel.filter { $0.jobID == jobID }
        if !expenses.isEmpty || !fuel.isEmpty {
            Section("Expenses & fuel") {
                ForEach(expenses) { e in
                    NavigationLink(value: FieldRoute.expense(e.id)) {
                        InboxRow(e.description.isEmpty ? "Expense" : e.description, e.status,
                                 InboxTexts.money(e.amount, e.currency) + " · " + e.at.listText)
                    }
                }
                ForEach(fuel) { f in
                    NavigationLink(value: FieldRoute.fuel(f.id)) {
                        InboxRow("Fuel \(InboxTexts.fuelType(f.eventType).lowercased()) · \(InboxTexts.litres(f.litres))", f.status,
                                 f.at.listText)
                    }
                }
            }
        }
    }
}
#endif
