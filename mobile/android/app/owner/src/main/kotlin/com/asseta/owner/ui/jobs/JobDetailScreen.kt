package com.asseta.owner.ui.jobs

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.ActivityDto
import com.asseta.core.model.owner.JobSummaryDto
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.NavigationRow
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.JobDetail
import com.asseta.owner.data.OwnerData
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.ui.components.GroupedSection
import com.asseta.owner.data.ActionResult
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.approvals.JobApprovalText
import com.asseta.owner.ui.approvals.JobDecisionCard
import com.asseta.owner.ui.approvals.JobRequestCard
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.ReadingRow
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import com.asseta.owner.ui.home.KpiTone
import com.asseta.owner.ui.spend.ExpenseRow
import com.asseta.owner.ui.spend.FuelRow
import com.asseta.owner.ui.spend.SpendText
import kotlinx.coroutines.flow.Flow
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.Duration
import java.time.Instant
import java.time.ZoneId

/** [spend]: the role may read expenses, so the job's expenses and fuel are loaded too. */
class JobDetailViewModel(val data: OwnerData, private val jobId: String, spend: Boolean, refreshOn: Flow<Unit>) :
    SnapshotViewModel<JobDetail>({ data.job(jobId, spend) }, refreshOn) {
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    /** Approve (with [hourlyRate] for a job without a rate card) and reload the job. */
    fun approve(hourlyRate: String?) = decide(JobApprovalText.APPROVED) { data.approveJob(jobId, hourlyRate) }

    /** Decline with the reason the supervisor is told (CANCEL). */
    fun decline(reason: String) {
        if (JobApprovalText.canDecline(reason)) decide(JobApprovalText.DECLINED) { data.declineJob(jobId, reason) }
    }

    private fun decide(done: String, call: suspend () -> ActionResult<*>) {
        if (_busy.value) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = call()) {
                is ActionResult.Done -> {
                    _message.value = done
                    refresh()
                }
                is ActionResult.Refused -> {
                    _error.value = JobApprovalText.error(r.code, r.error.message)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

/** Job detail wording shared with iOS (`JobDetailView`). */
object JobDetailText {
    const val NO_CHARGES = "Charges appear once both readings are in."

    fun billing(s: JobSummaryDto): String = when {
        s.billingReady -> "Ready to invoice."
        s.blockingExceptions > 0 -> "Not ready to invoice: ${s.blockingExceptions} blocking exception(s)."
        else -> "Not ready to invoice."
    }

    fun exceptions(open: Int): String? = if (open > 0) "$open open exception(s) need review." else null

    const val NO_WORK = "No work logged yet."
    const val BILLABLE = "Billable"
    const val NOT_BILLABLE = "Not billable"

    fun billableTone(billable: Boolean): KpiTone = if (billable) KpiTone.GOOD else KpiTone.MUTED

    /**
     * "21 Oct 2026, 08:00 – 21 Oct 2026, 12:30 · 4.5 h": whole minutes as hours; an activity without an end reads
     * "… – ongoing" with the time elapsed until [nowMs].
     */
    fun workLogDetail(a: ActivityDto, zone: ZoneId, nowMs: Long = System.currentTimeMillis()): String {
        val start = OwnerFormat.parseInstant(a.startedAt)
        val end = OwnerFormat.parseInstant(a.endedAt)
        val to = if (end == null) "ongoing" else OwnerFormat.dateTime(end, zone)
        val minutes = start?.let { Duration.between(it, end ?: Instant.ofEpochMilli(nowMs)).toMinutes().coerceAtLeast(0) } ?: 0
        val hours = BigDecimal.valueOf(minutes).divide(BigDecimal(60), 4, RoundingMode.HALF_EVEN)
        return "${OwnerFormat.dateTime(start, zone)} – $to · ${OwnerFormat.hours(hours)}"
    }
}

/**
 * Job drilldown: meter vs billable hours (server-computed), charges, readings with photos, work log, expenses and fuel
 * (when the role may read expenses), customer acknowledgement.
 */
@Composable
fun JobDetailScreen(vm: JobDetailViewModel, session: OwnerSession, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val features = session.features
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
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
            item { JobRequestCard(job) }
            if (job.status == "CANCELLED") job.cancellationReason?.takeIf { it.isNotBlank() }?.let { reason ->
                item { SectionCard(null) { KeyValue(JobApprovalText.REASON, reason) } }
            }
            if (job.status == "PENDING_APPROVAL" && features.approveJobs) item {
                JobDecisionCard(
                    job, session.can(OwnerAction.DECIDE_JOB, online, state.snapshot?.source), busy, error,
                    onApprove = vm::approve, onDecline = vm::decline,
                )
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
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
                    JobDetailText.exceptions(s.openExceptions)?.let {
                        // Opens this job's exceptions when the role can read meter evidence.
                        val open = if (features.meterEvidence) Modifier.clickable(role = Role.Button) { onOpen(OwnerDestination.Exceptions(job.id.toString())) } else Modifier
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = open)
                    }
                }
            }
            item {
                SectionCard("Readings") {
                    if (d.captures.isEmpty()) Text("No readings yet.", color = palette.secondaryText)
                    d.captures.forEach { c -> ReadingRow(c, zone, photosOnline) { vm.data.attachmentUrl(it) } }
                }
            }
            item {
                SectionCard("Work log") {
                    if (d.activities.isEmpty()) Text(JobDetailText.NO_WORK, color = palette.secondaryText)
                    d.activities.forEach { a -> WorkLogRow(a, zone) }
                }
            }
            d.expenses?.let { expenses ->
                item {
                    SectionCard("Expenses", footer = SpendText.totalApproved(expenses).joinToString("\n").ifEmpty { null }) {
                        if (expenses.isEmpty()) Text(SpendText.NO_JOB_EXPENSES, color = palette.secondaryText)
                        expenses.forEach { e -> ExpenseRow(e, zone) }
                    }
                }
            }
            d.fuel?.let { fuel ->
                item {
                    SectionCard("Fuel") {
                        if (fuel.isEmpty()) Text(SpendText.NO_JOB_FUEL, color = palette.secondaryText)
                        fuel.forEach { f -> FuelRow(f, zone) }
                    }
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

/** One work-log entry: activity, period and duration, billable pill, note. */
@Composable
private fun WorkLogRow(a: ActivityDto, zone: ZoneId) {
    Column(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(OwnerFormat.humanize(a.activityType), style = AssetaType.headline, modifier = Modifier.weight(1f))
            StatusPill(if (a.billable) JobDetailText.BILLABLE else JobDetailText.NOT_BILLABLE, OwnerColors.tone(JobDetailText.billableTone(a.billable)))
        }
        Text(JobDetailText.workLogDetail(a, zone), style = AssetaType.subheadline, color = palette.secondaryText)
        a.note?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
    }
}
