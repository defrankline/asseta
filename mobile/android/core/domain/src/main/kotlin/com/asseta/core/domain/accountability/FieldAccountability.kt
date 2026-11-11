package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.CurrencyCode
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.SyncCapabilities
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
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
    /** DEC-031 D2 remittance requirements (missing from older servers = not required). */
    val remittanceReferenceRequired: Boolean = false,
    val remittanceEvidenceRequired: Boolean = false,
    val remittanceAccountRequired: Boolean = false,
    /** DEC-032: every collection names its purchase or invoice (missing from older servers = not required). */
    val collectionLinkRequired: Boolean = false,
) {
    /** The remittance requirements the form enforces (the server applies them as well). */
    val remittanceRequirements: RemittanceRequirements
        get() = RemittanceRequirements(remittanceAccountRequired, remittanceReferenceRequired, remittanceEvidenceRequired)

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
                remittanceReferenceRequired = values.optionalFlag("remittance_reference_required"),
                remittanceEvidenceRequired = values.optionalFlag("remittance_evidence_required"),
                remittanceAccountRequired = values.optionalFlag("remittance_account_required"),
                collectionLinkRequired = values.optionalFlag("collection_link_required"),
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
    /** DEC-032: hours transfers need evidence (missing from older servers = not required). */
    val transferEvidenceRequired: Boolean = false,
    /** Field staff may record bank and mobile-money parts of a sale (missing from older servers = cash only). */
    val fieldNoncashPayments: Boolean = false,
    /** When the cash parts of a sale count as verified (CUSTOMER_HOURS `cash_activation`; missing = [HoursCashActivation.VERIFY]). */
    val cashActivation: HoursCashActivation = HoursCashActivation.VERIFY,
) {
    companion object {
        const val TYPE = "CUSTOMER_HOURS"

        fun fromValues(values: JsonObject): CustomerHoursPolicy? = runCatching {
            CustomerHoursPolicy(
                enabled = values.flag("enabled"),
                walkInAllowed = values.flag("walk_in_allowed"),
                transferRequiresApproval = values.flag("transfer_requires_approval"),
                reasonCodeRequired = values.flag("reason_code_required"),
                transferEvidenceRequired = values.optionalFlag("transfer_evidence_required"),
                fieldNoncashPayments = values.optionalFlag("field_noncash_payments"),
                cashActivation = HoursCashActivation.fromWire((values["cash_activation"] as? JsonPrimitive)?.contentOrNull),
            )
        }.getOrNull()
    }
}

/**
 * CUSTOMER_HOURS `cash_activation`: when the cash parts of an hours sale count as verified. Bank and mobile-money parts
 * always wait for the office to verify them.
 */
enum class HoursCashActivation(val wire: String) {
    /** The office verifies the cash payment (default; also when the key is missing or unknown). */
    VERIFY("VERIFY"),
    /** Verified automatically when the office confirms the cash handover that covers it. */
    ON_HANDOVER("ON_HANDOVER"),
    /** Verified when recorded; the supervisor holds the cash in custody until they hand it over. */
    ON_RECORDING("ON_RECORDING"),
    ;

    companion object {
        fun fromWire(value: String?): HoursCashActivation = entries.firstOrNull { it.wire == value } ?: VERIFY
    }
}

private fun JsonObject.flag(key: String): Boolean = (this[key] as JsonPrimitive).booleanOrNull!!

/** A key newer servers send: missing or not a boolean reads as off (today's behaviour). */
private fun JsonObject.optionalFlag(key: String): Boolean = (this[key] as? JsonPrimitive)?.booleanOrNull ?: false

/**
 * What the field app offers, from the server's sync capabilities, the user's permissions and the tenant policies
 * (cached on the phone). Every entry needs all three; [capabilities] null means the phone never synced.
 */
