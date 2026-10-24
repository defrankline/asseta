package com.asseta.owner.ui.jobs

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.ui.components.ButtonRow
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import kotlinx.coroutines.flow.asStateFlow
import java.time.Instant
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.time.ZoneId

class JobsViewModel private constructor(
    private val data: OwnerData,
    private val selected: MutableStateFlow<String?>,
    refreshOn: Flow<Unit>,
    private val clock: () -> Instant,
) : SnapshotViewModel<PageDto<JobDto>>({ data.jobs(selected.value) }, refreshOn) {
    constructor(data: OwnerData, refreshOn: Flow<Unit>, clock: () -> Instant = Instant::now) :
        this(data, MutableStateFlow(JobsPresentation.DEFAULT_FILTER), refreshOn, clock)

    val status: StateFlow<String?> get() = selected

    private val _creating = MutableStateFlow<JobCreateModel?>(null)

    /** The open "New job" form (one per visit, so one Idempotency-Key per visit), or null. */
    val creating: StateFlow<JobCreateModel?> = _creating.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }

    private val _openJob = MutableStateFlow<String?>(null)

    /** A job to open (created by "New job" but a later step was refused); consumed by [jobOpened]. */
    val openJob: StateFlow<String?> = _openJob.asStateFlow()

    /** Opens a new "New job" form; [canApprove]: "Approve now" is offered (and on by default). */
    fun startCreate(canApprove: Boolean) {
        _message.value = null
        _creating.value = JobCreateModel(data, viewModelScope, canApprove, clock(), onOutcome = { outcome ->
            _creating.value = null
            when (outcome) {
                is JobCreateOutcome.Done -> {
                    _message.value = outcome.message
                    filter(outcome.job.status)
                }
                is JobCreateOutcome.Partly -> {
                    // Close the form and open the job with the notice of what went wrong.
                    JobNotices.put(outcome.job.id.toString(), outcome.message)
                    filter(outcome.job.status)
                    _openJob.value = outcome.job.id.toString()
                }
            }
        })
    }

    fun closeCreate() {
        _creating.value = null
    }

    fun jobOpened() {
        _openJob.value = null
    }
}

/** Jobs list wording and rules shared with iOS (`JobsView`). */
object JobsPresentation {
    /** Status chips in display order; null = all. The list opens on jobs in progress. */
    val FILTERS: List<Pair<String?, String>> = listOf(
        "IN_PROGRESS" to "In progress", "APPROVED" to "Approved", "PENDING_APPROVAL" to "Pending approval",
        "COMPLETED" to "Completed", "CANCELLED" to "Cancelled", null to "All",
    )
    val DEFAULT_FILTER: String? = "IN_PROGRESS"

    /** The most relevant date: "Completed …", else "Started …", else "Planned …". */
    fun datesLine(job: JobDto, zone: ZoneId): String = when {
        job.completedAt != null -> "Completed ${OwnerFormat.dateTime(job.completedAt, zone)}"
        job.startedAt != null -> "Started ${OwnerFormat.dateTime(job.startedAt, zone)}"
        else -> "Planned ${OwnerFormat.dateTime(job.plannedStart, zone)}"
    }

    fun countLine(shown: Int, total: Int): String = "$shown of $total jobs"

    const val MORE_IN_CONSOLE = "Use the web console for the full list."
    const val EMPTY_TITLE = "No jobs"
    const val EMPTY_MESSAGE = "Nothing matches this filter."

    @Composable
    fun statusColor(status: String): Color = when (status) {
        "IN_PROGRESS" -> OwnerColors.Recent
        "APPROVED" -> OwnerColors.Live
        "CANCELLED" -> OwnerColors.Critical
        "PENDING_APPROVAL" -> OwnerColors.Warning
        else -> OwnerColors.Neutral
    }
}

@Composable
fun JobsScreen(vm: JobsViewModel, session: OwnerSession, online: Boolean, onJob: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    val creating by vm.creating.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val features = session.features
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(JobsPresentation.FILTERS, status, vm::filter)
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            val gate = session.can(OwnerAction.CREATE_JOB, online, state.snapshot?.source)
            // One inset-grouped list as on iOS: "New job", count line, empty state or job rows (with chevrons), console note.
            val rows = buildList {
                if (features.createJobs) {
                    add(GroupedItem("new") {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            ButtonRow(JobCreateText.NEW_JOB, Modifier.testTag("new-job"), enabled = gate is MutationCheck.Allowed) {
                                vm.startCreate(features.approveJobs)
                            }
                            if (gate is MutationCheck.Blocked) BlockedNote(gate.reason)
                        }
                    })
                }
                message?.let { m ->
                    add(GroupedItem("message") { Text(m, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) })
                }
                add(GroupedItem("count") { Text(JobsPresentation.countLine(page.items.size, page.total), style = AssetaType.caption, color = palette.secondaryText) })
                if (page.items.isEmpty()) add(GroupedItem("empty") { EmptyState(JobsPresentation.EMPTY_TITLE, JobsPresentation.EMPTY_MESSAGE, R.drawable.ic_nav_jobs) })
                page.items.forEach { job -> add(GroupedItem(job.id.toString(), onClick = { onJob(job.id.toString()) }) { JobRow(job, zone) }) }
                if (page.total > page.items.size) add(GroupedItem("more") { FootNote(JobsPresentation.MORE_IN_CONSOLE) })
            }
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) { groupedSection("jobs", rows) }
        }
    }
    creating?.let { model -> JobCreateDialog(model, showSite = features.jobSites, onDismiss = vm::closeCreate) }
    val openJob by vm.openJob.collectAsStateWithLifecycle()
    LaunchedEffect(openJob) {
        openJob?.let { id ->
            vm.jobOpened()
            onJob(id)
        }
    }
}

/** Job number with status pill, the most relevant date and the hourly rate (also used on the machine screen). */
@Composable
fun JobRow(job: JobDto, zone: ZoneId, modifier: Modifier = Modifier) {
    Column(modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(job.jobNumber, style = AssetaType.headline, modifier = Modifier.weight(1f))
            StatusPill(OwnerFormat.humanize(job.status), JobsPresentation.statusColor(job.status))
        }
        Text(JobsPresentation.datesLine(job, zone), style = AssetaType.subheadline, color = palette.secondaryText)
        Text("Rate ${OwnerFormat.money(job.hourlyRate.value, job.currency)} / h", style = AssetaType.caption, color = palette.secondaryText)
    }
}
