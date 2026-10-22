package com.asseta.owner.ui.jobs

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.owner.data.JobDetail
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow
import java.time.ZoneId

class JobDetailViewModel(val data: OwnerData, jobId: String, refreshOn: Flow<Unit>) : SnapshotViewModel<JobDetail>({ data.job(jobId) }, refreshOn)

/** Job drilldown: meter vs billable hours (server-computed), charges, readings with photos, customer acknowledgement. */
@Composable
fun JobDetailScreen(vm: JobDetailViewModel, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { d ->
        val s = d.summary
        val job = s.job
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                SectionCard("Job ${job.jobNumber}") {
                    KeyValue("Status", OwnerFormat.humanize(job.status))
                    Text("Open machine", Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Machine(job.machineId.toString())) }, color = MaterialTheme.colorScheme.primary)
                    KeyValue("Planned start", OwnerFormat.dateTime(job.plannedStart, zone))
                    job.startedAt?.let { KeyValue("Started", OwnerFormat.dateTime(it, zone)) }
                    job.completedAt?.let { KeyValue("Completed", OwnerFormat.dateTime(it, zone)) }
                    KeyValue("Hourly rate", OwnerFormat.money(job.hourlyRate.value, job.currency))
                    KeyValue("Minimum hours", OwnerFormat.hours(job.minimumHours.value))
                }
            }
            item {
                SectionCard("Hours") {
                    KeyValue("Opening reading", s.openingReading?.toPlainString() ?: "—")
                    KeyValue("Closing reading", s.closingReading?.toPlainString() ?: "—")
                    KeyValue("Meter hours", OwnerFormat.hours(s.meterHours?.value))
                    KeyValue("Billable hours", OwnerFormat.hours(s.billableHours?.value))
                    KeyValue("Non-billable hours", OwnerFormat.hours(s.nonbillableHours.value))
                    s.standbyHours?.let { KeyValue("Standby hours", OwnerFormat.hours(it.value)) }
                    KeyValue("Billing ready", if (s.billingReady) "Yes" else "No")
                    if (s.openExceptions > 0) KeyValue("Open exceptions", "${s.openExceptions} (${s.blockingExceptions} blocking)")
                }
            }
            s.charges?.let { c ->
                item {
                    SectionCard("Charges") {
                        c.lines.forEach { l -> KeyValue("${l.description} (${l.quantity.toPlainString()})", OwnerFormat.money(l.amount.value, c.currency)) }
                        KeyValue("Subtotal", OwnerFormat.money(c.subtotal.value, c.currency))
                        KeyValue("Discount", OwnerFormat.money(c.discountTotal.value, c.currency))
                        KeyValue("Tax", OwnerFormat.money(c.taxTotal.value, c.currency))
                        KeyValue("Total", OwnerFormat.money(c.total.value, c.currency))
                    }
                }
            }
            item {
                SectionCard("Readings") {
                    if (d.captures.isEmpty()) Text("No readings yet.")
                    d.captures.forEach { c ->
                        Text(
                            "${OwnerFormat.humanize(c.kind)} ${c.reading.toPlainString()} · ${OwnerFormat.humanize(c.state)} · ${OwnerFormat.dateTime(c.capturedAt, zone)}" +
                                (c.ocrConfidence?.let { " · OCR ${(it * 100).toInt()}%" } ?: "") + if (c.manuallyCorrected) " · corrected" else "",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        c.photoAttachmentId?.let { id -> EvidencePhoto("meter photo", online && !state.stale) { vm.data.attachmentUrl(id.toString()) } }
                    }
                }
            }
            item {
                SectionCard("Customer acknowledgement") {
                    if (d.acknowledgements.isEmpty()) Text("Not acknowledged yet.")
                    d.acknowledgements.forEach { a ->
                        KeyValue("Signed by", a.signerName)
                        KeyValue("Method", OwnerFormat.humanize(a.method))
                        KeyValue("Hours acknowledged", OwnerFormat.hours(a.acknowledgedHours?.value))
                        KeyValue("When", OwnerFormat.dateTime(a.capturedAt, zone))
                        a.signatureAttachmentId?.let { id -> EvidencePhoto("signature", online && !state.stale) { vm.data.attachmentUrl(id.toString()) } }
                    }
                }
            }
        }
    }
}
