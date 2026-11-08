package com.asseta.owner.ui.accountability

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AdjustmentRequestDto
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** Wording of the adjustment requests (docs/requirements/accountability-mobile-strings.md, DEC-032 Phase 2). */
object AdjustmentTexts {
    const val SECTION = "Adjustments"
    const val EMPTY = "No adjustments waiting."
    const val TITLE = "Adjustment request"
    const val TYPE = "Type"
    const val REFERENCE = "Reference"
    const val CUSTOMER = "Customer"
    const val MACHINE = "Machine"
    const val PURCHASE = "Purchase"
    const val HOURS = "Hours"
    const val AMOUNT = "Amount"
    const val SETTLEMENT = "Settlement"
    const val REASON_CATEGORY = "Reason category"
    const val WITHDRAWN_REASON = "Why it was withdrawn"
    const val EFFECTS_FORECAST = "If approved"
    const val EFFECTS_ACTUAL = "What it did"
    const val LOT_BEFORE_FORECAST = "Hours on the lot now"
    const val LOT_BEFORE_ACTUAL = "Hours on the lot before"
    const val LOT_AFTER = "Hours on the lot after"
    const val PURCHASE_REMAINING = "Left on the purchase"
    const val HOURS_REFUNDED = "Hours refunded"
    const val VALUE = "Value of the hours"
    const val PAYMENT_AMOUNT = "Payment amount"
    const val UNUSED_REMOVED = "Unused hours removed"
    const val USED_HOURS = "Hours already used"
    const val USED_KEPT = "Used hours kept"
    const val MONEY_OWED = "Money owed for hours already used"
    const val TREATMENT = "For hours already used"
    const val RECOVERY_INVOICE = "Recovery invoice"
    const val RELEASED = "Released from invoices"
    const val MONEY_RELEASED = "Released to credit"
    const val CUSTOMER_BALANCE = "Customer balance"
    const val CUSTODY_AFTER = "Custodian's cash after"
    const val WITHDRAW = "Withdraw"
    const val WITHDRAW_TITLE = "Withdraw this request"
    const val WITHDRAW_FOOTER = "Only the person who proposed a request can withdraw it."
    const val WITHDRAW_LABEL = "Why are you withdrawing it? (at least 3 characters)"
    const val WITHDRAW_CONFIRM = "Withdraw this request?"
    const val WITHDRAWN = "Withdrawn."
    const val REFUSED_UNKNOWN = "the record has changed. Reload to see it."
    const val WITHDRAW_MIN = 3

    fun type(wire: String): String = when (wire) {
        "HOURS_CORRECTION" -> "Hours correction"
        "HOURS_REFUND" -> "Hours refund"
        "PAYMENT_REVERSAL" -> "Payment reversal"
        "COLLECTION_REVERSAL" -> "Collection reversal"
        "PURCHASE_REVERSAL" -> "Purchase reversal"
        "INVOICE_VOID" -> "Invoice void"
        "ZERO_AMOUNT_ACTIVATION" -> "Purchase with nothing to pay"
        else -> OwnerFormat.humanize(wire)
    }

    fun settlement(wire: String): String = when (wire) {
        "CREDIT" -> "Credit to the customer"
        "PAY_OUT" -> "Paid out"
        else -> OwnerFormat.humanize(wire)
    }

    fun treatment(wire: String): String = when (wire) {
        "RECEIVABLE" -> "Bill the customer"
        "CASE" -> "Open an investigation case"
        else -> OwnerFormat.humanize(wire)
    }

    fun refused(reason: String) = "This request can't be approved as it stands: $reason"

    fun purchaseLine(unused: String, used: String, owed: String) = "$unused h removed · $used h used · $owed owed"

