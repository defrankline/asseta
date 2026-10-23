package com.asseta.owner.ui.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow

class HomeViewModel(data: OwnerData, refreshOn: Flow<Unit>) : SnapshotViewModel<TenantOverviewDto>({ data.overview() }, refreshOn)

/** Dashboard: overview KPIs per permitted section, each with the freshness of its source data (content shared with iOS). */
@Composable
fun HomeScreen(vm: HomeViewModel, features: OwnerFeatures, now: () -> Long, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { o ->
        val sections = OverviewPresentation.sections(o, state.stale, now())
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            sections.forEach { section ->
                item {
                    SectionCard(section.title, section.freshness) {
                        section.emptyText?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        section.groups.forEach { g ->
                            g.heading?.let { Text(it, style = MaterialTheme.typography.titleSmall) }
                            g.rows.forEach { row -> Kpi(row, row.target?.takeIf { allowed(it, features) }?.let { t -> { onOpen(t) } }) }
                        }
                        section.actions.filter { allowed(it.target, features) }.forEach { a -> TextButton(onClick = { onOpen(a.target) }) { Text(a.label) } }
                    }
                }
            }
            if (sections.isEmpty()) item { Text(OverviewPresentation.NO_SECTIONS) }
            item { Text(OverviewPresentation.asOf(o), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

/** A link is offered only when the role can open its screen. */
private fun allowed(target: OwnerDestination, f: OwnerFeatures): Boolean = when (target) {
    OwnerDestination.Fleet, is OwnerDestination.Alerts -> f.fleet
    OwnerDestination.Jobs -> f.jobs
    is OwnerDestination.Approvals -> f.approvals
    OwnerDestination.Cases -> f.cases
    else -> true
}

@Composable
private fun Kpi(row: OverviewRow, onClick: (() -> Unit)?) {
    val color = when (row.tone) {
        KpiTone.GOOD -> OwnerColors.Live
        KpiTone.WARNING -> OwnerColors.Warning
        KpiTone.CRITICAL -> OwnerColors.Critical
        KpiTone.MUTED -> MaterialTheme.colorScheme.onSurfaceVariant
        KpiTone.NORMAL -> Color.Unspecified
    }
    val base = Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}
    Column(if (onClick != null) base.clickable(role = Role.Button, onClick = onClick) else base) {
        Row(Modifier.fillMaxWidth()) {
            Text(
                row.label, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f),
                color = if (onClick != null) MaterialTheme.colorScheme.primary else Color.Unspecified,
            )
            Text(row.value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, color = color, textAlign = TextAlign.End)
        }
        row.detail?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}
