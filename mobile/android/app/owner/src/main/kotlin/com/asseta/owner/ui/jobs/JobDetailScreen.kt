package com.asseta.owner.ui.jobs

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.JobSummaryDto
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.NavigationRow
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.JobDetail
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.ReadingRow
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import java.time.ZoneId

class JobDetailViewModel(val data: OwnerData, jobId: String, refreshOn: Flow<Unit>) : SnapshotViewModel<JobDetail>({ data.job(jobId) }, refreshOn)

/** Job detail wording shared with iOS (`JobDetailView`). */
object JobDetailText {
    const val NO_CHARGES = "Charges appear once both readings are in."

    fun billing(s: JobSummaryDto): String = when {
        s.billingReady -> "Ready to invoice."
        s.blockingExceptions > 0 -> "Not ready to invoice: ${s.blockingExceptions} blocking exception(s)."
        else -> "Not ready to invoice."
    }

    fun exceptions(open: Int): String? = if (open > 0) "$open open exception(s) need review in the console." else null
}

/** Job drilldown: meter vs billable hours (server-computed), charges, readings with photos, customer acknowledgement. */
@Composable
fun JobDetailScreen(vm: JobDetailViewModel, features: OwnerFeatures, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { d ->
        val s = d.summary
        val job = s.job
        val zone = ZoneId.systemDefault()
        val photosOnline = online && !state.stale
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard("Job") {
                    KeyValue("Number", job.jobNumber)
                    LabeledValue("Status") { StatusPill(OwnerFormat.humanize(job.status), JobsPresentation.statusColor(job.status)) }
                    KeyValue("Planned start", OwnerFormat.dateTime(job.plannedStart, zone))
                    job.startedAt?.let { KeyValue("Started", OwnerFormat.dateTime(it, zone)) }
                    job.completedAt?.let { KeyValue("Completed", OwnerFormat.dateTime(it, zone)) }
                    KeyValue("Hourly rate", OwnerFormat.money(job.hourlyRate.value, job.currency))
                    KeyValue("Minimum hours", OwnerFormat.hours(job.minimumHours.value))
                    if (features.fleet) {
                        NavigationRow("Open machine") { onOpen(OwnerDestination.Machine(job.machineId.toString())) }
                    }
                }
            }
            item {
                SectionCard("Hours") {
                    KeyValue("Opening reading", s.openingReading?.toPlainString() ?: "—")
                    KeyValue("Closing reading", s.closingReading?.toPlainString() ?: "—")
                    KeyValue("Meter hours", OwnerFormat.hours(s.meterHours?.value))
                    KeyValue("Non-billable hours", OwnerFormat.hours(s.nonbillableHours.value))
                    s.standbyHours?.let { KeyValue("Standby hours", OwnerFormat.hours(it.value)) }
                    KeyValue("Billable hours", OwnerFormat.hours(s.billableHours?.value))
                }
            }
            item {
                SectionCard("Charges", footer = JobDetailText.billing(s)) {
                    val c = s.charges
                    if (c == null) {
                        Text(JobDetailText.NO_CHARGES, color = palette.secondaryText)
                    } else {
                        c.lines.forEach { l -> KeyValue("${l.description} (${l.quantity.toPlainString()})", OwnerFormat.money(l.amount.value, c.currency)) }
                        KeyValue("Subtotal", OwnerFormat.money(c.subtotal.value, c.currency))
                        KeyValue("Discount", OwnerFormat.money(c.discountTotal.value, c.currency))
                        KeyValue("Tax", OwnerFormat.money(c.taxTotal.value, c.currency))
                        LabeledValue("Total") { Text(OwnerFormat.money(c.total.value, c.currency), style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold) }
                    }
                    JobDetailText.exceptions(s.openExceptions)?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                }
            }
            item {
                SectionCard("Readings") {
                    if (d.captures.isEmpty()) Text("No readings yet.", color = palette.secondaryText)
                    d.captures.forEach { c -> ReadingRow(c, zone, photosOnline) { vm.data.attachmentUrl(it) } }
                }
            }
            item {
                SectionCard("Customer acknowledgement") {
                    if (d.acknowledgements.isEmpty()) Text("Not acknowledged yet.", color = palette.secondaryText)
                    d.acknowledgements.forEach { a ->
                        // One row per acknowledgement, as on iOS (`AcknowledgementRow`).
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            KeyValue("Signed by", a.signerName)
                            KeyValue("Method", OwnerFormat.humanize(a.method))
                            KeyValue("Hours acknowledged", OwnerFormat.hours(a.acknowledgedHours?.value))
                            KeyValue("When", OwnerFormat.dateTime(a.capturedAt, zone))
                            a.signatureAttachmentId?.let { id -> EvidencePhoto("signature", photosOnline) { vm.data.attachmentUrl(id.toString()) } }
                        }
                    }
                }
            }
        }
    }
}