    private val ERRORS = mapOf(
        "SEGREGATION_OF_DUTIES" to "You proposed this request, so someone else must decide it.",
        "ALREADY_DECIDED" to "This request was already decided or withdrawn. Reload to see it.",
        "NOT_PROPOSER" to "Only the person who proposed this request can withdraw it.",
        "REVERSAL_EXISTS" to "A reversal of this record is already waiting or done.",
        "REVERSAL_TYPE_MISMATCH" to "This record can't be reversed this way.",
        "NOTHING_TO_REVERSE" to "There is nothing left to reverse on this record.",
        "PURCHASE_CANCELLED" to "This purchase is cancelled.",
        "HOURS_CORRECTION_INVALID" to "The hours of this correction are not valid.",
        "HOURS_CORRECTION_NEGATIVE" to "This correction would take the hours below zero.",
        "HOURS_CORRECTION_EXCEEDS_LOT" to "This correction would lift the purchase above its activated hours.",
        "HOURS_CORRECTION_EXCEEDS_ENTRY" to "This correction is more than the entry it corrects.",
        "CONSUMED_ENTRY_NOT_FOUND" to "The usage entry this correction names is no longer on the purchase.",
        "REFUND_NOT_ALLOWED" to "Your company has switched refunds off.",
        "HOURS_REFUND_INVALID" to "The hours of this refund are not valid.",
        "EXCEEDS_REMAINING_HOURS" to "This refund is more than the unused hours left on the machine.",
        "REFUND_EXCEEDS_PAID" to "This refund is more than the verified money on the purchase.",
        "STAFF_NOT_FOUND" to "The person named to pay out this refund is no longer on record.",
        "PAYMENT_NOT_VERIFIED" to "Only a verified payment can be reversed.",
        "PAYMENT_ALREADY_REVERSED" to "This payment is already reversed.",
        "PAYMENT_REVERSED" to "This payment has been reversed.",
        "INVOICE_NOT_ISSUED" to "Only an issued invoice can be voided.",
        "PURCHASE_NOT_ZERO_AMOUNT" to "This purchase has an amount to pay.",
        "ALREADY_ACTIVATED" to "This purchase is already activated.",
        "ZERO_AMOUNT_PENDING" to "A request for this purchase already waits for a decision.",
    )

    /** Plain words for a refusal [code]; [fallback] (the server's message) for any other code. */
    fun error(code: String?, fallback: String): String = ERRORS[code] ?: fallback
}

/** Pure mapping of adjustment requests to the decision screen's [DecisionItem] (unit-tested; same rules as iOS). */
object AdjustmentPresentation {
    private val T = AdjustmentTexts

    private fun dec(raw: String?) = raw?.toBigDecimalOrNull()

    private fun zero(raw: String?) = dec(raw)?.signum() == 0

    private fun hours(raw: String?) = "${OwnerFormat.hoursNumber(raw)} h"

    /** Hours with their direction, as a correction reads: "+2 h", "-2 h". */
    fun signedHours(raw: String?): String = (if ((dec(raw)?.signum() ?: 0) > 0) "+" else "") + hours(raw)

    private fun money(raw: String?, currency: String?): String? {
        if (raw == null) return null
        val value = dec(raw)
        return if (value != null && currency != null) OwnerFormat.money(value, currency) else listOfNotNull(raw, currency).joinToString(" ")
    }

    /** What the row's headline adds after the type: signed hours, hours, money, or nothing for an invoice void. */
    private fun quantity(r: AdjustmentRequestDto): String? = when (r.requestType) {
        AdjustmentRequestDto.HOURS_CORRECTION -> r.hours?.let(::signedHours)
        AdjustmentRequestDto.HOURS_REFUND -> r.hours?.let(::hours)
        AdjustmentRequestDto.INVOICE_VOID -> null
        AdjustmentRequestDto.ZERO_AMOUNT_ACTIVATION -> r.hours?.let(::hours)
        else -> money(r.amount, r.currency)
    }

    fun headline(r: AdjustmentRequestDto): String = listOfNotNull(T.type(r.requestType), quantity(r)).joinToString(" · ")

    private fun machine(r: AdjustmentRequestDto) = r.machineCode ?: r.machineName ?: DisplayNames.shortId(r.machineId)

