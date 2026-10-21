package com.asseta.supervisor.ui.finance

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.finance.CustodyLine
import com.asseta.core.domain.finance.formatMoney
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.sync.data.CashView
import com.asseta.core.sync.data.FinanceRecord
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.ui.LocalTime

/** Entry points to the field-finance forms (shown on the jobs screen and on My cash). */
@Composable
fun FinanceActions(onExpense: () -> Unit, onCollection: () -> Unit, onHandover: () -> Unit, onFuel: () -> Unit, onMyCash: (() -> Unit)?) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = onExpense) { Text("Record expense") }
        OutlinedButton(onClick = onCollection) { Text("Cash collection") }
        OutlinedButton(onClick = onHandover) { Text("Hand over cash") }
        OutlinedButton(onClick = onFuel) { Text("Fuel event") }
        onMyCash?.let { OutlinedButton(onClick = it) { Text("My cash") } }
    }
}

/**
 * Synced (server-verified) custody per currency, clearly separated from this device's unsynced collections, handovers
 * and cash expenses, which are marked as not yet verified. Refused records are listed but never counted.
 */
@Composable
fun MyCashScreen(field: FieldGraph, tenantId: String, onExpense: () -> Unit, onCollection: () -> Unit, onHandover: () -> Unit, onFuel: () -> Unit) {
    val view by remember(tenantId) { field.financeRepository.observeCashView(tenantId) }.collectAsStateWithLifecycle(CashView(emptyList(), emptyList(), null))
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Text("My cash", style = MaterialTheme.typography.headlineSmall)
            Text(view.asOfMs?.let { "Server balance as of ${LocalTime.format(it)} (last sync)." } ?: "No server balance synced yet.",
                style = MaterialTheme.typography.bodySmall)
        }
        item { FinanceActions(onExpense, onCollection, onHandover, onFuel, null) }
        if (view.lines.isEmpty()) item { Text("No cash custody on this device yet. It downloads when you sync.") }
        items(view.lines, key = { it.currency }) { CustodyCard(it) }
        if (view.records.isNotEmpty()) item { Text("Recorded on this device", style = MaterialTheme.typography.titleMedium) }
        items(view.records, key = { it.operationId }) { RecordRow(it) }
    }
}

@Composable
private fun CustodyCard(line: CustodyLine) {
    val c = line.currency
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(c, style = MaterialTheme.typography.titleMedium)
            val synced = line.synced
            if (synced == null) {
                Text("No verified balance from the server for $c yet.", style = MaterialTheme.typography.bodySmall)
            } else {
                Text("Verified by the server", style = MaterialTheme.typography.titleSmall)
                Text("Custody outstanding: ${formatMoney(synced.outstanding, c)}")
                Text("Handovers awaiting office verification: ${formatMoney(synced.claimedUnverifiedHandovers, c)}", style = MaterialTheme.typography.bodySmall)
                Text("Expenses awaiting approval: ${formatMoney(synced.pendingSpending, c)}", style = MaterialTheme.typography.bodySmall)
            }
            if (line.hasPending) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                    Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text("Not yet synced — NOT verified", style = MaterialTheme.typography.titleSmall)
                        Text("+ ${formatMoney(line.pendingCollections, c)} collections")
                        Text("− ${formatMoney(line.pendingHandovers, c)} handovers")
                        Text("− ${formatMoney(line.pendingCashExpenses, c)} expenses paid from your cash")
                    }
                }
            }
            Text("Estimated cash in hand (not verified): ${formatMoney(line.estimatedInHand, c)}", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun RecordRow(record: FinanceRecord) {
    val status = when {
        record.status == ClientOperationStatus.ACKED -> "synced"
        record.status == ClientOperationStatus.QUARANTINED -> "held (subscription read-only): not verified"
        record.isPending -> "not synced yet: not verified"
        record.status == ClientOperationStatus.CONFLICT -> "conflict: not counted"
        else -> "rejected by server: not counted"
    }
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(record.title, style = MaterialTheme.typography.bodyLarge)
        Text(
            listOfNotNull(
                record.amount?.let { a -> record.currency?.let { formatMoney(a, it) } }, status, LocalTime.format(record.createdAtMs),
                record.errorCode?.let { "code $it" },
            ).joinToString(" · "),
            style = MaterialTheme.typography.bodySmall,
            color = if (record.isRefused) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
        )
    }
}
