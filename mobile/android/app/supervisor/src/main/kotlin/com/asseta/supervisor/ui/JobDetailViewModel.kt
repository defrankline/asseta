package com.asseta.supervisor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.JobEntity
import com.asseta.core.database.MachineEntity
import com.asseta.core.database.WorkLogEntryEntity
import com.asseta.core.domain.capture.JobStateRules
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.sync.data.JobFieldState
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.sync.usecase.JobWorkflow
import com.asseta.core.sync.usecase.WorkflowResult
import com.asseta.supervisor.FieldGraph
import com.asseta.core.model.owner.NonRevenueActivityDto
import com.asseta.supervisor.ui.accountability.NonRevenueText
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** The next allowed actions of one job, from its status on this device (mirrors the server's job rules). */
data class JobActions(val state: JobFieldState?) {
    private val status get() = state?.effectiveStatus

    val canOpening get() = status?.let { JobStateRules.readingAllowed(ReadingKind.OPENING, it) } == true && state?.hasOpening == false
    val canStart get() = status == JobStatus.APPROVED && state?.hasOpening == true && state.startQueued.not()
    val canClosing get() = status?.let { JobStateRules.readingAllowed(ReadingKind.CLOSING, it) } == true && state?.hasClosing == false
    val canAcknowledge get() = status == JobStatus.IN_PROGRESS && state?.hasClosing == true && state.hasAcknowledgement.not()

    /** The server requires the closing reading and the customer acknowledgement (ACK_REQUIRED). */
    val canComplete get() = status == JobStatus.IN_PROGRESS && state?.hasClosing == true && state.hasAcknowledgement && !state.completeQueued
    val canLogWork get() = status?.let(JobStateRules::canLogWork) == true
    val isClosed get() = status == JobStatus.COMPLETED || status == JobStatus.CANCELLED
    val showsCapture get() = canOpening || canClosing
}

data class JobDetailUi(
    val loaded: Boolean = false,
    val job: JobEntity? = null,
    val summary: JobSummary? = null,
    val state: JobFieldState? = null,
    val operations: List<ClientOperationEntity> = emptyList(),
    val workLog: List<WorkLogEntryEntity> = emptyList(),
    /** Why new readings are blocked (rules expired, offline too long), or null. */
    val captureBlocked: String? = null,
) {
    val machine: MachineEntity? get() = summary?.machine
    val actions get() = JobActions(state)
    val runningEntry get() = workLog.firstOrNull { it.operationId == null }
}

/** Job screen state: derived from the repository (domain rules), actions delegated to the JobWorkflow use case. */
class JobDetailViewModel(private val field: FieldGraph, private val tenantId: String, private val jobId: String) : ViewModel() {
    private val _error = MutableStateFlow<String?>(null)

    /** A refused action ("Not saved" alert). */
    val error: StateFlow<String?> = _error.asStateFlow()

    val ui: StateFlow<JobDetailUi> = combine(
        field.repository.observeJob(jobId),
        field.repository.observeJobs(tenantId),
        field.repository.observeJobOperations(tenantId, jobId),
        field.repository.observeWorkLog(jobId),
    ) { job, jobs, ops, log ->
        val blocked = job?.let { (field.repository.capturePolicy(tenantId, it.machineId) as? CapturePolicyDecision.Blocked)?.message }
        JobDetailUi(true, job, jobs.firstOrNull { it.job.id == jobId }, job?.let { field.repository.fieldState(it, ops) }, ops, log, blocked)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), JobDetailUi())

    private val _nonRevenue = MutableStateFlow<Map<String, NonRevenueActivityDto>>(emptyMap())

    /** The job's non-revenue entries by server activity id (DEC-031 R1, read online; empty offline or when hidden). */
    val nonRevenue: StateFlow<Map<String, NonRevenueActivityDto>> = _nonRevenue.asStateFlow()

    private val _refreshing = MutableStateFlow(false)

    /** A pull to refresh of the statuses is running. */
    val refreshing: StateFlow<Boolean> = _refreshing.asStateFlow()

    /** Re-reads the statuses online; a failed read keeps the last ones shown. */
    fun loadNonRevenue() {
        if (_refreshing.value) return
        _refreshing.value = true
        viewModelScope.launch {
            try {
                field.accountability.nonRevenueActivities(tenantId, jobId)?.let { _nonRevenue.value = NonRevenueText.byActivity(it) }
            } finally {
                _refreshing.value = false
            }
        }
    }

    fun start() = run { field.workflow.transition(tenantId, jobId, JobWorkflow.START) }
    fun complete() = run { field.workflow.transition(tenantId, jobId, JobWorkflow.COMPLETE) }
    fun startEntry(type: String) = run { field.workflow.startEntry(tenantId, jobId, type) }
    fun stopEntry(clientId: String) = run { field.workflow.stopEntry(tenantId, clientId) }
    fun clearError() { _error.value = null }

    private fun run(action: suspend () -> WorkflowResult) {
        viewModelScope.launch {
            (action() as? WorkflowResult.Refused)?.let { _error.value = it.message }
        }
    }
}
