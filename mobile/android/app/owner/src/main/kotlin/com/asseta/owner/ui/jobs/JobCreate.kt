package com.asseta.owner.ui.jobs

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.finance.AmountInput
import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.owner.OwnerErrors
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.ContractDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.JobIn
import com.asseta.core.model.owner.JobSiteDto
import com.asseta.core.model.owner.MachineDto
import com.asseta.core.model.owner.StaffDto
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.approvals.JobApprovalText
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit
import java.util.UUID

/** Where the hourly price comes from: the rate card in force at the planned start (server-resolved) or a negotiated rate. */
enum class RateMode { RATE_CARD, NEGOTIATED }

/** Fields that can carry a validation message. */
enum class JobField { CONTRACT, JOB_NUMBER, MACHINE, SUPERVISOR, PLANNED_END, HOURLY_RATE, MINIMUM_HOURS }

/** The "New job" form (same rules as the web job form; the standby/fee/discount/tax terms take the web defaults). */
data class JobForm(
    val plannedStart: Instant,
    val contract: ContractDto? = null,
    /** Typed by the user, as on the web (required, at most 32 characters, no suggestion). */
    val jobNumber: String = "",
    val machine: MachineDto? = null,
    val supervisor: StaffDto? = null,
    /** Empty = the contract's default site. */
    val site: JobSiteDto? = null,
    val plannedEnd: Instant? = null,
    val rateMode: RateMode = RateMode.RATE_CARD,
    val hourlyRate: String = "",
    val minimumHours: String = "",
    /** Approve right away (only offered with `tenant.job.approve`). */
    val approveNow: Boolean = false,
)

/** "New job" wording and rules shared with iOS. */
object JobCreateText {
    const val NEW_JOB = "New job"
    const val TITLE = "New job"
    const val CONTRACT = "Customer contract"
    const val MACHINE = "Machine"
    const val SUPERVISOR = "Supervisor"
    const val SITE = "Site (optional)"
    const val PLANNED_START = "Planned start"
    const val PLANNED_END = "Planned end (optional)"
    const val JOB_NUMBER = "Job number"
    const val PRICE = "Price"
    const val RATE_CARD = "Rate card"
    const val NEGOTIATED = "Negotiated rate"
    const val MINIMUM_HOURS = "Minimum hours (optional)"
    const val APPROVE_NOW = "Approve now"
    const val CREATE_AND_APPROVE = "Create and approve"
    const val CREATE = "Create"
    const val CANCEL = "Cancel"

    const val CHOOSE_CONTRACT = "Choose the customer contract."
    const val CHOOSE_MACHINE = "Choose the machine."
    const val CHOOSE_SUPERVISOR = "Choose the supervisor."
    const val ENTER_RATE = "Enter the hourly rate."
    const val END_BEFORE_START = "The planned end is before the planned start."

    const val SEND_FOR_APPROVAL = "Send for approval"

    // Wording not in the spec (identical on iOS).
    const val ENTER_JOB_NUMBER = "Enter the job number."
    const val JOB_NUMBER_TOO_LONG = "The job number is at most 32 characters."
    const val INVALID_MINIMUM_HOURS = "Enter the minimum hours as a number."
    const val CHOOSE = "Choose"
    const val SEARCH = "Search"
    const val NO_MATCHES = "No matches."
    const val NO_SITE = "None"
    const val SUPERVISOR_FALLBACK = "a supervisor"

    // Android date/time dialog buttons (iOS uses the system DatePicker).
    const val NEXT = "Next"
    const val OK = "OK"

    /** Planned end, when switched on, starts 8 hours after the planned start. */
    const val DEFAULT_END_HOURS = 8L

    /** Job numbers are at most 32 characters (server `JobIn`). */
    const val JOB_NUMBER_MAX = 32

    fun rateLabel(currency: String?): String = currency?.let { JobApprovalText.rateLabel(it) } ?: JobApprovalText.HOURLY_RATE

    fun primary(approveNow: Boolean): String = if (approveNow) CREATE_AND_APPROVE else CREATE

