package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.CurrencyCode
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.model.sync.SyncCapabilities
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import java.math.BigDecimal

/**
 * The part of the tenant `CASH_CUSTODY` policy the field app shows or hides UI by (the server applies every rule).
 * Parsed strictly: a value that is missing or of the wrong type makes the whole policy unknown (null), and an unknown
 * policy hides the new options so today's screens behave as before.
 */
data class CashCustodyPolicy(
    val recordersMayRecordForOthers: Boolean,
    val transferAckRequired: Boolean,
    val recorderReceiverCountsAsAck: Boolean,
    val floatAckRequired: Boolean,
    val remitFullBalance: Boolean,
    val retentionAllowed: Boolean,
) {
    companion object {
        const val TYPE = "CASH_CUSTODY"

        fun fromValues(values: JsonObject): CashCustodyPolicy? = runCatching {
            CashCustodyPolicy(
                recordersMayRecordForOthers = values.flag("recorders_may_record_for_others"),
                transferAckRequired = values.flag("transfer_ack_required"),
                recorderReceiverCountsAsAck = values.flag("recorder_receiver_counts_as_ack"),
                floatAckRequired = values.flag("float_ack_required"),
                remitFullBalance = values.flag("remit_full_balance"),
                retentionAllowed = values.flag("retention_allowed"),
            )
        }.getOrNull()
    }
}

/** The part of the tenant `CUSTOMER_HOURS` policy the field app needs (same strict parsing). */
data class CustomerHoursPolicy(
    val enabled: Boolean,
    val walkInAllowed: Boolean,
    val transferRequiresApproval: Boolean,
    val reasonCodeRequired: Boolean,
) {
    companion object {
        const val TYPE = "CUSTOMER_HOURS"

        fun fromValues(values: JsonObject): CustomerHoursPolicy? = runCatching {
            CustomerHoursPolicy(
                enabled = values.flag("enabled"),
                walkInAllowed = values.flag("walk_in_allowed"),
                transferRequiresApproval = values.flag("transfer_requires_approval"),
                reasonCodeRequired = values.flag("reason_code_required"),
            )
        }.getOrNull()
    }
}

private fun JsonObject.flag(key: String): Boolean = (this[key] as JsonPrimitive).booleanOrNull!!

/**
 * What the field app offers, from the server's sync capabilities, the user's permissions and the tenant policies
 * (cached on the phone). Every entry needs all three; [capabilities] null means the phone never synced.
 */
data class FieldAccess(
    val capabilities: Set<String>?,
    val permissions: Set<String>,
    val cash: CashCustodyPolicy? = null,
    val hours: CustomerHoursPolicy? = null,
) {
    private fun supports(capability: String) = capabilities?.contains(capability) == true
    private fun can(permission: String) = permission in permissions

    val sellHours: Boolean get() = supports(SyncCapabilities.OP_HOURS_PURCHASE) && can(HOURS_PURCHASE) && hours?.enabled == true
    val walkIn: Boolean get() = sellHours && hours?.walkInAllowed == true
    val requestHoursTransfer: Boolean
        get() = supports(SyncCapabilities.OP_HOURS_TRANSFER_REQUEST) && can(HOURS_TRANSFER) && hours?.enabled == true
    val transferCash: Boolean get() = supports(SyncCapabilities.OP_CASH_TRANSFER) && can(COLLECTION_RECORD)
    val acknowledgeCash: Boolean get() = transferCash

    /** A recorder may name another cash holder (collections, remittances, sales, transfers). */
    val recordForOthers: Boolean get() = can(COLLECTION_RECORD) && cash?.recordersMayRecordForOthers == true
    val askToKeepCash: Boolean get() = can(COLLECTION_RECORD) && cash?.retentionAllowed == true
    val dailyReading: Boolean get() = supports(SyncCapabilities.METER_DAILY_READING) && can(METER_CAPTURE)
    val proposeBaseline: Boolean get() = supports(SyncCapabilities.OP_METER_BASELINE) && can(METER_CAPTURE)
    val proposeCorrection: Boolean get() = supports(SyncCapabilities.OP_METER_CORRECTION) && can(METER_CAPTURE)

    companion object {
        const val HOURS_PURCHASE = "tenant.hours.purchase"
        const val HOURS_TRANSFER = "tenant.hours.transfer"
        const val HOURS_READ = "tenant.hours.read"
        const val COLLECTION_RECORD = "tenant.collection.record"
        const val METER_CAPTURE = "tenant.meter.capture"
    }
}

enum class PaymentMethod(val wire: String) { CASH("CASH"), BANK("BANK"), MOBILE_MONEY("MOBILE_MONEY") }

/** The hours-sale form as typed (validated by [AccountabilityRules.hoursSale]). */
data class HoursSaleDraft(
    val walkIn: Boolean,
    val customerId: String?,
    val walkInName: String,
    val walkInPhone: String,
    val machineId: String?,
    val hoursText: String,
    val paidNow: Boolean,
    val method: PaymentMethod?,
    val amountText: String,
    val reference: String,
    val note: String,
)

