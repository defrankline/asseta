package com.asseta.supervisor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.JobEntity
import com.asseta.core.database.MachineEntity
import com.asseta.core.database.MeterCaptureEntity
import com.asseta.core.database.WorkLogEntryEntity
import com.asseta.core.domain.capture.JobStateRules
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.sync.data.JobFieldState
import com.asseta.core.sync.usecase.JobWorkflow
import com.asseta.core.sync.usecase.WorkflowResult
import com.asseta.supervisor.FieldGraph
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class JobDetailUi(
    val job: JobEntity? = null,
    val machine: MachineEntity? = null,
    val state: JobFieldState? = null,
    val operations: List<ClientOperationEntity> = emptyList(),
    val captures: List<MeterCaptureEntity> = emptyList(),
    val workLog: List<WorkLogEntryEntity> = emptyList(),
) {
    private val status get() = state?.effectiveStatus
    val canOpening get() = status?.let { JobStateRules.readingAllowed(ReadingKind.OPENING, it) } == true && state?.hasOpening == false
    val canStart get() = status == JobStatus.APPROVED && state?.hasOpening == true && state.startQueued.not()
    val canLogWork get() = status?.let(JobStateRules::canLogWork) == true
    val canClosing get() = status?.let { JobStateRules.readingAllowed(ReadingKind.CLOSING, it) } == true && state?.hasClosing == false
    val canAcknowledge get() = status == JobStatus.IN_PROGRESS && state?.hasClosing == true && state.hasAcknowledgement.not()
    val canComplete get() = status == JobStatus.IN_PROGRESS && state?.hasClosing == true && state.hasAcknowledgement
    val runningEntry get() = workLog.firstOrNull { it.operationId == null }
}

/** Job screen state: derived from the repository (domain rules), actions delegated to the JobWorkflow use case. */
class JobDetailViewModel(private val field: FieldGraph, private val tenantId: String, private val jobId: String) : ViewModel() {
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    val ui: StateFlow<JobDetailUi> = combine(
        field.repository.observeJob(jobId),
        field.repository.observeJobOperations(tenantId, jobId),
        field.repository.observeCaptures(jobId),
        field.repository.observeWorkLog(jobId),
    ) { job, ops, captures, log ->
        val machine = job?.let { field.repository.machine(it.machineId) }
        JobDetailUi(job, machine, job?.let { field.repository.fieldState(it, ops) }, ops, captures, log)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), JobDetailUi())

    fun start() = run { field.workflow.transition(tenantId, jobId, JobWorkflow.START) }
    fun complete() = run { field.workflow.transition(tenantId, jobId, JobWorkflow.COMPLETE) }
    fun startEntry(type: String) = run { field.workflow.startEntry(tenantId, jobId, type) }
    fun stopEntry(clientId: String) = run { field.workflow.stopEntry(tenantId, clientId) }
    fun addNote(text: String) = run { field.workflow.addNote(tenantId, jobId, text) }
    fun clearMessage() { _message.value = null }

    private fun run(action: suspend () -> WorkflowResult) {
        viewModelScope.launch {
            _message.value = when (val r = action()) {
                is WorkflowResult.Done -> "Saved on this device. It will sync when online."
                is WorkflowResult.Refused -> r.message
            }
        }
    }
}