    fun contractLabel(c: ContractDto): String = c.reference?.takeIf { it.isNotBlank() }?.let { "${c.contractNumber} · $it" } ?: c.contractNumber
    fun machineLabel(m: MachineDto): String = "${m.assetCode} · ${m.name}"
    fun siteLabel(s: JobSiteDto): String = "${s.code} · ${s.name}"
    fun staffLabel(s: StaffDto): String = s.fullName

    /** Minimum hours: a plain decimal >= 0, else null. */
    private fun hours(text: String): String? = AmountParser.valueOrNull(text, DecimalLimit.MONEY, allowZero = true)?.toPlainString()

    private fun rate(text: String): String? = (AmountParser.parse(text, DecimalLimit.MONEY) as? AmountInput.Valid)?.value?.toPlainString()

    /** Validation messages per field (empty = the form can be sent), first failing rule per field. */
    fun errors(form: JobForm): Map<JobField, String> = buildMap {
        if (form.contract == null) put(JobField.CONTRACT, CHOOSE_CONTRACT)
        val number = form.jobNumber.trim()
        if (number.isEmpty()) put(JobField.JOB_NUMBER, ENTER_JOB_NUMBER) else if (number.length > JOB_NUMBER_MAX) put(JobField.JOB_NUMBER, JOB_NUMBER_TOO_LONG)
        if (form.machine == null) put(JobField.MACHINE, CHOOSE_MACHINE)
        if (form.supervisor == null) put(JobField.SUPERVISOR, CHOOSE_SUPERVISOR)
        if (form.plannedEnd != null && !form.plannedEnd.isAfter(form.plannedStart)) put(JobField.PLANNED_END, END_BEFORE_START)
        if (form.rateMode == RateMode.NEGOTIATED && rate(form.hourlyRate) == null) put(JobField.HOURLY_RATE, ENTER_RATE)
        if (form.minimumHours.isNotBlank() && hours(form.minimumHours) == null) put(JobField.MINIMUM_HOURS, INVALID_MINIMUM_HOURS)
    }

    /** The createJob body (same as the web's `toJobPayload`): no hourly rate for the rate card. Call on a valid form. */
    fun toJobIn(form: JobForm): JobIn = JobIn(
        contractId = form.contract!!.id.toString(),
        jobNumber = form.jobNumber.trim(),
        machineId = form.machine!!.id.toString(),
        plannedStart = form.plannedStart.truncatedTo(ChronoUnit.SECONDS).toString(),
        jobSiteId = form.site?.id?.toString(),
        supervisorId = form.supervisor?.id?.toString(),
        plannedEnd = form.plannedEnd?.truncatedTo(ChronoUnit.SECONDS)?.toString(),
        hourlyRate = if (form.rateMode == RateMode.NEGOTIATED) rate(form.hourlyRate) else null,
        minimumHours = form.minimumHours.trim().takeIf { it.isNotEmpty() }?.let(::hours),
    )

    /** "Job J-7 created and assigned to Juma." / "Job J-7 created and sent for approval." */
    fun done(job: JobDto, supervisor: String?, approved: Boolean): String =
        if (approved) "Job ${job.jobNumber} created and assigned to ${supervisor?.trim()?.takeIf { it.isNotEmpty() } ?: SUPERVISOR_FALLBACK}." else "Job ${job.jobNumber} created and sent for approval."

    /** Same hints as the web job form; anything else as the other owner actions ([fallback], already worded). */
    fun message(code: String?, fallback: String): String = when (code) {
        "NO_RATE" -> OwnerErrors.NO_RATE
        "DUPLICATE_JOB" -> OwnerErrors.DUPLICATE_JOB
        "MACHINE_BUSY" -> "This machine already has an approved or running job; complete or cancel that job first."
        "CONTRACT_NOT_ACTIVE" -> "Choose an active contract."
        "MACHINE_INACTIVE" -> "The chosen machine is retired; choose an active machine."
        "SITE_INACTIVE" -> "The chosen job site is inactive; choose an active site."
        "STAFF_INACTIVE" -> "The chosen supervisor is inactive; choose an active staff member."
        else -> fallback
    }

    /** The job exists, but a later step was refused ([submitted]: SUBMIT went through, APPROVE did not). */
    fun partial(job: JobDto, submitted: Boolean, error: String): String =
        if (submitted) "Job ${job.jobNumber} was created and sent for approval, but not approved: $error"
        else "Job ${job.jobNumber} was created but not sent for approval: $error"
}

