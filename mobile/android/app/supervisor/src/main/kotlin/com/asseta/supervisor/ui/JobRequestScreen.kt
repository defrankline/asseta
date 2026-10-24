package com.asseta.supervisor.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.database.JobEntity
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.jobs.JobRequestRules
import com.asseta.core.domain.jobs.JobRequestState
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.FieldContractDto
import com.asseta.core.model.sync.MachineDto
import com.asseta.core.sync.usecase.JobRequestInput
import com.asseta.core.sync.usecase.JobRequestItem
import com.asseta.core.sync.usecase.JobRequestLookups
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.ui.finance.PickerOption
import com.asseta.supervisor.ui.finance.SaveSection
import com.asseta.supervisor.ui.finance.SaveState
import com.asseta.supervisor.ui.finance.SearchablePickerField
import com.asseta.supervisor.ui.finance.TextInput
import com.asseta.supervisor.ui.finance.after
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID
import java.util.concurrent.TimeUnit

/**
 * Wording and small display rules of job requests from the field, word for word the iOS `JobRequestTexts`. A request
 * shows in the Jobs list (Ready to start) until its job is on the phone, then the job itself carries the chip.
 */
object JobRequestTexts {
    const val PERMISSION = "tenant.job.request"
    const val BUTTON = "Request job"
    const val FORM_TITLE = "Request a job"
    const val CONTRACT = "Customer contract"
    const val MACHINE = "Machine"
    const val SITE = "Site (optional)"
    const val PLANNED_START = "Planned start"
    const val PLANNED_END = "Planned end (optional)"
    const val NOTE = "What the customer asked for"
    const val SUBMIT = "Send for approval"
    const val NOT_SET = "Not set"
    const val CLEAR = "Clear"
    const val FOOTER = "The owner sets the price and approves the job. You can start it once it is approved."
    const val NO_CONTRACTS = "No contracts on this phone yet. Connect to the internet once to load them."
    const val UNAVAILABLE = "Job requests not available"
    const val NO_MACHINES = "No machines on this phone yet. Connect to the internet once to load them."

    const val NOT_SENT = "Waiting for approval (not yet sent)"
    const val WAITING = "Waiting for approval"
    const val DECLINED = "Declined"

    /** Title of a request before the server numbered it, and of its outbox item. */
    const val REQUESTED_JOB = "Requested job"
    const val OPERATION = "Job request"

    fun chip(state: JobRequestState, operation: ClientOperationStatus?): String? = when (state) {
        JobRequestState.NOT_SENT -> NOT_SENT
        JobRequestState.WAITING -> WAITING
        JobRequestState.DECLINED -> DECLINED
        JobRequestState.PROBLEM -> operation?.let(FieldTexts::syncState)
        JobRequestState.DECIDED -> null
    }

    /** The request chip of a job on the phone (waiting for or declined by the owner), else null (normal status). */
    fun jobChip(job: JobEntity, requestedHere: Boolean): String? = when {
        job.status == JobRequestRules.PENDING_APPROVAL -> WAITING
        job.status == JobStatus.CANCELLED && (requestedHere || job.requestedByStaffId != null) -> DECLINED
        else -> null
    }

    /**
     * Requests to list on their own: not yet on the phone as a job; an accepted one only for
     * [JobRequestRules.SHOW_ACCEPTED_DAYS] (its job arrives with sync once the owner decides).
     */
    fun pending(requests: List<JobRequestItem>, jobIds: Set<String>, nowMs: Long): List<JobRequestItem> =
        requests.filter { r ->
            r.clientId !in jobIds && (r.operationStatus != ClientOperationStatus.ACKED ||
                nowMs - r.createdAtMs <= TimeUnit.DAYS.toMillis(JobRequestRules.SHOW_ACCEPTED_DAYS))
        }

    fun contractOption(c: FieldContractDto) =
        PickerOption(c.id, c.customerName, listOfNotNull(c.contractNumber, c.jobSiteName).joinToString(" · "), c.reference)

    fun machineOption(m: MachineDto) = PickerOption(m.id, InboxTexts.machine(m.assetCode, m.name), null, m.serialNumber)

    /** Second line of a pending request: machine and customer (from the saved lookups). */
    fun requestLine(r: JobRequestItem, lookups: JobRequestLookups): String =
        listOfNotNull(
            lookups.machines.firstOrNull { it.id == r.payload.machineId }?.let { InboxTexts.machine(it.assetCode, it.name) },
            lookups.contracts.firstOrNull { it.id == r.payload.contractId }?.customerName,
        ).joinToString("\n")
}

/** Fields of the request form; [plannedEndMs] null = not set. */
data class JobRequestForm(
    val contractId: String? = null,
    val machineId: String? = null,
    val siteId: String? = null,
    val plannedStartMs: Long = 0,
    val plannedEndMs: Long? = null,
    val note: String = "",
)

