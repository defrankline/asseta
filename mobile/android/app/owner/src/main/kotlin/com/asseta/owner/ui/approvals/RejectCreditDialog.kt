package com.asseta.owner.ui.approvals

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.asseta.owner.data.CreditSale
import com.asseta.owner.ui.common.Figures

/**
 * Reject credit (owner decision; same as iOS `RejectCreditSheet`): the reason is required (at least 3 characters) and
 * the seller is told it. The credit invoice is cancelled and the credit hours never become usable; paid parts stay.
 */
@Composable
fun RejectCreditDialog(sale: CreditSale, onDismiss: () -> Unit, onReject: (String) -> Unit) {
    val p = sale.purchase
    var reason by rememberSaveable(p.id) { mutableStateOf("") }
    val valid = ApprovalsTexts.rejectReasonValid(reason)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(ApprovalsTexts.REJECT_CREDIT_TITLE) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    ApprovalsTexts.rejectCreditMessage(
                        p.customerName ?: p.purchaseNumber,
                        Figures.money(Figures.dec(p.creditAmount), p.currency ?: "").trim(),
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedTextField(
                    reason, { reason = it.take(1000) }, Modifier.fillMaxWidth().testTag("credit-reject-reason"),
                    label = { Text(ApprovalsTexts.REJECT_REASON_LABEL) }, minLines = 2,
                    supportingText = { Text(ApprovalsTexts.REJECT_REASON_HINT) },
                )
            }
        },
        confirmButton = {
            TextButton({ onDismiss(); onReject(reason.trim()) }, enabled = valid, modifier = Modifier.testTag("credit-reject-confirm")) {
                Text(ApprovalsTexts.REJECT_CONFIRM, color = if (valid) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        dismissButton = { TextButton(onDismiss) { Text(ApprovalsTexts.CANCEL) } },
    )
}