/** Progress of one form visit: [created] once the job exists (never created again), [error] the latest refusal. */
data class JobCreateStatus(
    val busy: Boolean = false,
    val showErrors: Boolean = false,
    val error: String? = null,
    val created: JobDto? = null,
)

/** How a create attempt ended (besides "not created", which keeps the form open with the error). */
sealed interface JobCreateOutcome {
    /** Every step went through; [message] is the toast. */
    data class Done(val job: JobDto, val message: String) : JobCreateOutcome

    /** The job exists (DRAFT or PENDING_APPROVAL) but SUBMIT or APPROVE was refused: open the job with [message]. */
    data class Partly(val job: JobDto, val message: String) : JobCreateOutcome
}

/**
 * One visit of the "New job" form: create, SUBMIT, and APPROVE when "Approve now" is on, in sequence, each step with its
 * own Idempotency-Key kept for the visit (a lost response is replayed by the server). A refused create created nothing,
 * so the corrected retry gets a new create key. Once the job exists it is never created again.
 */
class JobCreateModel(
    private val data: OwnerData,
    private val scope: CoroutineScope,
    val canApprove: Boolean,
    now: Instant,
    private val onOutcome: (JobCreateOutcome) -> Unit,
    private val newKey: () -> String = { UUID.randomUUID().toString() },
) {
    private var createKey = newKey()
    private val submitKey = newKey()
    private val approveKey = newKey()

    private val _form = MutableStateFlow(JobForm(plannedStart = now.truncatedTo(ChronoUnit.MINUTES), approveNow = canApprove))
    val form: StateFlow<JobForm> = _form.asStateFlow()
    private val _status = MutableStateFlow(JobCreateStatus())
    val status: StateFlow<JobCreateStatus> = _status.asStateFlow()

    fun update(transform: (JobForm) -> JobForm) {
        if (_status.value.created == null) _form.update(transform)
    }

    /** Planned end on (start + 8 h, or the end already chosen) or off. */
    fun setPlannedEnd(on: Boolean) = update {
        it.copy(plannedEnd = if (on) it.plannedEnd ?: it.plannedStart.plus(JobCreateText.DEFAULT_END_HOURS, ChronoUnit.HOURS) else null)
    }

    suspend fun searchContracts(q: String) = data.searchContracts(q)
    suspend fun searchMachines(q: String) = data.searchMachines(q)
    suspend fun searchSupervisors(q: String) = data.searchSupervisors(q)
    suspend fun searchSites(q: String) = data.searchJobSites(q)

    fun submit() {
        val start = _status.value
        if (start.busy) return
        val form = _form.value
        if (start.created == null && JobCreateText.errors(form).isNotEmpty()) {
            _status.update { it.copy(showErrors = true) }
            return
        }
        _status.update { it.copy(busy = true, showErrors = true, error = null) }
        val approve = canApprove && form.approveNow
        scope.launch {
            var job = start.created ?: when (val r = data.createJob(JobCreateText.toJobIn(form), createKey)) {
                is ActionResult.Done -> r.value
                is ActionResult.Refused -> {
                    // A server refusal created nothing; only a lost response (no code) may have, so keep its key.
                    if (r.code != null) createKey = newKey()
                    _status.update { it.copy(busy = false, error = JobCreateText.message(r.code, r.error.message)) }
                    return@launch
                }
            }
            _status.update { it.copy(created = job) }
            if (job.status == DRAFT) {
                when (val r = data.submitJob(job.id.toString(), submitKey)) {
                    is ActionResult.Done -> job = r.value
                    is ActionResult.Refused -> return@launch partly(job, JobCreateText.partial(job, submitted = false, JobCreateText.message(r.code, r.error.message)))
                }
            }
            if (approve && job.status == PENDING) {
                when (val r = data.approveNewJob(job.id.toString(), approveKey)) {
                    is ActionResult.Done -> job = r.value
                    is ActionResult.Refused -> return@launch partly(job, JobCreateText.partial(job, submitted = true, JobCreateText.message(r.code, r.error.message)))
                }
            }
            onOutcome(JobCreateOutcome.Done(job, JobCreateText.done(job, form.supervisor?.fullName, approved = approve)))
            _status.update { it.copy(busy = false, created = job) }
        }
    }

    private fun partly(job: JobDto, message: String) {
        onOutcome(JobCreateOutcome.Partly(job, message))
        _status.update { it.copy(busy = false, created = job, error = message) }
    }

    private companion object {
        const val DRAFT = "DRAFT"
        const val PENDING = "PENDING_APPROVAL"
    }
}