class JobRequestViewModel(private val field: FieldGraph, private val tenantId: String) : ViewModel() {
    /** Generated once per form visit; becomes the server job id (sending twice never makes two jobs). */
    private val clientId = UUID.randomUUID().toString()
    private val _form = MutableStateFlow(JobRequestForm(plannedStartMs = field.clock.nowMs()))
    val form: StateFlow<JobRequestForm> = _form.asStateFlow()
    private val _lookups = MutableStateFlow(JobRequestLookups())
    val lookups: StateFlow<JobRequestLookups> = _lookups.asStateFlow()
    private val _save = MutableStateFlow(SaveState())
    val save: StateFlow<SaveState> = _save.asStateFlow()
    private val _unavailable = MutableStateFlow<String?>(null)

    /** Why job requests cannot be recorded (never synced, or a server without job requests), or null. */
    val unavailable: StateFlow<String?> = _unavailable.asStateFlow()

    init {
        viewModelScope.launch { _unavailable.value = field.jobRequests.unavailable(tenantId) }
        viewModelScope.launch {
            _lookups.value = field.jobRequests.savedLookups(tenantId)
            _lookups.value = field.jobRequests.refreshLookups(tenantId)
        }
    }

    fun edit(change: (JobRequestForm) -> JobRequestForm) = _form.update(change)

    /** Choosing a contract preselects its site. */
    fun chooseContract(id: String?) = _form.update { f ->
        f.copy(contractId = id, siteId = _lookups.value.contracts.firstOrNull { it.id == id }?.jobSiteId ?: f.siteId)
    }

    fun submit() {
        if (_save.value.saving) return
        val f = _form.value
        _save.update { it.copy(saving = true, messages = emptyList()) }
        viewModelScope.launch {
            val result = field.jobRequests.request(
                JobRequestInput(tenantId, clientId, f.contractId, f.machineId, f.siteId, f.plannedStartMs, f.plannedEndMs, f.note),
            )
            _save.update { it.after(result) }
        }
    }
}

/** "Request a job": contract, machine, optional site, planned start/end and the customer's request; works offline. */
@Composable
fun JobRequestScreen(vm: JobRequestViewModel, onDone: () -> Unit) {
    val form by vm.form.collectAsStateWithLifecycle()
    val lookups by vm.lookups.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val unavailable by vm.unavailable.collectAsStateWithLifecycle()
    val editable = !save.saving && !save.saved && unavailable == null
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        unavailable?.let { NoticeCard(JobRequestTexts.UNAVAILABLE, it, isError = true) }
        Section(null, footer = JobRequestTexts.FOOTER) {
            SearchablePickerField(
                JobRequestTexts.CONTRACT, lookups.contracts.map(JobRequestTexts::contractOption), form.contractId, vm::chooseContract,
                emptyText = JobRequestTexts.NO_CONTRACTS, enabled = editable,
            )
            SearchablePickerField(
                JobRequestTexts.MACHINE, lookups.machines.map(JobRequestTexts::machineOption), form.machineId,
                { id -> vm.edit { it.copy(machineId = id) } }, emptyText = JobRequestTexts.NO_MACHINES, enabled = editable,
            )
            SearchablePickerField(
                JobRequestTexts.SITE, lookups.sites.map { PickerOption(it.id, it.name) }, form.siteId,
                { id -> vm.edit { it.copy(siteId = id) } }, noneLabel = JobRequestTexts.NOT_SET, enabled = editable,
            )
        }
        Section(null) {
            DateTimeField(JobRequestTexts.PLANNED_START, form.plannedStartMs, { ms ->
                vm.edit { it.copy(plannedStartMs = ms, plannedEndMs = it.plannedEndMs?.coerceAtLeast(ms)) }
            }, enabled = editable)
            OptionalDateTimeField(JobRequestTexts.PLANNED_END, form.plannedEndMs, form.plannedStartMs, { ms -> vm.edit { it.copy(plannedEndMs = ms) } }, editable)
        }
        Section(null) {
            TextInput(JobRequestTexts.NOTE, form.note, { v -> vm.edit { it.copy(note = v.take(JobRequestRules.NOTE_MAX)) } }, editable, singleLine = false)
        }
        SaveSection(save, vm::submit, onDone, enabled = editable, label = JobRequestTexts.SUBMIT)
    }
}

/** A date and time that may stay empty ("Not set"); tapping sets it from [defaultMs], "Clear" empties it again. */
@Composable
private fun OptionalDateTimeField(label: String, valueMs: Long?, defaultMs: Long, onChange: (Long?) -> Unit, enabled: Boolean) {
    if (valueMs != null) {
        DateTimeField(label, valueMs, { onChange(it) }, enabled = enabled, notBefore = defaultMs)
        if (enabled) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { onChange(null) }) { Text(JobRequestTexts.CLEAR, color = palette.offline) }
            }
        }
        return
    }
    OutlinedCard(Modifier.fillMaxWidth().clickable(enabled = enabled) { onChange(defaultMs) }) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium)
            Text(JobRequestTexts.NOT_SET, style = MaterialTheme.typography.bodyLarge, color = palette.secondaryText)
        }
    }
}
