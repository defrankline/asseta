package com.asseta.supervisor.ui

import androidx.compose.runtime.Composable
import com.asseta.core.domain.inbox.JobFigures
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.ui.components.LinkRow
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph

/** Job summary: opening/closing reading, meter hours, work totals per type and open/blocking findings. */
@Composable
fun JobSummarySection(snapshot: InboxSnapshot, jobId: String) {
    val opening = snapshot.jobReading(jobId, "OPENING")
    val closing = snapshot.jobReading(jobId, "CLOSING")
    val readings = snapshot.readingsOfJob(jobId)
    val totals = JobFigures.minutesByType(
        snapshot.activities.filter { it.jobId == jobId }.map { com.asseta.core.domain.inbox.WorkSpan(it.activityType, it.startMs, it.endMs) },
        System.currentTimeMillis(),
    )
    Section("Summary") {
        LabeledRow("Opening reading", opening?.reading ?: "Not captured")
        LabeledRow("Closing reading", closing?.reading ?: "Not captured")
        JobFigures.meterHours(opening?.reading, closing?.reading)?.let { LabeledRow("Meter hours", InboxTexts.hours(it)) }
        totals.forEach { (type, minutes) -> LabeledRow(FieldTexts.activityType(type), JobFigures.duration(minutes)) }
        val open = readings.sumOf { it.openFindings }
        val blocking = readings.sumOf { it.blockingFindings }
        LabeledRow("Open findings", "$open", if (open > 0) WarningColor else androidx.compose.ui.graphics.Color.Unspecified)
        if (blocking > 0) LabeledRow("Blocking findings", "$blocking", palette.offline)
    }
}

/** My readings of the job, newest first, each opening its detail. */
@Composable
fun JobReadingsSection(snapshot: InboxSnapshot, jobId: String, onRoute: (Route) -> Unit) {
    val readings = snapshot.readingsOfJob(jobId)
    if (readings.isEmpty()) return
    Section("Readings") {
        readings.forEach { r ->
            LinkRow(onClick = { onRoute(Route.ReadingDetail(r.id)) }) {
                InboxRow(InboxTexts.readingKind(r.kind) + " " + r.reading, r.status, LocalTime.format(r.atMs))
            }
        }
    }
}

/** The customer acknowledgement of the job: signer, method, confirmed hours and the signature. */
@Composable
fun AcknowledgementSection(field: FieldGraph, snapshot: InboxSnapshot, jobId: String) {
    val ack = snapshot.acknowledgements.filter { it.jobId == jobId }.maxByOrNull { it.atMs } ?: return
    Section("Acknowledgement") {
        LabeledRow("Status", "") { StatusPill(ack.status) }
        LabeledRow("Signer", ack.signerName)
        LabeledRow("Method", InboxTexts.ackMethod(ack.method))
        ack.signerPhone?.let { LabeledRow("Phone", it) }
        ack.hours?.let { LabeledRow("Confirmed hours", it) }
        LabeledRow("Recorded", LocalTime.format(ack.atMs))
        if (ack.method == "SIGNATURE") {
            val op = ack.op
            EvidenceImage(
                "Signature of ${ack.signerName}",
                local = op?.let { o -> { field.inbox.attachmentsOf(o.id).firstNotNullOfOrNull { field.inbox.localEvidence(it) } } },
                remoteUrl = ack.signatureAttachmentId?.let { id -> { field.online.attachmentUrl(id) } },
            )
        }
    }
}

/** Expenses and fuel recorded for the job. */
@Composable
fun JobMoneySection(snapshot: InboxSnapshot, jobId: String, onRoute: (Route) -> Unit) {
    val expenses = snapshot.expenses.filter { it.jobId == jobId }
    val fuel = snapshot.fuel.filter { it.jobId == jobId }
    if (expenses.isEmpty() && fuel.isEmpty()) return
    Section("Expenses & fuel") {
        expenses.forEach { e ->
            LinkRow(onClick = { onRoute(Route.ExpenseDetail(e.key)) }) {
                InboxRow(e.description.ifBlank { "Expense" }, e.status, InboxTexts.money(e.amount, e.currency) + " · " + LocalTime.format(e.atMs))
            }
        }
        fuel.forEach { f ->
            LinkRow(onClick = { onRoute(Route.FuelDetail(f.key)) }) {
                InboxRow("Fuel ${InboxTexts.fuelType(f.eventType).lowercase()} · ${InboxTexts.litres(f.litres)}", f.status, LocalTime.format(f.atMs))
            }
        }
    }
}