/**
 * Notice for a job created by "New job" whose SUBMIT or APPROVE was refused: the form closes and the job detail shows
 * it once (job id -> message).
 */
object JobNotices {
    private val pending = java.util.concurrent.ConcurrentHashMap<String, String>()

    fun put(jobId: String, message: String) { pending[jobId] = message }

    fun take(jobId: String): String? = pending.remove(jobId)
}

/** Full-screen "New job" form. */
@Composable
fun JobCreateDialog(model: JobCreateModel, showSite: Boolean, onDismiss: () -> Unit) {
    val form by model.form.collectAsStateWithLifecycle()
    val status by model.status.collectAsStateWithLifecycle()
    Dialog(onDismissRequest = { if (!status.busy) onDismiss() }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = palette.groupedBackground) {
            Column(Modifier.fillMaxSize().imePadding()) {
                Text(JobCreateText.TITLE, style = AssetaType.navTitle, modifier = Modifier.padding(16.dp).semantics { heading() })
                JobFormFields(model, form, status, showSite, Modifier.weight(1f))
                Footer(model, form, status, onDismiss)
            }
        }
    }
}

@Composable
private fun JobFormFields(model: JobCreateModel, form: JobForm, status: JobCreateStatus, showSite: Boolean, modifier: Modifier) {
    val all = JobCreateText.errors(form)
    // Field errors appear once the user tried to create (the end-before-start one at once), as on iOS.
    val errors = if (status.showErrors) all else all.filterKeys { it == JobField.PLANNED_END }
    val enabled = !status.busy
    Column(modifier.verticalScroll(rememberScrollState()).padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SearchPickerField(
            JobCreateText.CONTRACT, form.contract, JobCreateText::contractLabel, errors[JobField.CONTRACT], enabled, "job-contract",
            search = model::searchContracts, onPick = { c -> model.update { it.copy(contract = c) } },
        )
        SearchPickerField(
            JobCreateText.MACHINE, form.machine, JobCreateText::machineLabel, errors[JobField.MACHINE], enabled, "job-machine",
            search = model::searchMachines, onPick = { m -> model.update { it.copy(machine = m) } },
        )
        SearchPickerField(
            JobCreateText.SUPERVISOR, form.supervisor, JobCreateText::staffLabel, errors[JobField.SUPERVISOR], enabled, "job-supervisor",
            search = model::searchSupervisors, onPick = { s -> model.update { it.copy(supervisor = s) } },
        )
        if (showSite) {
            SearchPickerField(
                JobCreateText.SITE, form.site, JobCreateText::siteLabel, null, enabled, "job-site",
                search = model::searchSites, onPick = { s -> model.update { it.copy(site = s) } },
                onNone = { model.update { it.copy(site = null) } },
            )
        }
        OutlinedTextField(
            form.jobNumber, { v -> model.update { it.copy(jobNumber = v) } },
            Modifier.fillMaxWidth().testTag("job-number"), enabled = enabled, singleLine = true,
            label = { Text(JobCreateText.JOB_NUMBER) }, isError = errors[JobField.JOB_NUMBER] != null,
            supportingText = errors[JobField.JOB_NUMBER]?.let { { Text(it) } },
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters, autoCorrectEnabled = false),
        )
        DateTimeRow(JobCreateText.PLANNED_START, form.plannedStart, null, enabled, "job-start", onPick = { t -> model.update { it.copy(plannedStart = t) } })
        Row(
            Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("job-end-toggle")
                .toggleable(form.plannedEnd != null, enabled = enabled, role = Role.Switch, onValueChange = model::setPlannedEnd),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(JobCreateText.PLANNED_END, Modifier.weight(1f))
            Switch(form.plannedEnd != null, onCheckedChange = null, enabled = enabled)
        }
        form.plannedEnd?.let { end ->
            DateTimeRow(JobCreateText.PLANNED_END, end, errors[JobField.PLANNED_END], enabled, "job-end", onPick = { t -> model.update { it.copy(plannedEnd = t) } })
        }
        Text(JobCreateText.PRICE, style = MaterialTheme.typography.labelLarge)
        Column(Modifier.selectableGroup()) {
            listOf(RateMode.RATE_CARD to JobCreateText.RATE_CARD, RateMode.NEGOTIATED to JobCreateText.NEGOTIATED).forEach { (mode, label) ->
                Row(
                    Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("job-rate-${mode.name}")
                        .selectable(form.rateMode == mode, enabled = enabled, role = Role.RadioButton) { model.update { it.copy(rateMode = mode) } },
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RadioButton(form.rateMode == mode, onClick = null, enabled = enabled)
                    Text(label, Modifier.padding(start = 12.dp))
                }
            }
        }
        if (form.rateMode == RateMode.NEGOTIATED) {
            OutlinedTextField(
                form.hourlyRate, { v -> model.update { it.copy(hourlyRate = v.filter { c -> c.isDigit() || c == '.' }) } },
                Modifier.fillMaxWidth().testTag("job-hourly-rate"), enabled = enabled, singleLine = true,
                label = { Text(JobCreateText.rateLabel(form.contract?.currency)) }, isError = errors[JobField.HOURLY_RATE] != null,
                supportingText = errors[JobField.HOURLY_RATE]?.let { { Text(it) } },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            )
        }
        OutlinedTextField(
            form.minimumHours, { v -> model.update { it.copy(minimumHours = v.filter { c -> c.isDigit() || c == '.' }) } },
            Modifier.fillMaxWidth().testTag("job-minimum-hours"), enabled = enabled, singleLine = true,
            label = { Text(JobCreateText.MINIMUM_HOURS) }, isError = errors[JobField.MINIMUM_HOURS] != null,
            supportingText = errors[JobField.MINIMUM_HOURS]?.let { { Text(it) } },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        )
        Spacer(Modifier.heightIn(min = 8.dp))
    }
}

