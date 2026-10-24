package com.asseta.owner.ui.approvals

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.finance.AmountInput
import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerErrors
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.JobDto
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import java.time.ZoneId

/**
 * Job approval wording and rules shared with iOS: jobs waiting for approval (office-created or requested from the field
 * by a supervisor) are approved -- priced first when no rate card applies (rate source PENDING_PRICE) -- or declined
 * with a reason (CANCEL).
 */
object JobApprovalText {
    const val SECTION = "Jobs"
    const val PENDING_STATUS = "PENDING_APPROVAL"
    const val EMPTY = "No jobs waiting for approval."
    const val REQUEST = "Request"
    const val DECISION = "Decision"
    const val APPROVE = "Approve"
    const val DECLINE = "Decline"
    const val CANCEL = "Cancel"
    const val APPROVE_TITLE = "Approve this job?"
    const val DECLINE_TITLE = "Decline this job?"
    const val REASON = "Reason"
    const val PRICE_HELPER = "No rate card applies — set the price to approve"
    const val HOURLY_RATE = "Hourly rate"
    const val APPROVED = "Job approved."
    const val DECLINED = "Job declined."

    fun requestedBy(name: String?): String = "Requested from the field by ${name?.takeIf { it.isNotBlank() } ?: "a supervisor"}"

    /** Whether the job came from a supervisor's field request. */
    fun fromField(job: JobDto): Boolean = job.requestedByStaffId != null

    fun rateLabel(currency: String): String = "Hourly rate ($currency)"

    /** The hourly rate typed in the approve dialog: a positive amount, or null when not valid. */
    fun rate(text: String): String? =
        (AmountParser.parse(text.trim(), DecimalLimit.MONEY) as? AmountInput.Valid)?.value?.toPlainString()

    /** Approve is possible once a PENDING_PRICE job has a valid rate; other jobs keep their rate. */
    fun canApprove(job: JobDto, rateText: String): Boolean = !job.pendingPrice || rate(rateText) != null

    /** Declining needs a reason (the supervisor is told). */
    fun canDecline(reason: String): Boolean = reason.isNotBlank()

    /** Friendly wording of a refused decision (PRICE_REQUIRED, ...). */
    fun error(code: String?, serverMessage: String): String = code?.let { OwnerErrors.message(it, serverMessage) } ?: serverMessage

    /** "Planned 24 Oct 2026, 08:00": the planned start line of a waiting job. */
    fun plannedLine(job: JobDto, zone: ZoneId): String = "Planned ${OwnerFormat.dateTime(job.plannedStart, zone)}"
}

/** A row of the Approvals "Jobs" section: number, who requested it from the field, the planned start and the note. */
@Composable
fun JobApprovalRow(job: JobDto, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(job.jobNumber, style = AssetaType.headline)
        if (JobApprovalText.fromField(job)) {
            Text(JobApprovalText.requestedBy(job.requestedByName), style = AssetaType.subheadline, color = palette.secondaryText)
        }
        Text(JobApprovalText.plannedLine(job, zone), style = AssetaType.caption, color = palette.secondaryText)
        job.requestNote?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
    }
}

/** "Request" card of a field-requested job: who asked and what the customer asked for. */
@Composable
fun JobRequestCard(job: JobDto) {
    if (!JobApprovalText.fromField(job) && job.requestNote.isNullOrBlank()) return
    SectionCard(JobApprovalText.REQUEST) {
        if (JobApprovalText.fromField(job)) Text(JobApprovalText.requestedBy(job.requestedByName), style = AssetaType.subheadline)
        job.requestNote?.takeIf { it.isNotBlank() }?.let { KeyValue("What the customer asked for", it) }
    }
}

/**
 * Approve / Decline of a job waiting for approval (job detail). Approve opens a dialog asking for the hourly rate when
 * no rate card applies; Decline asks for the reason.
 */
@Composable
fun JobDecisionCard(
    job: JobDto,
    gate: MutationCheck,
    busy: Boolean,
    error: String?,
    onApprove: (hourlyRate: String?) -> Unit,
    onDecline: (reason: String) -> Unit,
) {
    var approving by rememberSaveable { mutableStateOf(false) }
    var declining by rememberSaveable { mutableStateOf(false) }
    var rate by rememberSaveable { mutableStateOf("") }
    var reason by rememberSaveable { mutableStateOf("") }
    SectionCard(JobApprovalText.DECISION) {
        if (gate is MutationCheck.Blocked) {
            BlockedNote(gate.reason)
            return@SectionCard
        }
        if (!job.pendingPrice) KeyValue(JobApprovalText.HOURLY_RATE, OwnerFormat.money(job.hourlyRate.value, job.currency))
        // Same layout as the other decisions: green prominent "Approve" and a bordered red "Decline".
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Button(
                { approving = true }, enabled = !busy, modifier = Modifier.testTag("approve-job-${job.id}"),
                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White),
                shape = RoundedCornerShape(8.dp),
            ) { Text(JobApprovalText.APPROVE) }
            Spacer(Modifier.weight(1f))
            Button(
                { declining = true }, enabled = !busy, modifier = Modifier.testTag("decline-job-${job.id}"),
                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Critical.copy(alpha = 0.15f), contentColor = OwnerColors.Critical),
                shape = RoundedCornerShape(8.dp),
            ) { Text(JobApprovalText.DECLINE) }
        }
        error?.let {
            Text(
                it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
                modifier = Modifier.testTag("job-decision-error").semantics { liveRegion = LiveRegionMode.Assertive },
            )
        }
    }
    if (approving) {
        AlertDialog(
            onDismissRequest = { approving = false },
            title = { Text(JobApprovalText.APPROVE_TITLE) },
            text = {
                if (job.pendingPrice) {
                    OutlinedTextField(
                        rate, { v -> rate = v.filter { it.isDigit() || it == '.' } }, Modifier.fillMaxWidth().testTag("job-rate"),
                        label = { Text(JobApprovalText.rateLabel(job.currency)) },
                        supportingText = { Text(JobApprovalText.PRICE_HELPER) },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true,
                    )
                } else {
                    KeyValue(JobApprovalText.HOURLY_RATE, OwnerFormat.money(job.hourlyRate.value, job.currency))
                }
            },
            confirmButton = {
                TextButton(
                    { approving = false; onApprove(if (job.pendingPrice) JobApprovalText.rate(rate) else null) },
                    enabled = JobApprovalText.canApprove(job, rate),
                ) { Text(JobApprovalText.APPROVE) }
            },
            dismissButton = { TextButton({ approving = false }) { Text(JobApprovalText.CANCEL) } },
        )
    }
    if (declining) {
        AlertDialog(
            onDismissRequest = { declining = false },
            title = { Text(JobApprovalText.DECLINE_TITLE) },
            text = {
                OutlinedTextField(reason, { reason = it.take(1000) }, Modifier.fillMaxWidth().testTag("job-reason"),
                    label = { Text(JobApprovalText.REASON) }, minLines = 2)
            },
            confirmButton = {
                TextButton({ declining = false; onDecline(reason) }, enabled = JobApprovalText.canDecline(reason)) {
                    Text(JobApprovalText.DECLINE, color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton({ declining = false }) { Text(JobApprovalText.CANCEL) } },
        )
    }
}