data class HoursSaleValues(
    val hours: BigDecimal,
    val amount: BigDecimal?,
    val reference: String?,
    val walkInName: String?,
    val walkInPhone: String?,
    val note: String?,
)

data class HoursTransferValues(val hours: BigDecimal, val reason: String)

data class CashTransferValues(val amount: BigDecimal, val currency: String, val amountReceived: BigDecimal?, val note: String?)

data class AckValues(val amountReceived: BigDecimal?, val note: String?)

data class RetentionValues(val amount: BigDecimal, val currency: String, val reason: String)

/** Offline checks of the accountability forms (wording in [AccountabilityMessages]; the server re-validates). */
object AccountabilityRules {
    const val MAX_NOTE = 1000
    const val MAX_REFERENCE = 120
    const val MIN_REASON = 3
    const val MIN_CORRECTION_REASON = 10
    const val MIN_PHONE = 3
    const val MAX_NAME = 200
    const val MAX_PHONE = 40
    private val HOURS = DecimalLimit.METER_READING

    fun hoursSale(d: HoursSaleDraft, walkInAllowed: Boolean): FormCheck<HoursSaleValues> {
        val m = mutableListOf<String>()
        var name: String? = null
        var phone: String? = null
        if (d.walkIn) {
            if (!walkInAllowed) m += AccountabilityMessages.WALK_IN_OFF
            name = d.walkInName.trim().take(MAX_NAME).ifEmpty { null }
            if (name == null) m += AccountabilityMessages.WALK_IN_NAME
            phone = d.walkInPhone.trim().ifEmpty { null }
            if (phone != null && (phone.length < MIN_PHONE || phone.length > MAX_PHONE)) m += AccountabilityMessages.PHONE
        } else if (d.customerId.isNullOrBlank()) {
            m += AccountabilityMessages.CUSTOMER
        }
        if (d.machineId.isNullOrBlank()) m += AccountabilityMessages.MACHINE
        val hours = AmountParser.valueOrNull(d.hoursText, HOURS)
        if (hours == null) m += AccountabilityMessages.HOURS
        var amount: BigDecimal? = null
        var reference: String? = null
        if (d.paidNow) {
            amount = AmountParser.valueOrNull(d.amountText, DecimalLimit.MONEY)
            if (amount == null) m += AccountabilityMessages.AMOUNT_RECEIVED
            reference = d.reference.trim().take(MAX_REFERENCE).ifEmpty { null }
            if (d.method != PaymentMethod.CASH && reference == null) m += AccountabilityMessages.REFERENCE
        }
        val note = d.note.trim().take(MAX_NOTE).ifEmpty { null }
        return if (m.isEmpty()) FormCheck.Valid(HoursSaleValues(hours!!, amount, reference, name, phone, note)) else FormCheck.Invalid(m)
    }

    /** [remaining]: hours left on the purchase (null when unknown); [fromMachineId]: the machine the hours are on. */
    fun hoursTransfer(
        purchaseId: String?,
        fromMachineId: String?,
        toMachineId: String?,
        hoursText: String,
        remaining: BigDecimal?,
        reason: String,
        reasonCodeId: String?,
        reasonCodeRequired: Boolean,
    ): FormCheck<HoursTransferValues> {
        val m = mutableListOf<String>()
        if (purchaseId.isNullOrBlank()) m += AccountabilityMessages.PURCHASE
        if (toMachineId.isNullOrBlank()) m += AccountabilityMessages.TARGET_MACHINE
        else if (toMachineId == fromMachineId) m += AccountabilityMessages.SAME_MACHINE
        val hours = AmountParser.valueOrNull(hoursText, HOURS)
        if (hours == null) m += AccountabilityMessages.TRANSFER_HOURS
        else if (remaining != null && hours > remaining) m += AccountabilityMessages.tooMany(remaining)
        val text = reason.trim()
        if (text.length < MIN_REASON) m += AccountabilityMessages.REASON
        if (reasonCodeRequired && reasonCodeId.isNullOrBlank()) m += AccountabilityMessages.CATEGORY
        return if (m.isEmpty()) FormCheck.Valid(HoursTransferValues(hours!!, text.take(MAX_NOTE))) else FormCheck.Invalid(m)
    }

