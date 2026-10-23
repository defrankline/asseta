package com.asseta.supervisor.ui.finance

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.ui.theme.palette
import com.asseta.core.domain.finance.CustodyLine
import com.asseta.core.domain.finance.PendingCashKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.sync.data.CashView
import com.asseta.core.sync.data.FinanceRecord
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.ui.EmptyState
import com.asseta.supervisor.ui.LabeledRow
import com.asseta.supervisor.ui.LocalTime
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.WarningColor
import java.math.BigDecimal

/** Wording of "My cash" shared with iOS (`MyCashView`). */
object MyCashTexts {
    fun money(value: BigDecimal, currency: String): String = "${value.plainText()} $currency"

    fun signed(value: BigDecimal, currency: String, sign: Int): String = (if (sign > 0) "+" else "−") + money(value, currency)

    fun title(kind: PendingCashKind): String = when (kind) {
        PendingCashKind.COLLECTION -> "Cash collection"
        PendingCashKind.CASH_EXPENSE -> "Expense paid from my cash"
        PendingCashKind.HANDOVER -> "Cash handover"
    }

    fun status(record: FinanceRecord): String = when (record.status) {
        ClientOperationStatus.FAILED -> "Rejected" + (record.errorCode?.let { ": $it" } ?: "")
        ClientOperationStatus.CONFLICT -> "Conflict"
        ClientOperationStatus.QUARANTINED -> "Held (read-only subscription) · unverified"
        else -> "Waiting to sync · unverified"
    }

    /** Only records that move the supervisor's cash, split into still pending and refused (never counted). */
    fun split(records: List<FinanceRecord>): Pair<List<FinanceRecord>, List<FinanceRecord>> {
        val cash = records.filter { it.cashKind != null && it.status != ClientOperationStatus.ACKED }
        return cash.filter { it.isPending } to cash.filter { it.isRefused }
    }
}

/**
 * My cash: the server's custody balance (as of the last sync) kept apart from what this phone has recorded but the
 * server has not confirmed yet, which is clearly marked unverified. Refused records are listed but never counted.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyCashScreen(field: FieldGraph, tenantId: String, syncing: Boolean, onRefresh: () -> Unit) {
    val view by remember(tenantId) { field.financeRepository.observeCashView(tenantId) }.collectAsStateWithLifecycle(CashView(emptyList(), emptyList(), null))
    val (pending, attention) = MyCashTexts.split(view.records)
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (view.lines.isEmpty()) {
                item { EmptyState("No cash balance yet", "Your cash custody appears here after a sync.") }
            }
            items(view.lines, key = { it.currency }) { CustodySection(it) }
            if (pending.isNotEmpty()) {
                item {
                    Section(
                        "Not yet confirmed (${pending.size})",
                        footer = "Recorded on this phone. Not verified: the server has not accepted these yet, so they are not in the synced balance.",
                    ) { pending.forEach { RecordRow(it) } }
                }
            }
            if (attention.isNotEmpty()) {
                item {
                    Section("Needs attention", footer = "Refused by the server or in conflict. Not counted. See Sync status for details.") {
                        attention.forEach { RecordRow(it) }
                    }
                }
            }
        }
    }
}

@Composable
private fun CustodySection(line: CustodyLine) {
    val c = line.currency
    Section(c, footer = line.synced?.asOf?.let {
        "Synced balance as of ${LocalTime.format(it.toEpochMilli())}: cash floats and collections minus approved expenses and verified handovers."
    }) {
        val synced = line.synced
        if (synced == null) {
            LabeledRow("Synced balance", "Not yet received")
        } else {
            LabeledRow("Synced balance", "") {
                Text(MyCashTexts.money(synced.outstanding, c), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
            if (synced.claimedUnverifiedHandovers.signum() != 0) {
                LabeledRow("Handed over, awaiting verification", MyCashTexts.money(synced.claimedUnverifiedHandovers, c))
            }
            if (synced.pendingSpending.signum() != 0) LabeledRow("Expenses awaiting approval", MyCashTexts.money(synced.pendingSpending, c))
        }
        if (line.pendingCollections.signum() != 0) {
            LabeledRow("Collections not yet synced", MyCashTexts.signed(line.pendingCollections, c, +1), WarningColor)
        }
        if (line.pendingHandovers.signum() != 0) {
            LabeledRow("Handovers not yet synced", MyCashTexts.signed(line.pendingHandovers, c, -1), WarningColor)
        }
        if (line.pendingCashExpenses.signum() != 0) {
            LabeledRow("Cash expenses not yet synced", MyCashTexts.signed(line.pendingCashExpenses, c, -1), WarningColor)
        }
        LabeledRow("Estimated cash in hand (unverified)", MyCashTexts.money(line.estimatedInHand, c), WarningColor)
    }
}

@Composable
private fun RecordRow(record: FinanceRecord) {
    val kind = record.cashKind ?: return
    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row {
            Text(MyCashTexts.title(kind), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            record.amount?.let { a ->
                Text(MyCashTexts.signed(a, record.currency.orEmpty(), if (kind == PendingCashKind.COLLECTION) 1 else -1),
                    style = MaterialTheme.typography.bodyMedium)
            }
        }
        Row {
            Text(LocalTime.format(record.createdAtMs), style = MaterialTheme.typography.bodySmall,
                color = palette.secondaryText, modifier = Modifier.weight(1f))
            Text(MyCashTexts.status(record), style = MaterialTheme.typography.bodySmall,
                color = if (record.isRefused) palette.offline else WarningColor)
        }
    }
}
