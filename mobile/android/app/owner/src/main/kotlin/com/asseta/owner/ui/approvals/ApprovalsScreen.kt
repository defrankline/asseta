package com.asseta.owner.ui.approvals

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.ui.components.ButtonRow
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.session.UiError
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.data.ActionResult
import com.asseta.owner.ui.accountability.DecisionItem
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionRow
import com.asseta.owner.data.ExceptionList
import com.asseta.owner.data.HandoverList
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.EvidencePhoto
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.cash.HandoverRow
import com.asseta.owner.ui.cash.HandoverText
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.exceptions.ExceptionApprovalRow
import com.asseta.owner.ui.exceptions.ExceptionReviewText
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId
import com.asseta.core.ui.R as CoreR

/** A refused decision, kept next to the request it belongs to ([code] e.g. SEGREGATION_OF_DUTIES). */
data class DecisionError(val approvalId: String, val error: UiError, val code: String?) {
    val segregationOfDuties: Boolean get() = code == "SEGREGATION_OF_DUTIES"
}

/** Approval wording and rules shared with iOS (`ApprovalsView` / `ApprovalDetailView`). */
object ApprovalText {
    val FILTERS: List<Pair<String, String>> = listOf("PENDING" to "Pending", "APPROVED" to "Approved", "REJECTED" to "Rejected")
    const val DEFAULT_FILTER = "PENDING"
    const val EMPTY_TITLE = "Nothing here"
    const val EMPTY_MESSAGE = "No requests with this status."
    const val NOT_FOUND_TITLE = "Request not found"
    const val NOT_FOUND_MESSAGE = "It may be older than the latest 200 requests."
    const val NOTE_LABEL = "Note (optional to approve, required to reject)"
    const val SOD_FOOTER = "The person who submitted a request can't decide it (segregation of duties)."
    const val SOD_TITLE = "Not allowed: segregation of duties"
    const val CONFIRM_REJECT = "Reject this request?"

    /** A rejection must say why; an approval note is optional. */
    fun canDecide(approve: Boolean, note: String): Boolean = approve || note.isNotBlank()

    @Composable
    fun statusColor(status: String) = when (status) {
        "APPROVED" -> OwnerColors.Live
        "REJECTED" -> OwnerColors.Critical
        else -> OwnerColors.Warning
    }

    fun summary(a: ApprovalRequestDto): String = "${OwnerFormat.humanize(a.subjectType)} · ${a.reason}"
}

class ApprovalsViewModel private constructor(
    data: OwnerData,
    private val selected: MutableStateFlow<String?>,
    refreshOn: Flow<Unit>,
    meterResets: Boolean,
    jobs: Boolean,
    handovers: Boolean,
    exceptions: Boolean,
    decisions: List<DecisionKind>,
) : SnapshotViewModel<PageDto<ApprovalRequestDto>>({ data.approvals(selected.value) }, refreshOn) {
    /**
     * [meterResets]: also list pending meter reset requests (`tenant.meter.read`); [jobs]: also list jobs waiting for
     * approval, e.g. requested from the field by a supervisor (`tenant.job.read`); [handovers]: cash handovers waiting
     * to be confirmed (`tenant.finance.read`); [exceptions]: open meter exceptions (`tenant.meter.read`), named by their
     * job number when [jobs] is allowed.
     */
    constructor(
        data: OwnerData,
        refreshOn: Flow<Unit>,
        meterResets: Boolean = false,
        jobs: Boolean = false,
        handovers: Boolean = false,
        exceptions: Boolean = false,
        decisions: List<DecisionKind> = emptyList(),
    ) : this(data, MutableStateFlow(ApprovalText.DEFAULT_FILTER), refreshOn, meterResets, jobs, handovers, exceptions, decisions)

    val status: StateFlow<String?> get() = selected

    /** Pending meter resets, loaded independently of the expense requests (null when the role cannot see them). */
    val resets: Section<List<MeterResetDto>>? = if (meterResets) Section(viewModelScope) { data.meterResets("PENDING") } else null

    /** Jobs waiting for approval, loaded independently (null when the role cannot read jobs). */
    val pendingJobs: Section<PageDto<JobDto>>? = if (jobs) Section(viewModelScope) { data.jobs(JobApprovalText.PENDING_STATUS) } else null

    /** Cash handovers waiting to be confirmed, loaded independently (null when the role cannot read finance). */
    val claimedHandovers: Section<HandoverList>? = if (handovers) Section(viewModelScope) { data.handovers(HandoverText.CLAIMED) } else null

    /** Open meter exceptions, loaded independently (null when the role cannot read meter evidence). */
    val openExceptions: Section<ExceptionList>? = if (exceptions) Section(viewModelScope) { data.openExceptions(jobNumbers = jobs) } else null

    /** Accountability requests waiting for a decision, one independently loaded section per kind the role may see. */
    val decisionSections: List<Pair<DecisionKind, Section<List<DecisionItem>>>> = decisions.map { k -> k to Section(viewModelScope) { data.decisions(k) } }

    private val sections get() = listOfNotNull(resets, pendingJobs, claimedHandovers, openExceptions) + decisionSections.map { it.second }

    init {
        sections.forEach { it.refresh() }
        viewModelScope.launch { refreshOn.collect { sections.forEach { it.refresh() } } }
    }

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }

    fun refreshAll() {
        refresh()
        sections.forEach { it.refresh() }
    }
}

