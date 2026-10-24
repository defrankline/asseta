package com.asseta.owner.ui.exceptions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import com.asseta.owner.ui.home.KpiTone
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.time.ZoneId

/** Meter exception wording shared with iOS (`ExceptionsView`). Read-only: reviews happen in the web console. */
object ExceptionText {
    /** Status chips; null = all. The list opens on open exceptions. */
    val FILTERS: List<Pair<String?, String>> = listOf("OPEN" to "Open", null to "All")
    const val DEFAULT_FILTER = "OPEN"
    const val BLOCKING = "Blocking"
    const val FOOTER = "Exceptions are reviewed in the web console."

    fun title(e: ExceptionDto): String = OwnerFormat.humanize(e.exceptionType)

    /** "Warning · 22 Oct 2026, 08:00". */
    fun detail(e: ExceptionDto, zone: ZoneId): String = "${OwnerFormat.humanize(e.severity)} · ${OwnerFormat.dateTime(e.createdAt, zone)}"

    /** Tone of the status pill; null for OPEN (no pill). */
    fun statusTone(status: String): KpiTone? = when (status) {
        "OPEN" -> null
        "EXPLAINED" -> KpiTone.GOOD
        "CONFIRMED" -> KpiTone.CRITICAL
        else -> KpiTone.MUTED
    }

    fun empty(status: String?): String = if (status == "OPEN") "No open exceptions." else "No exceptions."
}

class ExceptionsViewModel private constructor(
    data: OwnerData,
    jobId: String?,
    private val selected: MutableStateFlow<String?>,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<PageDto<ExceptionDto>>({ data.exceptions(selected.value, jobId) }, refreshOn) {
    constructor(data: OwnerData, jobId: String?, refreshOn: Flow<Unit>) : this(data, jobId, MutableStateFlow(ExceptionText.DEFAULT_FILTER), refreshOn)

    val status: StateFlow<String?> get() = selected

    fun filter(status: String?) {
        selected.value = status
        refresh()
    }
}

/** Meter exceptions (all, or one job's); a row linked to a job opens it. */
@Composable
fun ExceptionsScreen(vm: ExceptionsViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(ExceptionText.FILTERS, status, vm::filter)
        SnapshotScaffold(state, vm::refresh) { page ->
            val zone = ZoneId.systemDefault()
            val rows = buildList {
                if (page.items.isEmpty()) add(GroupedItem("empty") { EmptyState(ExceptionText.empty(status), icon = R.drawable.ic_warning) })
                page.items.forEach { e ->
                    val open = e.jobId?.takeIf { features.jobs }?.let { id -> { onOpen(OwnerDestination.Job(id.toString())) } }
                    add(GroupedItem(e.id.toString(), onClick = open) { ExceptionRow(e, zone) })
                }
            }
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
                groupedSection("exceptions", rows, footer = ExceptionText.FOOTER)
            }
        }
    }
}

@Composable
private fun ExceptionRow(e: ExceptionDto, zone: ZoneId) {
    Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(ExceptionText.title(e), style = AssetaType.headline, modifier = Modifier.weight(1f))
            if (e.blocking) StatusPill(ExceptionText.BLOCKING, OwnerColors.Critical)
            ExceptionText.statusTone(e.status)?.let { StatusPill(OwnerFormat.humanize(e.status), OwnerColors.tone(it)) }
        }
        Text(ExceptionText.detail(e, zone), style = AssetaType.subheadline, color = palette.secondaryText)
        e.reviewNote?.takeIf { it.isNotBlank() }?.let { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
    }
}