    /** "{customer} · {machine}", each only when present. */
    fun subline(r: AdjustmentRequestDto): String? =
        listOfNotNull(DisplayNames.of(r.customerName, r.customerId), machine(r)).joinToString(" · ").ifEmpty { null }

    private fun requestFields(r: AdjustmentRequestDto): List<DecisionField> {
        val withdrawn = r.status == AdjustmentRequestDto.WITHDRAWN
        val rows = listOf(
            OwnerAccountabilityTexts.NUMBER to r.requestNumber,
            T.TYPE to T.type(r.requestType),
            T.REFERENCE to r.originalReference,
            T.CUSTOMER to DisplayNames.of(r.customerName, r.customerId),
            T.MACHINE to DisplayNames.machine(r.machineCode, r.machineName, r.machineId),
            T.PURCHASE to r.purchaseNumber,
            T.HOURS to r.hours?.let { if (r.requestType == AdjustmentRequestDto.HOURS_CORRECTION) signedHours(it) else hours(it) },
            T.AMOUNT to money(r.amount, r.currency),
            T.SETTLEMENT to r.settlement?.let(T::settlement),
            T.REASON_CATEGORY to r.reasonLabel,
            OwnerAccountabilityTexts.F_PROPOSED_BY to DisplayNames.of(r.proposedByName, r.proposedBy),
            OwnerAccountabilityTexts.F_DECIDED_BY to DisplayNames.of(r.decidedByName, r.decidedBy),
            (if (withdrawn) T.WITHDRAWN_REASON else OwnerAccountabilityTexts.F_DECISION_NOTE) to r.decisionNote,
        )
        return rows.mapNotNull { (label, value) -> value?.takeIf { it.isNotBlank() }?.let { DecisionField(label, it) } }
    }

    private fun JsonObject.text(key: String): String? = (this[key] as? JsonPrimitive)?.contentOrNull

    private fun purchaseRows(e: JsonObject, currency: String?): List<DecisionField> =
        (e["purchases"] as? JsonArray).orEmpty().mapNotNull { element: JsonElement ->
            val p = element as? JsonObject ?: return@mapNotNull null
            val owed = money(p.text("money_owed") ?: "0", currency).orEmpty()
            DecisionField(
                p.text("purchase_number") ?: DisplayNames.shortId(p.text("purchase_id")).orEmpty(),
                T.purchaseLine(OwnerFormat.hoursNumber(p.text("unused_hours")), OwnerFormat.hoursNumber(p.text("used_hours")), owed),
            )
        }

    /** The rows of [r]'s `effects`, in the documented order; unknown keys are ignored, zero rows left out except the lot's. */
    fun effectRows(r: AdjustmentRequestDto): List<DecisionField> {
        val e = r.effects
        val pending = r.status == AdjustmentRequestDto.PROPOSED
        fun lot(label: String, key: String) = e.text(key)?.let { DecisionField(label, hours(it)) }
        fun hoursRow(label: String, key: String) = e.text(key)?.takeUnless(::zero)?.let { DecisionField(label, hours(it)) }
        fun moneyRow(label: String, key: String) = e.text(key)?.takeUnless(::zero)?.let { DecisionField(label, money(it, r.currency).orEmpty()) }
        fun textRow(label: String, value: String?) = value?.let { DecisionField(label, it) }
        // How used hours are treated only matters when a reversal actually touches some.
        val touchesUsed = !zero(e.text("used_hours") ?: "0") || !zero(e.text("money_owed") ?: "0")
        return listOfNotNull(
            lot(if (pending) T.LOT_BEFORE_FORECAST else T.LOT_BEFORE_ACTUAL, "lot_hours_before"),
            lot(T.LOT_AFTER, "lot_hours_after"),
            hoursRow(T.PURCHASE_REMAINING, "purchase_remaining"),
            hoursRow(T.HOURS_REFUNDED, "hours_refunded"),
            moneyRow(T.VALUE, "value"),
            textRow(T.SETTLEMENT, e.text("settlement")?.let(T::settlement)),
            moneyRow(T.PAYMENT_AMOUNT, "payment_amount"),
            hoursRow(T.UNUSED_REMOVED, "unused_hours_removed"),
            hoursRow(T.USED_HOURS, "used_hours"),
            hoursRow(T.USED_KEPT, "used_hours_kept"),
            moneyRow(T.MONEY_OWED, "money_owed"),
            textRow(T.TREATMENT, e.text("treatment")?.takeIf { touchesUsed }?.let(T::treatment)),
            textRow(T.RECOVERY_INVOICE, e.text("recovery_invoice_number")),
            moneyRow(T.RELEASED, "hire_allocations_released"),
            moneyRow(T.MONEY_RELEASED, "money_released_to_credit"),
            moneyRow(T.CUSTOMER_BALANCE, "customer_balance"),
            moneyRow(T.CUSTODY_AFTER, "custody_balance_after"),
        ) + purchaseRows(e, r.currency)
    }