/** One request (found in the latest 200; there is no single-request endpoint) with approve / reject. */
class ApprovalDetailViewModel(val data: OwnerData, val approvalId: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<PageDto<ApprovalRequestDto>>({ data.recentApprovals() }, refreshOn) {
    private val _error = MutableStateFlow<DecisionError?>(null)
    val error: StateFlow<DecisionError?> = _error.asStateFlow()
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    fun request(page: PageDto<ApprovalRequestDto>): ApprovalRequestDto? = page.items.firstOrNull { it.id.toString() == approvalId }

    fun decide(approve: Boolean, note: String?) {
        if (_busy.value || !ApprovalText.canDecide(approve, note.orEmpty())) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = data.decideApproval(approvalId, approve, note)) {
                is ActionResult.Done -> {
                    replaceData { page -> page.copy(items = page.items.map { if (it.id == r.value.id) r.value else it }) }
                    _message.value = if (approve) "Approved." else "Rejected."
                }
                is ActionResult.Refused -> {
                    _error.value = DecisionError(approvalId, r.error, r.code)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

@Composable
fun ApprovalsScreen(vm: ApprovalsViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    val resets = vm.resets?.state?.collectAsStateWithLifecycle()?.value
    val jobs = vm.pendingJobs?.state?.collectAsStateWithLifecycle()?.value
    val handovers = vm.claimedHandovers?.state?.collectAsStateWithLifecycle()?.value
    val exceptions = vm.openExceptions?.state?.collectAsStateWithLifecycle()?.value
    val decisions = vm.decisionSections.map { (kind, section) -> kind to section.state.collectAsStateWithLifecycle().value }
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(ApprovalText.FILTERS.map { (s, l) -> s as String? to l }, status, vm::filter)
        SnapshotScaffold(state, vm::refreshAll) { page ->
            val zone = ZoneId.systemDefault()
            val rows = buildList {
                if (page.items.isEmpty()) add(GroupedItem("empty") { EmptyState(ApprovalText.EMPTY_TITLE, ApprovalText.EMPTY_MESSAGE, R.drawable.ic_approval) })
                page.items.forEach { a ->
                    add(GroupedItem(a.id.toString(), onClick = { onOpen(OwnerDestination.Approvals(a.id.toString())) }) { ApprovalRow(a, zone) })
                }
            }
            // Meter resets below the (unchanged) expense requests, as their own section with its own state.
            val resetRows = resets?.let { r ->
                buildList {
                    val list = r.data
                    when {
                        list == null && r.loading -> Unit
                        list == null -> add(GroupedItem("error") { FootNote(r.error?.message.orEmpty()) })
                        list.isEmpty() -> add(GroupedItem("empty") { FootNote(MeterResetText.EMPTY) })
                        else -> list.forEach { m ->
                            add(GroupedItem(m.id.toString(), onClick = { onOpen(OwnerDestination.MeterReset(m.id.toString())) }) { MeterResetRow(m, zone) })
                        }
                    }
                }
            }
            // Jobs waiting for approval (office-created or requested from the field), as their own section.
            val jobRows = jobs?.let { j ->
                buildList {
                    val list = j.data?.items
                    when {
                        list == null && j.loading -> Unit
                        list == null -> add(GroupedItem("error") { FootNote(j.error?.message.orEmpty()) })
                        list.isEmpty() -> add(GroupedItem("empty") { FootNote(JobApprovalText.EMPTY) })
                        else -> list.forEach { job ->
                            add(GroupedItem(job.id.toString(), onClick = { onOpen(OwnerDestination.Job(job.id.toString())) }) { JobApprovalRow(job, zone) })
                        }
                    }
                }
            }
            // Cash handovers a supervisor claimed, waiting to be confirmed received or disputed.
            val handoverRows = handovers?.let { h ->
                sectionRows(h, HandoverText.EMPTY) { list ->
                    list.items.map { item ->
                        GroupedItem(item.id.toString(), onClick = { onOpen(OwnerDestination.Handover(item.id.toString())) }) { HandoverRow(item, list.name(item), zone) }
                    }
                }
            }
            // Open meter exceptions, each opening its review.
            val exceptionRows = exceptions?.let { x ->
                sectionRows(x, ExceptionReviewText.EMPTY) { list ->
                    list.items.map { e ->
                        GroupedItem(e.id.toString(), onClick = { onOpen(OwnerDestination.MeterException(e.id.toString())) }) {
                            ExceptionApprovalRow(e, list.jobNumber(e), zone)
                        }
                    }
                }
            }
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
                groupedSection("approvals", rows)
                jobRows?.let { groupedSection("jobs", it, header = JobApprovalText.SECTION) }
                handoverRows?.let { groupedSection("handovers", it, header = HandoverText.SECTION) }
                exceptionRows?.let { groupedSection("exceptions", it, header = ExceptionReviewText.SECTION) }
                resetRows?.let { groupedSection("resets", it, header = MeterResetText.SECTION) }
                // Accountability sections appear only when something waits (a capability the company does not use
                // never adds an empty section): today's Approvals screen is unchanged for it.
                decisions.forEach { (kind, st) ->
                    val items = st.data.orEmpty().filter { it.pending }
                    if (items.isNotEmpty()) {
                        groupedSection(
                            "decision-${kind.code}",
                            items.map { d -> GroupedItem(d.id, onClick = { onOpen(OwnerDestination.Decision(kind.code, d.id)) }) { DecisionRow(d, zone) } },
                            header = kind.header,
                        )
                    }
                }
            }
        }
    }
}

/** Rows of an independently loaded section: nothing while first loading, the error, the empty line, or the items. */
private fun <T> sectionRows(state: ScreenState<T>, empty: String, items: (T) -> List<GroupedItem>): List<GroupedItem> {
    val data = state.data
    return when {
        data == null && state.loading -> emptyList()
        data == null -> listOf(GroupedItem("error") { FootNote(state.error?.message.orEmpty()) })
        else -> items(data).ifEmpty { listOf(GroupedItem("empty") { FootNote(empty) }) }
    }
}

@Composable
private fun ApprovalRow(a: ApprovalRequestDto, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(OwnerFormat.money(a.amount.value, a.currency), style = AssetaType.headline, modifier = Modifier.weight(1f))
            StatusPill(OwnerFormat.humanize(a.status), ApprovalText.statusColor(a.status))
        }
        Text(ApprovalText.summary(a), style = AssetaType.subheadline, color = palette.secondaryText)
        Text("Requested ${OwnerFormat.dateTime(a.requestedAt, zone)}", style = AssetaType.caption, color = palette.secondaryText)
    }
}

