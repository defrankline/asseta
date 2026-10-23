package com.asseta.supervisor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.asseta.core.sync.data.FuelItem
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.LinkRow
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette

/** Fuel tab: my fuel events by type (purchase, issue, usage), newest first; "+" opens the fuel form. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FuelScreen(snapshot: InboxSnapshot, syncing: Boolean, onRefresh: () -> Unit, onRoute: (Route) -> Unit) {
    var segment by rememberSaveable { mutableStateOf(FuelSegment.ISSUE) }
    val events = snapshot.fuel.filter { it.eventType == segment.code }
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            item(key = "segments") {
                FilterChipRow(FuelSegment.entries.map { it to it.label }, segment, { segment = it }, Modifier.padding(bottom = 8.dp))
            }
            if (snapshot.loaded && events.isEmpty()) {
                item(key = "empty") {
                    EmptyState("No fuel ${segment.label.lowercase()} events", "Fuel events you record appear here. Tap + to record one.")
                }
            }
            groupedSection(
                keyPrefix = "fuel-${segment.name}",
                items = events.map { f -> GroupedItem(f.key, onClick = { onRoute(Route.FuelDetail(f.key)) }) { FuelRow(snapshot, f) } },
            )
        }
    }
}

@Composable
private fun FuelRow(snapshot: InboxSnapshot, f: FuelItem) {
    val machine = f.machineId?.let(snapshot.machines::get)?.assetCode
    val job = f.jobId?.let(snapshot.jobs::get)?.jobNumber
    InboxRow(
        listOfNotNull(InboxTexts.litres(f.litres), machine).joinToString(" · "), f.status,
        listOfNotNull(job, f.supplier).joinToString(" · ").ifEmpty { null },
        LocalTime.format(f.atMs),
    )
}

/** One fuel event with its linked expense and sync state. */
@Composable
fun FuelDetailScreen(snapshot: InboxSnapshot, key: String, onRoute: (Route) -> Unit) {
    val f = snapshot.fuel.firstOrNull { it.key == key }
    if (f == null) {
        if (snapshot.loaded) EmptyState("Fuel event not available", "It is no longer on this phone.")
        return
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section(null) {
            LabeledRow("Status", "") { StatusPill(f.status) }
            LabeledRow("Type", InboxTexts.fuelType(f.eventType))
            LabeledRow("Litres", InboxTexts.litres(f.litres))
            f.unitPrice?.let { LabeledRow("Price per litre", InboxTexts.money(it, f.currency)) }
            f.attributedCost?.let { LabeledRow("Cost", InboxTexts.money(it, f.currency)) }
            LabeledRow("When", LocalTime.format(f.atMs))
        }
        Section("Charge to") {
            LabeledRow("Machine", f.machineId?.let(snapshot.machines::get)?.let { InboxTexts.machine(it.assetCode, it.name) } ?: "None")
            LabeledRow("Job", f.jobId?.let(snapshot.jobs::get)?.jobNumber ?: "None")
            f.meterReading?.let { LabeledRow("Meter reading", it) }
            f.supplier?.let { LabeledRow("Supplier", it) }
        }
        f.note?.let { Section("Note") { Text(it, style = AssetaType.subheadline) } }
        val expense = f.expenseId?.let { id -> snapshot.expenses.firstOrNull { it.serverId == id } }
        if (f.expenseId != null) {
            Section("Linked expense") {
                if (expense != null) {
                    LinkRow(onClick = { onRoute(Route.ExpenseDetail(expense.key)) }) {
                        InboxRow(expense.description.ifBlank { "Expense" }, expense.status, InboxTexts.money(expense.amount, expense.currency))
                    }
                } else {
                    Text("Recorded by the office.", style = AssetaType.footnote, color = palette.secondaryText)
                }
            }
        }
        f.op?.let { op ->
            Section("Sync") {
                LabeledRow("On this phone", "") { SyncStateLabel(op.status) }
                op.errorCode?.let { Text("$it: ${op.lastError.orEmpty()}", style = AssetaType.caption, color = palette.offline) }
            }
        }
        f.machineId?.let(snapshot.machines::get)?.let { m ->
            Section(null) { LinkActionRow("Machine ${m.assetCode}", com.asseta.supervisor.R.drawable.ic_gauge) { onRoute(Route.MachineDetail(m.id, m.assetCode)) } }
        }
    }
}