    /** Set while PROPOSED when the server's forecast says approving would be refused. */
    fun refusal(r: AdjustmentRequestDto): String? =
        r.effects.text("refused")?.takeIf { r.status == AdjustmentRequestDto.PROPOSED }?.let { T.refused(T.error(it, T.REFUSED_UNKNOWN)) }

    fun item(r: AdjustmentRequestDto): DecisionItem {
        val pending = r.status == AdjustmentRequestDto.PROPOSED
        return DecisionItem(
            DecisionKinds.ADJUSTMENT_REQUEST, r.id, headline(r), r.reason, r.proposedAt, r.proposedBy, r.status, pending, requestFields(r),
            proposedByName = DisplayNames.of(r.proposedByName, r.proposedBy),
            photoAttachmentIds = r.evidenceAttachmentIds,
            subline = subline(r),
            effectsTitle = if (pending) T.EFFECTS_FORECAST else T.EFFECTS_ACTUAL,
            effects = effectRows(r),
            effectsWarning = refusal(r),
        )
    }

    fun withdrawReasonValid(reason: String): Boolean = reason.trim().length >= T.WITHDRAW_MIN

    /** Offered to the proposer only, while the request still waits (the server enforces both). */
    fun canWithdraw(item: DecisionItem, userId: String?): Boolean =
        item.kind == DecisionKinds.ADJUSTMENT_REQUEST && item.pending && item.isOwn(userId)
}

/** The proposer takes back a request nobody has decided yet. */
@Composable
fun WithdrawCard(gate: MutationCheck, busy: Boolean, error: String?, onWithdraw: (String) -> Unit) {
    val T = AdjustmentTexts
    var reason by rememberSaveable { mutableStateOf("") }
    var confirm by rememberSaveable { mutableStateOf(false) }
    SectionCard(T.WITHDRAW_TITLE, footer = T.WITHDRAW_FOOTER) {
        if (gate is MutationCheck.Blocked) {
            BlockedNote(gate.reason)
        } else {
            OutlinedTextField(reason, { reason = it.take(1000) }, Modifier.fillMaxWidth().testTag("withdraw-reason"), label = { Text(T.WITHDRAW_LABEL) }, minLines = 2)
            Button(
                { confirm = true }, enabled = !busy && AdjustmentPresentation.withdrawReasonValid(reason), modifier = Modifier.testTag("withdraw"),
                colors = ButtonDefaults.buttonColors(containerColor = OwnerColors.Warning.copy(alpha = 0.15f), contentColor = OwnerColors.Warning),
                shape = RoundedCornerShape(8.dp),
            ) { Text(T.WITHDRAW) }
            error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
        }
    }
    if (confirm) {
        AlertDialog(
            onDismissRequest = { confirm = false },
            title = { Text(T.WITHDRAW_CONFIRM) },
            confirmButton = { TextButton({ confirm = false; onWithdraw(reason) }) { Text(T.WITHDRAW, color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton({ confirm = false }) { Text("Cancel") } },
        )
    }
}
