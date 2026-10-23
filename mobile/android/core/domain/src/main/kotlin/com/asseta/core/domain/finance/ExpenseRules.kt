package com.asseta.core.domain.finance

import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.policy.BlockReason
import com.asseta.core.domain.policy.PolicySnapshot
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull
import java.math.BigDecimal
import java.time.Instant

enum class PaidFrom(val label: String) {
    CASH_CUSTODY("My cash (custody)"),
    COMPANY("Company (office, card or account)"),
}

/**
 * The server `ExpenseCapturePolicy` as enforced offline (server re-validates every expense). Thresholds are in the
 * tenant's base currency; an expense in another currency always needs a receipt and a human approval.
 */
data class ExpenseCapturePolicy(
    val receiptRequiredAbove: BigDecimal,
    val gpsRequired: Boolean,
    val gpsMaxAccuracyM: Double,
    val autoApproveLimit: BigDecimal,
) {
    companion object {
        /** Strict: a snapshot missing a value is unusable (fail closed), never defaulted locally. */
        fun fromValues(values: JsonObject): ExpenseCapturePolicy? = runCatching {
            ExpenseCapturePolicy(
                receiptRequiredAbove = values.decimal("receipt_required_above"),
                gpsRequired = (values["gps_required"] as JsonPrimitive).booleanOrNull!!,
                gpsMaxAccuracyM = (values["gps_max_accuracy_m"] as JsonPrimitive).doubleOrNull!!.also { require(it > 0) },
                autoApproveLimit = values.decimal("auto_approve_limit"),
            )
        }.getOrNull()

        /** Decimals arrive as JSON strings ("250.00"); a JSON number is read from its literal text, never via Double. */
        private fun JsonObject.decimal(key: String): BigDecimal =
            BigDecimal((this[key] as JsonPrimitive).content).also { require(it.signum() >= 0) }
    }
}

sealed interface ExpensePolicyDecision {
    data class Allowed(val snapshot: PolicySnapshot, val policy: ExpenseCapturePolicy) : ExpensePolicyDecision

    data class Blocked(val reason: BlockReason) : ExpensePolicyDecision {
        val message: String
            get() = "Connect to refresh rules. " + when (reason) {
                BlockReason.NO_SNAPSHOT -> "Your company's expense rules have not been downloaded yet."
                BlockReason.SNAPSHOT_EXPIRED -> "The downloaded expense rules have expired."
                BlockReason.OFFLINE_GRANT_EXPIRED -> "This device has been offline longer than allowed."
                BlockReason.POLICY_UNREADABLE -> "The downloaded expense rules could not be read."
            }
    }
}

/** Tenant-scoped `EXPENSE_CAPTURE` snapshot; bounded by its expiry and the device offline grant, like capture rules. */
object ExpensePolicySelector {
    const val EXPENSE_CAPTURE = "EXPENSE_CAPTURE"

    fun select(snapshots: List<PolicySnapshot>, now: Instant, offlineGrantUntil: Instant?): ExpensePolicyDecision {
        val snapshot = snapshots.firstOrNull { it.policyType == EXPENSE_CAPTURE && it.scopeKey == PolicySnapshot.TENANT_SCOPE }
            ?: return ExpensePolicyDecision.Blocked(BlockReason.NO_SNAPSHOT)
        if (offlineGrantUntil == null || now.isAfter(offlineGrantUntil)) {
            return ExpensePolicyDecision.Blocked(BlockReason.OFFLINE_GRANT_EXPIRED)
        }
        if (now.isAfter(snapshot.validUntil)) return ExpensePolicyDecision.Blocked(BlockReason.SNAPSHOT_EXPIRED)
        val policy = ExpenseCapturePolicy.fromValues(snapshot.values)
            ?: return ExpensePolicyDecision.Blocked(BlockReason.POLICY_UNREADABLE)
        return ExpensePolicyDecision.Allowed(snapshot, policy)
    }
}

/** Everything the supervisor entered for one expense, before it is persisted. */
data class ExpenseDraft(
    val categoryId: String?,
    val description: String,
    val supplier: String,
    val amountText: String,
    val currency: String,
    val paidFrom: PaidFrom?,
    val machineId: String?,
    val jobId: String?,
    /** Machine of the selected job (attribution must agree with it). */
    val jobMachineId: String?,
    val hasReceipt: Boolean,
    val gps: GpsOutcome?,
)

enum class ExpenseViolation {
    CATEGORY_REQUIRED, DESCRIPTION_REQUIRED, TEXT_TOO_LONG, AMOUNT_INVALID, CURRENCY_INVALID, PAID_FROM_REQUIRED,
    ATTRIBUTION_MISMATCH, RECEIPT_REQUIRED, GPS_NOT_ATTEMPTED, GPS_REQUIRED, GPS_TOO_INACCURATE,
}

data class ExpenseIssue(val code: ExpenseViolation, val message: String)

/** Whether the server will auto-approve the expense under the snapshot, and why not. */
sealed interface ApprovalOutlook {
    data object AutoApproved : ApprovalOutlook
    data class NeedsApproval(val reason: String) : ApprovalOutlook
}