@Composable
private fun Footer(model: JobCreateModel, form: JobForm, status: JobCreateStatus, onDismiss: () -> Unit) {
    val approving = model.canApprove && form.approveNow
    HorizontalDivider()
    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (model.canApprove) {
            Row(
                Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("job-approve-now")
                    .toggleable(form.approveNow, enabled = !status.busy, role = Role.Switch) { on -> model.update { it.copy(approveNow = on) } },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(JobCreateText.APPROVE_NOW, Modifier.weight(1f))
                Switch(form.approveNow, onCheckedChange = null, enabled = !status.busy)
            }
        }
        if (!approving) Text(JobCreateText.SEND_FOR_APPROVAL, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
        status.error?.let { ErrorText(it) }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onDismiss, enabled = !status.busy, modifier = Modifier.testTag("job-cancel")) { Text(JobCreateText.CANCEL) }
            Spacer(Modifier.weight(1f))
            if (status.busy) CircularProgressIndicator(Modifier.padding(end = 12.dp).size(24.dp))
            Button(model::submit, enabled = !status.busy, modifier = Modifier.testTag("job-create")) { Text(JobCreateText.primary(approving)) }
        }
    }
}

@Composable
private fun ErrorText(text: String) {
    Text(
        text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error,
        modifier = Modifier.testTag("job-create-error").semantics { liveRegion = LiveRegionMode.Assertive },
    )
}

/** A tappable form row: the label, the chosen value (or [placeholder]) and the validation message. */
@Composable
private fun FormRow(label: String, value: String?, placeholder: String, error: String?, enabled: Boolean, tag: String, onClick: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        OutlinedCard(Modifier.fillMaxWidth().testTag(tag).clickable(enabled = enabled, role = Role.Button, onClick = onClick)) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(label, style = MaterialTheme.typography.labelMedium, color = if (error != null) MaterialTheme.colorScheme.error else palette.secondaryText)
                Text(value ?: placeholder, style = MaterialTheme.typography.bodyLarge, color = if (value == null) palette.secondaryText else Color.Unspecified)
            }
        }
        error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(start = 12.dp)) }
    }
}

