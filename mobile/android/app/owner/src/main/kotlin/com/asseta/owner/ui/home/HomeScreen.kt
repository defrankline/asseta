package com.asseta.owner.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow

class HomeViewModel(data: OwnerData, refreshOn: Flow<Unit>) : SnapshotViewModel<TenantOverviewDto>({ data.overview() }, refreshOn)

/**
 * Dashboard (iOS `OverviewView`): per permitted section a bold title with the freshness of its source data, then the
 * KPIs as a grid of tiles (label above a big, tinted figure), then the section's links. Content shared with iOS.
 */
@Composable
fun HomeScreen(vm: HomeViewModel, features: OwnerFeatures, now: () -> Long, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { o ->
        val sections = OverviewPresentation.sections(o, state.stale, now())
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            sections.forEach { section ->
                item(key = section.title) {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Column(Modifier.semantics(mergeDescendants = true) { heading() }, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(section.title, style = MaterialTheme.typography.titleLarge)
                            Text(section.freshness, style = AssetaType.caption, color = palette.secondaryText)
                        }
                        section.emptyText?.let { Text(it, style = MaterialTheme.typography.bodyLarge, color = palette.secondaryText) }
                        section.groups.forEach { g ->
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                g.heading?.let { Text(it, style = AssetaType.headline) }
                                KpiGrid(g.rows) { row -> row.target?.takeIf { allowed(it, features) }?.let { t -> { onOpen(t) } } }
                            }
                        }
                        section.actions.filter { allowed(it.target, features) }.forEach { a ->
                            Text(
                                a.label, style = AssetaType.subheadline, color = palette.accent,
                                modifier = Modifier.clickable(role = Role.Button) { onOpen(a.target) }.padding(vertical = 4.dp),
                            )
                        }
                    }
                }
            }
            if (sections.isEmpty()) item { Text(OverviewPresentation.NO_SECTIONS, color = palette.secondaryText) }
            item { Text(OverviewPresentation.asOf(o), style = AssetaType.caption, color = palette.secondaryText) }
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

/** Tiles at least 150 dp wide with 12 dp gaps (iOS `GridItem(.adaptive(minimum: 150), spacing: 12)`): two per row on a phone. */
@Composable
private fun KpiGrid(rows: List<OverviewRow>, action: (OverviewRow) -> (() -> Unit)?) {
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val columns = ((maxWidth + 12.dp) / (150.dp + 12.dp)).toInt().coerceAtLeast(1)
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            rows.chunked(columns).forEach { line ->
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    line.forEach { row -> KpiTile(row, action(row), Modifier.weight(1f).fillMaxHeight()) }
                    repeat(columns - line.size) { Spacer(Modifier.weight(1f)) }
                }
            }
        }
    }
}

/** One KPI tile: caption, big figure tinted by its tone, optional detail (iOS `KPITile`). */
@Composable
private fun KpiTile(row: OverviewRow, onClick: (() -> Unit)?, modifier: Modifier) {
    val p = palette
    val color = when (row.tone) {
        KpiTone.GOOD -> p.live
        KpiTone.WARNING -> p.warning
        KpiTone.CRITICAL -> p.critical
        KpiTone.MUTED -> p.secondaryText
        KpiTone.NORMAL -> MaterialTheme.colorScheme.onSurface
    }
    val base = modifier.clip(RoundedCornerShape(12.dp)).background(p.cell)
    Column(
        (if (onClick != null) base.clickable(role = Role.Button, onClickLabel = "Open ${row.label.lowercase()}", onClick = onClick) else base)
            .padding(12.dp).semantics(mergeDescendants = true) {},
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(row.label, style = AssetaType.caption, color = p.secondaryText)
        Text(row.value, style = MaterialTheme.typography.titleLarge, color = color, maxLines = 1, softWrap = false)
        row.detail?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = p.secondaryText) }
    }
}
