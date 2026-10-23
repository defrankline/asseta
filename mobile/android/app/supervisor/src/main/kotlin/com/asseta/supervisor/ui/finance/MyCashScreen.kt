package com.asseta.supervisor.ui.finance

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.font.FontWeight
import com.asseta.core.domain.finance.CustodyLine
import com.asseta.core.domain.finance.PendingCashKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.sync.data.FinanceRecord
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

/** Custody of one currency: the synced balance and, apart from it, what this phone has not synced yet (Money tab). */
@Composable
fun CustodySection(line: CustodyLine) {
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