/**
 * Server-searched picker (as the web's async autocompletes): type to search (300 ms debounce, never cached), tap a
 * result to choose it; [onNone] adds a "None" row (the optional site).
 */
@Composable
private fun <T> SearchPickerField(
    label: String,
    value: T?,
    display: (T) -> String,
    error: String?,
    enabled: Boolean,
    tag: String,
    search: suspend (String) -> ActionResult<List<T>>,
    onPick: (T) -> Unit,
    onNone: (() -> Unit)? = null,
) {
    var open by remember { mutableStateOf(false) }
    FormRow(label, value?.let(display), if (onNone != null) JobCreateText.NO_SITE else JobCreateText.CHOOSE, error, enabled, tag) { open = true }
    if (!open) return
    var query by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<ActionResult<List<T>>?>(null) }
    LaunchedEffect(query) {
        if (query.isNotEmpty()) delay(SEARCH_DEBOUNCE_MS)
        result = search(query)
    }
    Dialog(onDismissRequest = { open = false }) {
        Surface(shape = MaterialTheme.shapes.large, color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(16.dp).heightIn(max = 520.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(label, style = AssetaType.headline, modifier = Modifier.semantics { heading() })
                OutlinedTextField(
                    query, { query = it.take(100) }, Modifier.fillMaxWidth().testTag("$tag-search"), singleLine = true,
                    label = { Text(JobCreateText.SEARCH) },
                )
                val row = Modifier.fillMaxWidth().heightIn(min = 48.dp)
                if (onNone != null) {
                    Text(JobCreateText.NO_SITE, row.clickable(role = Role.Button) { onNone(); open = false }.padding(vertical = 12.dp))
                }
                when (val r = result) {
                    null -> CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
                    is ActionResult.Refused -> ErrorText(r.error.message)
                    is ActionResult.Done -> if (r.value.isEmpty()) {
                        Text(JobCreateText.NO_MATCHES, color = palette.secondaryText)
                    } else {
                        LazyColumn(Modifier.weight(1f, fill = false)) {
                            items(r.value) { item ->
                                Text(display(item), row.clickable(role = Role.Button) { onPick(item); open = false }.padding(vertical = 12.dp))
                            }
                        }
                    }
                }
                TextButton({ open = false }, Modifier.align(Alignment.End)) { Text(JobCreateText.CANCEL) }
            }
        }
    }
}

private const val SEARCH_DEBOUNCE_MS = 300L

/** A date and time row: tapping opens the date, then the time dialog (device time zone). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DateTimeRow(label: String, value: Instant, error: String?, enabled: Boolean, tag: String, onPick: (Instant) -> Unit) {
    val zone = ZoneId.systemDefault()
    var step by remember { mutableIntStateOf(0) } // 0 closed, 1 date, 2 time
    var pickedDate by remember { mutableStateOf<Long?>(null) }
    FormRow(label, OwnerFormat.dateTime(value, zone), JobCreateText.CHOOSE, error, enabled, tag) { step = 1 }
    val local = value.atZone(zone)
    if (step == 1) {
        val state = rememberDatePickerState(initialSelectedDateMillis = local.toLocalDate().atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli())
        DatePickerDialog(
            onDismissRequest = { step = 0 },
            confirmButton = { TextButton({ pickedDate = state.selectedDateMillis; step = 2 }) { Text(JobCreateText.NEXT) } },
            dismissButton = { TextButton({ step = 0 }) { Text(JobCreateText.CANCEL) } },
        ) { DatePicker(state) }
    }
    if (step == 2) {
        val is24 = android.text.format.DateFormat.is24HourFormat(LocalContext.current)
        val state = rememberTimePickerState(local.hour, local.minute, is24)
        AlertDialog(
            onDismissRequest = { step = 0 },
            text = { TimePicker(state) },
            confirmButton = {
                TextButton({
                    val day = pickedDate?.let { Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate() } ?: local.toLocalDate()
                    onPick(day.atTime(state.hour, state.minute).atZone(zone).toInstant())
                    step = 0
                }) { Text(JobCreateText.OK) }
            },
            dismissButton = { TextButton({ step = 0 }) { Text(JobCreateText.CANCEL) } },
        )
    }
}