@Composable
fun ApprovalDetailScreen(vm: ApprovalDetailViewModel, session: OwnerSession, online: Boolean) {
    val state by vm.state.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var note by rememberSaveable { mutableStateOf("") }
    var confirmReject by rememberSaveable { mutableStateOf(false) }
    SnapshotScaffold(state, vm::refresh) { page ->
        val a = vm.request(page)
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            if (a == null) {
                item { EmptyState(ApprovalText.NOT_FOUND_TITLE, ApprovalText.NOT_FOUND_MESSAGE, CoreR.drawable.ic_help) }
                return@LazyColumn
            }
            item {
                SectionCard("Request") {
                    KeyValue("Amount", OwnerFormat.money(a.amount.value, a.currency))
                    KeyValue("Type", OwnerFormat.humanize(a.subjectType))
                    KeyValue("Reason", a.reason)
                    KeyValue("Requested", OwnerFormat.dateTime(a.requestedAt, zone))
                    KeyValue("Status", OwnerFormat.humanize(a.status))
                    a.decidedAt?.let { KeyValue("Decided", OwnerFormat.dateTime(it, zone)) }
                    a.decisionNote?.let { KeyValue("Decision note", it) }
                    KeyValue("Policy", a.policyVersion)
                }
            }
            if (a.subjectType == "EXPENSE") item { ExpenseCard(vm.data, a.subjectId.toString(), online && !state.stale, zone) }
            if (a.status == "PENDING") item {
                SectionCard("Decision", footer = ApprovalText.SOD_FOOTER) {
                    val gate = session.can(OwnerAction.DECIDE_APPROVAL, online, state.snapshot?.source)
                    if (gate is MutationCheck.Blocked) {
                        BlockedNote(gate.reason)
                    } else {
                        OutlinedTextField(note, { note = it.take(1000) }, Modifier.fillMaxWidth(), label = { Text(ApprovalText.NOTE_LABEL) }, minLines = 2)
                        // Same as iOS: a green prominent "Approve" and a bordered red "Reject" on one row.
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Button(
                                { vm.decide(true, note) }, enabled = !busy, modifier = Modifier.testTag("approve-${a.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Live, contentColor = Color.White),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text("Approve") }
                            Spacer(Modifier.weight(1f))
                            Button(
                                { confirmReject = true }, enabled = !busy && ApprovalText.canDecide(false, note), modifier = Modifier.testTag("reject-${a.id}"),
                                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Critical.copy(alpha = 0.15f), contentColor = OwnerColors.Critical),
                                shape = RoundedCornerShape(8.dp),
                            ) { Text("Reject") }
                        }
                        error?.let { SegregationNotice(it) }
                    }
                }
            }
            message?.let { item { GroupedSection { Text(it, color = palette.accent, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) } } }
        }
    }
    if (confirmReject) {
        AlertDialog(
            onDismissRequest = { confirmReject = false },
            title = { Text(ApprovalText.CONFIRM_REJECT) },
            confirmButton = { TextButton({ confirmReject = false; vm.decide(false, note) }) { Text("Reject", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton({ confirmReject = false }) { Text("Cancel") } },
        )
    }
    LaunchedEffect(message) { if (message != null) note = "" }
}

/** Expense behind an approval: fetched on demand (online only, never cached), with receipt photos. */
@Composable
private fun ExpenseCard(data: OwnerData, expenseId: String, online: Boolean, zone: ZoneId) {
    val scope = rememberCoroutineScope()
    var expense by remember { mutableStateOf<ExpenseDto?>(null) }
    var detailError by remember { mutableStateOf<String?>(null) }
    SectionCard("Expense") {
        val e = expense
        if (e == null) {
            ButtonRow(if (online) "Expense details" else "Expense details (online only)", enabled = online) {
                scope.launch {
                    when (val r = data.expense(expenseId)) {
                        is ActionResult.Done -> expense = r.value
                        is ActionResult.Refused -> detailError = r.error.message
                    }
                }
            }
        } else {
            KeyValue("Description", e.description)
            e.supplier?.let { KeyValue("Supplier", it) }
            KeyValue("Paid from", OwnerFormat.humanize(e.paidFrom))
            KeyValue("Incurred", OwnerFormat.dateTime(e.incurredAt, zone))
            e.receiptAttachmentIds.forEach { rid -> EvidencePhoto("receipt", online) { data.receiptUrl(e.id.toString(), rid.toString()) } }
        }
        detailError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
    }
}

/** Segregation-of-duties and other refusals, shown on the request itself (not as a transient toast). */
@Composable
fun SegregationNotice(error: DecisionError) {
    // Red text in the decision section, as on iOS.
    val red = MaterialTheme.colorScheme.error
    Column(Modifier.fillMaxWidth().testTag("decision-error").semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Assertive }) {
        if (error.segregationOfDuties) Text(ApprovalText.SOD_TITLE, style = MaterialTheme.typography.titleSmall, color = red)
        Text(error.error.message, style = MaterialTheme.typography.bodySmall, color = red)
        error.error.reference?.let { Text("Reference: $it", style = MaterialTheme.typography.bodySmall, color = red) }
    }
}