data class ExpenseAssessment(
    val amount: BigDecimal?,
    val currency: String?,
    val receiptRequired: Boolean,
    /** Why a receipt is required (shown before the user saves). */
    val receiptReason: String?,
    val approval: ApprovalOutlook?,
    val issues: List<ExpenseIssue>,
) {
    val isValid: Boolean get() = issues.isEmpty()
}

/**
 * Offline expense rules mirroring the server (`ExpenseService.submit`): receipt required above the threshold (or in a
 * foreign currency), GPS fix within the accuracy limit when required, attribution consistency, and the auto-approval
 * outlook. [baseCurrency] is the tenant currency as far as the device knows it; when unknown, the expense is treated
 * as foreign (stricter: receipt + approval), never as base.
 */
object ExpenseRules {
    const val MAX_DESCRIPTION = 2000
    const val MAX_SUPPLIER = 200

    /** Receipt photos per expense (the server accepts at most ten `receipt_upload_ids`). */
    const val MAX_RECEIPTS = 10

    fun assess(draft: ExpenseDraft, policy: ExpenseCapturePolicy, baseCurrency: String?): ExpenseAssessment {
        val issues = mutableListOf<ExpenseIssue>()
        fun add(code: ExpenseViolation, message: String) { issues += ExpenseIssue(code, message) }

        if (draft.categoryId.isNullOrBlank()) add(ExpenseViolation.CATEGORY_REQUIRED, "Choose a category.")
        if (draft.description.isBlank()) add(ExpenseViolation.DESCRIPTION_REQUIRED, "Describe what was paid for.")
        if (draft.description.trim().length > MAX_DESCRIPTION || draft.supplier.trim().length > MAX_SUPPLIER) {
            add(ExpenseViolation.TEXT_TOO_LONG, "Shorten the description (max $MAX_DESCRIPTION) or supplier (max $MAX_SUPPLIER).")
        }
        val amount = when (val parsed = AmountParser.parse(draft.amountText, DecimalLimit.MONEY)) {
            is AmountInput.Valid -> parsed.value
            is AmountInput.Invalid -> null.also { add(ExpenseViolation.AMOUNT_INVALID, parsed.error.describe("Amount", DecimalLimit.MONEY)) }
        }
        val currency = CurrencyCode.normalize(draft.currency)
        if (currency == null) add(ExpenseViolation.CURRENCY_INVALID, "Enter a 3-letter currency code (e.g. ${baseCurrency ?: "USD"}).")
        if (draft.paidFrom == null) add(ExpenseViolation.PAID_FROM_REQUIRED, "Choose who paid: your cash or the company.")
        if (draft.jobId != null && draft.machineId != null && draft.jobMachineId != null && draft.machineId != draft.jobMachineId) {
            add(ExpenseViolation.ATTRIBUTION_MISMATCH, "The machine does not match the selected job's machine.")
        }

        val inBase = currency != null && baseCurrency != null && currency == baseCurrency
        val receiptReason = when {
            currency == null || amount == null -> null
            !inBase -> "A receipt photo is required for an expense in another currency."
            policy.receiptRequiredAbove.signum() == 0 -> "A receipt photo is required for every expense."
            amount > policy.receiptRequiredAbove ->
                "A receipt photo is required above ${policy.receiptRequiredAbove.plain()} $currency."
            else -> null
        }
        if (receiptReason != null && !draft.hasReceipt) add(ExpenseViolation.RECEIPT_REQUIRED, receiptReason)

        gpsIssue(draft.gps, policy)?.let { (code, message) -> add(code, message) }

        val approval = when {
            currency == null || amount == null -> null
            !inBase -> ApprovalOutlook.NeedsApproval(
                "Expenses in another currency always need a manager's approval. It is recorded now and stays pending until approved.",
            )
            policy.autoApproveLimit.signum() == 0 -> ApprovalOutlook.NeedsApproval(
                "Every expense needs a manager's approval. It is recorded now and stays pending until approved.",
            )
            amount > policy.autoApproveLimit -> ApprovalOutlook.NeedsApproval(
                "Above the auto-approval limit of ${policy.autoApproveLimit.plain()} $currency: a manager must " +
                    "approve it. It is recorded now and stays pending until approved.",
            )
            else -> ApprovalOutlook.AutoApproved
        }
        return ExpenseAssessment(amount, currency, receiptReason != null, receiptReason, approval, issues)
    }

    private fun gpsIssue(gps: GpsOutcome?, policy: ExpenseCapturePolicy): Pair<ExpenseViolation, String>? {
        val limit = Math.round(policy.gpsMaxAccuracyM)
        return when {
            gps == null -> ExpenseViolation.GPS_NOT_ATTEMPTED to "Waiting for the location fix…"
            !policy.gpsRequired -> null
            gps !is GpsOutcome.Fix || gps.accuracyM == null -> ExpenseViolation.GPS_REQUIRED to
                "Your company requires a GPS fix for expenses (${gps.status}). Try location again outdoors."
            gps.accuracyM > policy.gpsMaxAccuracyM -> ExpenseViolation.GPS_TOO_INACCURATE to
                "The location is accurate to ±${Math.round(gps.accuracyM)} m; your company requires ±$limit m or better. Try location again."
            else -> null
        }
    }
}

/** "500.00" -> "500" (plain digits, no exponent) for amounts shown in sentences. */
internal fun BigDecimal.plain(): String = stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }.toPlainString()