data class FieldAccess(
    val capabilities: Set<String>?,
    val permissions: Set<String>,
    val cash: CashCustodyPolicy? = null,
    val hours: CustomerHoursPolicy? = null,
    /** Tenant capabilities switched off by policy (`/me` `disabled_capabilities`, e.g. CUSTOMER_HOURS). */
    val disabled: Set<String> = emptySet(),
    /** The tenant's ENGINE_HOURS switches the field forms need; null when unknown (the server still applies them). */
    val engine: EngineHoursPolicy? = null,
) {
    private fun supports(capability: String) = capabilities?.contains(capability) == true
    private fun can(permission: String) = permission in permissions

    /** The tenant uses customer hours (not switched off in `/me`) and its CUSTOMER_HOURS policy is enabled. */
    private val customerHours: Boolean get() = TenantAccess.CUSTOMER_HOURS !in disabled && hours?.enabled == true

    val sellHours: Boolean get() = supports(SyncCapabilities.OP_HOURS_PURCHASE) && can(HOURS_PURCHASE) && customerHours
    val walkIn: Boolean get() = sellHours && hours?.walkInAllowed == true
    /** Bank and mobile-money parts may be recorded on a sale (CUSTOMER_HOURS `field_noncash_payments`); else cash only. */
    val noncashPayments: Boolean get() = sellHours && hours?.fieldNoncashPayments == true
    /** The payment methods the sale form offers. */
    /** When the cash parts of a sale count as verified (VERIFY while the policy is unknown). */
    val cashActivation: HoursCashActivation get() = hours?.cashActivation ?: HoursCashActivation.VERIFY
    val saleMethods: List<PaymentMethod> get() = if (noncashPayments) PaymentMethod.entries else listOf(PaymentMethod.CASH)
    val requestHoursTransfer: Boolean
        get() = supports(SyncCapabilities.OP_HOURS_TRANSFER_REQUEST) && can(HOURS_TRANSFER) && customerHours
    /** The tenant uses the DEC-030 cash custody additions (CASH_CUSTODY not switched off in `/me`). */
    val cashCustody: Boolean get() = TenantAccess.CASH_CUSTODY !in disabled

    /** The tenant uses engine-hour controls (ENGINE_HOURS not switched off in `/me`). */
    val engineHours: Boolean get() = TenantAccess.ENGINE_HOURS !in disabled

    val transferCash: Boolean get() = cashCustody && supports(SyncCapabilities.OP_CASH_TRANSFER) && can(COLLECTION_RECORD)
    val acknowledgeCash: Boolean get() = transferCash

    /** A recorder may name another cash holder (collections, remittances, sales, transfers). */
    val recordForOthers: Boolean get() = cashCustody && can(COLLECTION_RECORD) && cash?.recordersMayRecordForOthers == true
    val askToKeepCash: Boolean get() = cashCustody && can(COLLECTION_RECORD) && cash?.retentionAllowed == true

    /** "Ask to keep cash" goes through the outbox (works offline) when the server accepts CASH_RETENTION_REQUEST. */
    val retentionOffline: Boolean get() = cashCustody && supports(SyncCapabilities.OP_CASH_RETENTION_REQUEST)
    val dailyReading: Boolean get() = engineHours && supports(SyncCapabilities.METER_DAILY_READING) && can(METER_CAPTURE)
    val proposeBaseline: Boolean get() = engineHours && supports(SyncCapabilities.OP_METER_BASELINE) && can(METER_CAPTURE)
    val proposeCorrection: Boolean get() = engineHours && supports(SyncCapabilities.OP_METER_CORRECTION) && can(METER_CAPTURE)

    /** Send a daily report (DEC-032 A4, outbox operation; ENGINE_HOURS on and the capture permission). */
    val dailyReport: Boolean get() = engineHours && supports(SyncCapabilities.OP_DAILY_REPORT) && can(METER_CAPTURE)

    /** See the daily reports of my machines (online read, saved on the phone). */
    val readDailyReports: Boolean get() = dailyReport && can(METER_READ)

    /** Record a mid-job changeover reading (DEC-032 A3). */
    val changeover: Boolean get() = engineHours && supports(SyncCapabilities.METER_CHANGEOVER) && can(METER_CAPTURE)

    /** The next job is mandatory on a changeover (the tenant bills the hours after it to that job). */
    val changeoverJobRequired: Boolean get() = engine?.changeoverSplitsBilling == true

    /** At least one photo is mandatory on a daily report. */
    val dailyReportEvidenceRequired: Boolean get() = engine?.dailyReportEvidenceRequired == true

    /** Revenue checks are in use (REVENUE_RECONCILIATION, platform default off, listed in `/me` while off). */
    val revenueOn: Boolean get() = TenantAccess.REVENUE_RECONCILIATION !in disabled

    /** Work-log entries show their non-revenue status (online read, DEC-031 R1). */
    val nonRevenueStatus: Boolean get() = revenueOn && can(REVENUE_READ)

    /** "Explain" on a non-revenue entry (online only; the reason list needs read too). */
    val explainNonRevenue: Boolean get() = nonRevenueStatus && can(REVENUE_EXPLAIN)

    /**
     * Site check-ins (DEC-031 M3): the server announces OP_SITE_CHECKIN only while the tenant requires them; the role
     * records check-ins and SITE_CHECKIN is not switched off.
     */
    val siteCheckin: Boolean
        get() = TenantAccess.SITE_CHECKIN !in disabled && supports(SyncCapabilities.OP_SITE_CHECKIN) && can(SITE_CHECKIN_RECORD)

    /** The handover form offers method, deposit account and deposit slip photos (DEC-031 D2). */
    val remittanceDetails: Boolean get() = supports(SyncCapabilities.REMITTANCE_DETAILS_V1)

    /** The tenant keeps company deposit accounts (not switched off): the handover form offers the account picker. */
    val depositAccounts: Boolean get() = TenantAccess.DEPOSIT_ACCOUNTS !in disabled

    /** What the tenant requires on a remittance; nothing while CASH_CUSTODY is off or the policy is unknown. */
    val remittanceRequirements: RemittanceRequirements
        get() = cash?.takeIf { cashCustody && remittanceDetails }?.remittanceRequirements
            ?.let { if (depositAccounts) it else it.copy(accountRequired = false) } ?: RemittanceRequirements()

    /** DEC-032 Phase 3: the server takes the collection link, partial reason and transfer evidence. */
    val cashDetailsV2: Boolean get() = supports(SyncCapabilities.CASH_DETAILS_V2)

    /** Collections offer "Pays for" (a purchase, or an offline purchase's client id); required per policy. */
    val collectionLink: Boolean get() = cashDetailsV2 && can(COLLECTION_RECORD)
    val collectionLinkRequired: Boolean get() = collectionLink && cash?.collectionLinkRequired == true

    /** "Pays for" also lists open invoices (DEC-032 Phase 4, SYNC_OPEN_INVOICES). */
    val openInvoices: Boolean get() = collectionLink && supports(SyncCapabilities.SYNC_OPEN_INVOICES)

    /** Under the full-remittance policy the handover asks why part of the balance stays with the custodian. */
    val partialReason: Boolean get() = cashDetailsV2 && cashCustody && cash?.remitFullBalance == true

    /** The hours transfer form offers evidence photos; at least one is required per policy. */
    val transferEvidence: Boolean get() = cashDetailsV2 && customerHours
    val transferEvidenceRequired: Boolean get() = transferEvidence && hours?.transferEvidenceRequired == true

    /**
     * DEC-033 petty cash: the server announces OP_PETTY_CASH (only while the tenant uses it), the role reads petty cash
     * (a holder sees only the funds they hold) and PETTY_CASH is not switched off in `/me`.
     */
    val pettyCash: Boolean
        get() = TenantAccess.PETTY_CASH !in disabled && supports(SyncCapabilities.OP_PETTY_CASH) && can(PETTY_CASH_READ)

    /** Record a physical count of a fund I hold. */
    val pettyCashCount: Boolean get() = pettyCash && can(PETTY_CASH_COUNT)

    /** Give an advance from a fund I hold (the screen also needs the policy's advances_enabled). */
    val pettyCashGiveAdvance: Boolean get() = pettyCash && supports(SyncCapabilities.OP_PETTY_CASH_ADVANCE)

    /** Pay an expense from a fund (the form also needs a fund or an advance on the phone). */
    val pettyCashExpense: Boolean get() = pettyCash && can(EXPENSE_WRITE)

    companion object {
        const val PETTY_CASH_READ = "tenant.pettycash.read"
        const val PETTY_CASH_COUNT = "tenant.pettycash.count"
        const val EXPENSE_WRITE = "tenant.expense.write"
        const val HOURS_PURCHASE = "tenant.hours.purchase"
        const val HOURS_TRANSFER = "tenant.hours.transfer"
        const val HOURS_READ = "tenant.hours.read"
        const val COLLECTION_RECORD = "tenant.collection.record"
        const val METER_CAPTURE = "tenant.meter.capture"
        const val METER_READ = "tenant.meter.read"
        const val REVENUE_READ = "tenant.revenue.read"
        const val REVENUE_EXPLAIN = "tenant.revenue.explain"
        const val SITE_CHECKIN_RECORD = "tenant.site_checkin.record"
    }
}