    /** [receiverIsMe] with [selfAck]: the recorder receives the cash and must say how much arrived. */
    fun cashTransfer(
        fromId: String?,
        toId: String?,
        amountText: String,
        currency: String,
        receiverIsMe: Boolean,
        selfAck: Boolean,
        receivedText: String,
        note: String,
    ): FormCheck<CashTransferValues> {
        val m = mutableListOf<String>()
        if (toId.isNullOrBlank()) m += AccountabilityMessages.TRANSFER_TO
        else if (toId == fromId) m += AccountabilityMessages.TRANSFER_SAME
        val amount = AmountParser.valueOrNull(amountText, DecimalLimit.MONEY)
        if (amount == null) m += AccountabilityMessages.TRANSFER_AMOUNT
        val code = CurrencyCode.normalize(currency)
        if (code == null) m += AccountabilityMessages.CURRENCY
        val received = if (receiverIsMe && selfAck) {
            AmountParser.valueOrNull(receivedText, DecimalLimit.MONEY, allowZero = true).also { if (it == null) m += AccountabilityMessages.TRANSFER_RECEIVED }
        } else {
            null
        }
        val text = note.trim().take(MAX_NOTE).ifEmpty { null }
        return if (m.isEmpty()) FormCheck.Valid(CashTransferValues(amount!!, code!!, received, text)) else FormCheck.Invalid(m)
    }

    /** Acknowledge: the amount received (0 or more). Dispute: a reason is required. */
    fun acknowledgement(acknowledge: Boolean, receivedText: String, note: String): FormCheck<AckValues> {
        val text = note.trim().take(MAX_NOTE).ifEmpty { null }
        if (!acknowledge) {
            return if (text == null) FormCheck.Invalid(listOf(AccountabilityMessages.DISPUTE_REASON)) else FormCheck.Valid(AckValues(null, text))
        }
        val received = AmountParser.valueOrNull(receivedText, DecimalLimit.MONEY, allowZero = true)
            ?: return FormCheck.Invalid(listOf(AccountabilityMessages.ACK_RECEIVED))
        return FormCheck.Valid(AckValues(received, text))
    }

    fun retention(amountText: String, currency: String, reason: String): FormCheck<RetentionValues> {
        val m = mutableListOf<String>()
        val amount = AmountParser.valueOrNull(amountText, DecimalLimit.MONEY)
        if (amount == null) m += AccountabilityMessages.RETENTION_AMOUNT
        val code = CurrencyCode.normalize(currency)
        if (code == null) m += AccountabilityMessages.CURRENCY
        val text = reason.trim()
        if (text.length < MIN_REASON) m += AccountabilityMessages.RETENTION_REASON
        return if (m.isEmpty()) FormCheck.Valid(RetentionValues(amount!!, code!!, text.take(MAX_NOTE))) else FormCheck.Invalid(m)
    }

    fun correctionReasonValid(reason: String): Boolean = reason.trim().length >= MIN_CORRECTION_REASON

    /** Plain decimal text without exponent or trailing zeros ("12.50" -> "12.5"). */
    fun plain(value: BigDecimal): String = value.stripTrailingZeros().let { if (it.scale() < 0) it.setScale(0) else it }.toPlainString()

    /** Remaining hours of a purchase on [machineId] (after transfers), else the purchase total remaining. */
    fun remainingOn(machineId: String?, perMachine: Map<String, String>, total: String): BigDecimal? =
        (machineId?.let(perMachine::get) ?: total).toBigDecimalOrNull()
}

/** Validation wording shared with iOS (docs/requirements/accountability-mobile-strings.md). */
object AccountabilityMessages {
    const val CUSTOMER = "Choose the customer."
    const val WALK_IN_NAME = "Enter the customer's name."
    const val PHONE = "The phone number must have at least 3 characters."
    const val MACHINE = "Choose the machine."
    const val HOURS = "Enter the hours (more than 0, at most 2 decimal places)."
    const val AMOUNT_RECEIVED = "Enter the amount received (more than 0)."
    const val REFERENCE = "Enter the reference for bank and mobile-money payments."
    const val WALK_IN_OFF = "Walk-in customers are turned off for your company."
    const val PURCHASE = "Choose the purchase."
    const val TARGET_MACHINE = "Choose the machine to move the hours to."
    const val SAME_MACHINE = "Choose a different machine from the one the hours are on."
    const val TRANSFER_HOURS = "Enter the hours to move (more than 0, at most 2 decimal places)."
    const val REASON = "Enter a reason (at least 3 characters)."
    const val CATEGORY = "Choose a reason category."
    const val TRANSFER_TO = "Choose who receives the cash."
    const val TRANSFER_SAME = "The sender and the receiver must be different people."
    const val TRANSFER_AMOUNT = "Enter the amount (more than 0)."
    const val TRANSFER_RECEIVED = "Enter the amount you received (0 or more)."
    const val CURRENCY = "Enter a 3-letter currency code."
    const val ACK_RECEIVED = "Enter the amount you received (0 or more)."
    const val DISPUTE_REASON = "Say why you dispute it."
    const val RETENTION_AMOUNT = "Enter the amount to keep (more than 0)."
    const val RETENTION_REASON = "Enter a reason (at least 3 characters)."
    const val CORRECTION_REASON = "Enter a reason of at least 10 characters."

    fun tooMany(remaining: BigDecimal): String = "Only ${AccountabilityRules.plain(remaining)} h are left on this purchase."
}