enum class PaymentMethod(val wire: String) { CASH("CASH"), BANK("BANK"), MOBILE_MONEY("MOBILE_MONEY") }

/**
 * One payment line of the hours sale as typed (the reference only for bank and mobile money). [followsTotal]: the opening
 * Cash line, whose amount tracks the sale total until the user types into it ([HoursPayments.follow]); never sent.
 */
data class PaymentLine(
    val method: PaymentMethod = PaymentMethod.CASH,
    val amountText: String = "",
    val reference: String = "",
    val followsTotal: Boolean = false,
) {
    /** The user typed the amount: it no longer follows the total. */
    fun typed(amount: String) = copy(amountText = amount, followsTotal = false)
}

/** The hours-sale form as typed (validated by [AccountabilityRules.hoursSale]); no payment lines = not paid yet. */
data class HoursSaleDraft(
    val walkIn: Boolean,
    val customerId: String?,
    val walkInName: String,
    val walkInPhone: String,
    val machineId: String?,
    val hoursText: String,
    val payments: List<PaymentLine>,
    val note: String,
)

/** A checked payment part (`PurchasePaymentIn`). */
data class PaymentPart(val method: PaymentMethod, val amount: BigDecimal, val reference: String?)

data class HoursSaleValues(
    val hours: BigDecimal,
    val payments: List<PaymentPart>,
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

    /** The hours of a sale as typed (more than 0, at most 2 decimals), or null while they are not a valid number. */
    fun saleHours(text: String): BigDecimal? = AmountParser.valueOrNull(text, HOURS)

    /**
     * [noncashAllowed]: the tenant lets field staff record bank and mobile-money parts (CUSTOMER_HOURS
     * `field_noncash_payments`); [price]: the offline total, which the parts may not exceed.
     */
    fun hoursSale(
        d: HoursSaleDraft,
        walkInAllowed: Boolean,
        noncashAllowed: Boolean = false,
        price: HoursSalePrice = HoursSalePrice.Hidden,
    ): FormCheck<HoursSaleValues> {
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
        if (d.payments.size > HoursPayments.MAX) m += AccountabilityMessages.TOO_MANY_PAYMENTS
        val lineProblems = linkedSetOf<String>()
        val parts = d.payments.mapNotNull { line ->
            val amount = AmountParser.valueOrNull(line.amountText, DecimalLimit.MONEY)
            if (amount == null) lineProblems += AccountabilityMessages.AMOUNT_RECEIVED
            val reference = line.reference.trim().take(MAX_REFERENCE).ifEmpty { null }
            if (line.method != PaymentMethod.CASH) {
                if (!noncashAllowed) lineProblems += AccountabilityMessages.NONCASH_OFF
                if (reference == null) lineProblems += AccountabilityMessages.REFERENCE
            }
            amount?.let { PaymentPart(line.method, it, reference.takeIf { line.method != PaymentMethod.CASH }) }
        }
        m += lineProblems
        if (price is HoursSalePrice.Priced && parts.fold(BigDecimal.ZERO) { s, p -> s + p.amount } > price.quote.amount) {
            m += AccountabilityMessages.paymentsExceed(HoursPricing.money(price.quote.amount, price.quote.currency, price.quote.minorUnits))
        }
        val note = d.note.trim().take(MAX_NOTE).ifEmpty { null }
        return if (m.isEmpty()) FormCheck.Valid(HoursSaleValues(hours!!, parts, name, phone, note)) else FormCheck.Invalid(m)
    }

    /** True when a bank or mobile-money line has no reference yet (shown under that line's Reference field). */
    fun referenceMissing(line: PaymentLine): Boolean = line.method != PaymentMethod.CASH && line.reference.isBlank()

    /**
     * Every rule of [hoursSale] that keeps Save off, as one plain line ("To save: enter the reference for payments 2 and
     * 3."); null when the sale can be saved. Same rules, same order as [hoursSale].
     */
    fun hoursSaleBlockers(
        d: HoursSaleDraft,
        walkInAllowed: Boolean,
        noncashAllowed: Boolean = false,
        price: HoursSalePrice = HoursSalePrice.Hidden,
    ): String? {
        if (hoursSale(d, walkInAllowed, noncashAllowed, price) is FormCheck.Valid) return null
        val todo = mutableListOf<String>()
        if (d.walkIn) {
            if (!walkInAllowed) todo += AccountabilityMessages.TODO_REGISTERED
            if (d.walkInName.isBlank()) todo += AccountabilityMessages.TODO_NAME
            val phone = d.walkInPhone.trim()
            if (phone.isNotEmpty() && (phone.length < MIN_PHONE || phone.length > MAX_PHONE)) todo += AccountabilityMessages.TODO_PHONE
        } else if (d.customerId.isNullOrBlank()) {
            todo += AccountabilityMessages.TODO_CUSTOMER
        }
        if (d.machineId.isNullOrBlank()) todo += AccountabilityMessages.TODO_MACHINE
        if (AmountParser.valueOrNull(d.hoursText, HOURS) == null) todo += AccountabilityMessages.TODO_HOURS
        if (d.payments.size > HoursPayments.MAX) todo += AccountabilityMessages.TODO_TOO_MANY
        fun numbers(test: (PaymentLine) -> Boolean) = d.payments.withIndex().filter { test(it.value) }.map { it.index + 1 }
        numbers { AmountParser.valueOrNull(it.amountText, DecimalLimit.MONEY) == null }
            .takeIf { it.isNotEmpty() }?.let { todo += AccountabilityMessages.todoAmount(it) }
        if (!noncashAllowed) {
            numbers { it.method != PaymentMethod.CASH }.takeIf { it.isNotEmpty() }?.let { todo += AccountabilityMessages.todoCash(it) }
        }
        numbers(::referenceMissing).takeIf { it.isNotEmpty() }?.let { todo += AccountabilityMessages.todoReference(it) }
        if (price is HoursSalePrice.Priced && HoursPayments.paid(d.payments) > price.quote.amount) {
            todo += AccountabilityMessages.todoLower(HoursPricing.money(price.quote.amount, price.quote.currency, price.quote.minorUnits))
        }
        return AccountabilityMessages.toSave(todo)
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
    const val NONCASH_OFF = "Bank and mobile-money payments are recorded by the office."
    const val TOO_MANY_PAYMENTS = "At most 10 payments per sale."
    fun paymentsExceed(total: String) = "The payments add up to more than the total of $total."

    /** Under a bank or mobile-money line's Reference field while it is empty. */
    const val REFERENCE_LINE = "Enter the reference for this payment"

    // "To save: …" line under the payment summary: what keeps Save off (field.hours.toSave*).
    const val TODO_REGISTERED = "choose a registered customer"
    const val TODO_NAME = "enter the customer's name"
    const val TODO_PHONE = "fix the phone number (at least 3 characters)"
    const val TODO_CUSTOMER = "choose the customer"
    const val TODO_MACHINE = "choose the machine"
    const val TODO_HOURS = "enter the hours (more than 0)"
    const val TODO_TOO_MANY = "remove payments (at most 10)"
    fun todoAmount(n: List<Int>) = "enter the amount for ${payments(n)}"
    fun todoCash(n: List<Int>) = "change ${payments(n)} to cash"
    fun todoReference(n: List<Int>) = "enter the reference for ${payments(n)}"
    fun todoLower(total: String) = "lower the payments to the total of $total"

    /** "To save: a, b and c."; null when there is nothing to do. */
    fun toSave(todo: List<String>): String? = if (todo.isEmpty()) null else "To save: ${and(todo)}."

    /** "payment 2", "payments 2 and 3", "payments 1, 2 and 3". */
    fun payments(n: List<Int>) = if (n.size == 1) "payment ${n[0]}" else "payments ${and(n.map(Int::toString))}"

    private fun and(items: List<String>) = if (items.size == 1) items[0] else items.dropLast(1).joinToString(", ") + " and " + items.last()
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
    const val COLLECTION_LINK_REQUIRED = "Your company requires every collection to name its purchase or invoice."
    const val PARTIAL_REASON = "Enter why part of the cash stays with you (at least 3 characters)."
    const val TRANSFER_EVIDENCE_REQUIRED = "Photograph the evidence for this transfer."
    const val PURCHASE_GONE = "The purchase you chose was not accepted by the server. Choose another one."

    fun tooMany(remaining: BigDecimal): String = "Only ${AccountabilityRules.plain(remaining)} h are left on this purchase."
}
