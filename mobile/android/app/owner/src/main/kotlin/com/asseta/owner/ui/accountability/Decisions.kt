package com.asseta.owner.ui.accountability

import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.BaselineDto
import com.asseta.core.model.owner.CashRetentionDto
import com.asseta.core.model.owner.CashVarianceDto
import com.asseta.core.model.owner.ClassificationDto
import com.asseta.core.model.owner.CorrectionDto
import com.asseta.core.model.owner.CreditArrangementDto
import com.asseta.core.model.owner.CustodyAdjustmentDto
import com.asseta.core.model.owner.DiscountDto
import com.asseta.core.model.owner.HoursCancellationDto
import com.asseta.core.model.owner.HoursTransferDto
import com.asseta.owner.ui.OwnerFeatures
import kotlinx.serialization.Serializable
import java.time.ZoneId

private val T = OwnerAccountabilityTexts

/**
 * One accountability decision kind: its Approvals section, the permission to see it, the [action] that decides it,
 * whether it is a meter decision (APPROVE/REJECT with a note of at least 5 characters) and the status that means
 * "waiting for a decision".
 */
enum class DecisionKind(
    val code: String,
    val header: String,
    val empty: String,
    val title: String,
    val action: OwnerAction,
    val meter: Boolean,
    val pendingStatus: String,
    private val visible: (OwnerFeatures) -> Boolean,
    /** The tenant capability (`/me` `disabled_capabilities` code) this kind belongs to. */
    val capability: String,
) {
    DISCOUNT(DecisionKinds.DISCOUNT, T.DISCOUNTS, T.DISCOUNTS_EMPTY, T.TITLE_DISCOUNT, OwnerAction.DECIDE_DISCOUNT, false, "PROPOSED", { it.customerHours }, TenantAccess.CUSTOMER_HOURS),
    CREDIT(DecisionKinds.CREDIT, T.CREDIT, T.CREDIT_EMPTY, T.TITLE_CREDIT, OwnerAction.DECIDE_CREDIT, false, "PROPOSED", { it.customerHours }, TenantAccess.CUSTOMER_HOURS),
    HOURS_TRANSFER(DecisionKinds.HOURS_TRANSFER, T.HOURS_TRANSFERS, T.HOURS_TRANSFERS_EMPTY, T.TITLE_HOURS_TRANSFER, OwnerAction.DECIDE_HOURS_TRANSFER, false, "PENDING", { it.customerHours }, TenantAccess.CUSTOMER_HOURS),
    CANCELLATION(DecisionKinds.CANCELLATION, T.CANCELLATIONS, T.CANCELLATIONS_EMPTY, T.TITLE_CANCELLATION, OwnerAction.DECIDE_HOURS_CANCELLATION, false, "PENDING", { it.customerHours }, TenantAccess.CUSTOMER_HOURS),
    BASELINE(DecisionKinds.BASELINE, T.BASELINES, T.BASELINES_EMPTY, T.TITLE_BASELINE, OwnerAction.DECIDE_BASELINE, true, "PROPOSED", { it.meterEvidence }, TenantAccess.ENGINE_HOURS),
    CLASSIFICATION(DecisionKinds.CLASSIFICATION, T.CLASSIFICATIONS, T.CLASSIFICATIONS_EMPTY, T.TITLE_CLASSIFICATION, OwnerAction.DECIDE_CLASSIFICATION, true, "PROPOSED", { it.meterEvidence }, TenantAccess.ENGINE_HOURS),
    CORRECTION(DecisionKinds.CORRECTION, T.CORRECTIONS, T.CORRECTIONS_EMPTY, T.TITLE_CORRECTION, OwnerAction.DECIDE_CORRECTION, true, "PROPOSED", { it.meterEvidence }, TenantAccess.ENGINE_HOURS),
    WRITE_OFF(DecisionKinds.WRITE_OFF, T.WRITE_OFFS, T.WRITE_OFFS_EMPTY, T.TITLE_WRITE_OFF, OwnerAction.DECIDE_WRITE_OFF, false, "WRITE_OFF_PROPOSED", { it.finance }, TenantAccess.CASH_CUSTODY),
    RETENTION(DecisionKinds.RETENTION, T.RETENTIONS, T.RETENTIONS_EMPTY, T.TITLE_RETENTION, OwnerAction.DECIDE_RETENTION, false, "PENDING", { it.custodyRead }, TenantAccess.CASH_CUSTODY),
    ADJUSTMENT(DecisionKinds.ADJUSTMENT, T.ADJUSTMENTS, T.ADJUSTMENTS_EMPTY, T.TITLE_ADJUSTMENT, OwnerAction.DECIDE_ADJUSTMENT, false, "PENDING", { it.finance }, TenantAccess.CASH_CUSTODY);

    /** The tenant switched off the capability this kind belongs to (its section and screen are hidden). */
    fun switchedOff(features: OwnerFeatures): Boolean = capability in features.disabled

    fun visibleTo(features: OwnerFeatures): Boolean = !switchedOff(features) && visible(features)

    companion object {
        fun of(code: String): DecisionKind? = entries.firstOrNull { it.code == code }

        /** Kinds the role may see, in Approvals order. */
        fun visible(features: OwnerFeatures): List<DecisionKind> = entries.filter { it.visibleTo(features) }
    }
}

@Serializable
data class DecisionField(val label: String, val value: String)

/** A request waiting for (or past) a decision, ready to show: one shape for every [DecisionKind]. */
@Serializable
data class DecisionItem(
    val kind: String,
    val id: String,
    val headline: String,
    val reason: String?,
    val proposedAt: String?,
    /** User id of the proposer (segregation of duties: they never decide it). */
    val proposedBy: String?,
    val status: String,
    val pending: Boolean,
    val fields: List<DecisionField>,
    /** Meter photo of a baseline proposal (fetched on demand). */
    val photoAttachmentId: String? = null,
    /** Who proposed it, by name (short id when the server sends no name). */
    val proposedByName: String? = null,
) {
    /** The signed-in user proposed this request, so someone else must decide it. */
    fun isOwn(userId: String?): Boolean = userId != null && proposedBy == userId
}

/** Pure mapping of the accountability DTOs to [DecisionItem]s (unit-tested). */
object DecisionMapper {
    private fun money(amount: String, currency: String): String =
        amount.toBigDecimalOrNull()?.let { OwnerFormat.money(it, currency) } ?: "$amount $currency"

    private fun num(value: String): String = value.toBigDecimalOrNull()?.let(OwnerFormat::decimal) ?: value

    private fun date(raw: String?, zone: ZoneId) = OwnerFormat.dateTime(raw, zone)

    private fun fields(vararg pairs: Pair<String, String?>): List<DecisionField> =
        pairs.mapNotNull { (l, v) -> v?.takeIf { it.isNotBlank() }?.let { DecisionField(l, it) } }

    private fun name(name: String?, id: String?) = DisplayNames.of(name, id)

    private fun decided(name: String?, id: String?, note: String?) =
        arrayOf(T.F_DECIDED_BY to name(name, id), T.F_DECISION_NOTE to note)

    fun discount(d: DiscountDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.DISCOUNT, d.id, T.rowDiscount(num(d.percent)), d.reason, d.proposedAt, d.proposedBy, d.status, d.status == "PROPOSED",
        fields(T.F_CUSTOMER to name(d.customerName, d.customerId), T.F_DISCOUNT to "${num(d.percent)}%",
            T.F_EFFECTIVE_FROM to date(d.effectiveFrom, zone), T.F_EFFECTIVE_TO to d.effectiveTo?.let { date(it, zone) },
            T.F_PROPOSED_BY to name(d.proposedByName, d.proposedBy), *decided(d.decidedByName, d.decidedBy, d.decisionNote)),
        proposedByName = name(d.proposedByName, d.proposedBy),
    )

    fun credit(c: CreditArrangementDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.CREDIT, c.id, T.rowCredit(money(c.limitAmount, c.currency)), c.reason, c.proposedAt, c.proposedBy, c.status, c.status == "PROPOSED",
        fields(T.F_CUSTOMER to name(c.customerName, c.customerId), T.F_CREDIT_LIMIT to money(c.limitAmount, c.currency), T.F_TERMS to c.terms,
            T.F_EFFECTIVE_FROM to date(c.effectiveFrom, zone), T.F_EFFECTIVE_TO to c.effectiveTo?.let { date(it, zone) },
            T.F_PROPOSED_BY to name(c.proposedByName, c.proposedBy), *decided(c.decidedByName, c.decidedBy, c.decisionNote)),
        proposedByName = name(c.proposedByName, c.proposedBy),
    )

    fun hoursTransfer(t: HoursTransferDto) = DecisionItem(
        DecisionKinds.HOURS_TRANSFER, t.id, T.rowHoursTransfer(num(t.hours)), t.reason, t.requestedAt, t.requestedBy, t.status, t.status == "PENDING",
        fields(T.F_CUSTOMER to t.customerName, T.F_PURCHASE to name(t.purchaseNumber, t.purchaseId), T.F_HOURS to num(t.hours),
            T.F_FROM_MACHINE to DisplayNames.machine(t.fromMachineCode, t.fromMachineName, t.fromMachineId),
            T.F_TO_MACHINE to DisplayNames.machine(t.toMachineCode, t.toMachineName, t.toMachineId),
            T.F_REQUESTED_BY to name(t.requestedByName, t.requestedBy), *decided(t.decidedByName, t.decidedBy, t.decisionNote)),
        proposedByName = name(t.requestedByName, t.requestedBy),
    )

    fun cancellation(c: HoursCancellationDto) = DecisionItem(
        DecisionKinds.CANCELLATION, c.id, T.ROW_CANCELLATION, c.reason, c.requestedAt, c.requestedBy, c.status, c.status == "PENDING",
        fields(T.F_CUSTOMER to c.customerName, T.F_PURCHASE to name(c.purchaseNumber, c.purchaseId),
            T.F_REQUESTED_BY to name(c.requestedByName, c.requestedBy), *decided(c.decidedByName, c.decidedBy, c.decisionNote)),
        proposedByName = name(c.requestedByName, c.requestedBy),
    )

    fun baseline(b: BaselineDto, zone: ZoneId): DecisionItem {
        val machine = b.machineCode ?: b.machineName ?: DisplayNames.shortId(b.machineId).orEmpty()
        return DecisionItem(
            DecisionKinds.BASELINE, b.id, T.rowBaseline(num(b.reading), machine), b.note, b.proposedAt, b.proposedBy, b.status, b.status == "PROPOSED",
            fields(T.F_MACHINE to DisplayNames.machine(b.machineCode, b.machineName, b.machineId), T.F_READING to num(b.reading),
                T.F_PROPOSED_BY to name(b.proposedByName, b.proposedBy), T.F_CAPTURED to date(b.capturedAt, zone),
                *decided(b.decidedByName, b.decidedBy, b.decisionNote)),
            photoAttachmentId = b.photoAttachmentId,
            proposedByName = name(b.proposedByName, b.proposedBy),
        )
    }

    fun classification(c: ClassificationDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.CLASSIFICATION, c.id, T.rowClassification(num(c.hours), c.reasonName ?: OwnerFormat.humanize(c.outcome)), c.note,
        c.proposedAt, c.proposedBy, c.status, c.status == "PROPOSED",
        fields(T.F_MACHINE to DisplayNames.machine(c.machineCode, c.machineName, c.machineId), T.F_HOURS to num(c.hours),
            T.F_PERIOD to "${date(c.startAt, zone)} – ${date(c.endAt, zone)}", T.F_CATEGORY to c.reasonName, T.F_OUTCOME to outcome(c.outcome),
            T.F_PROPOSED_BY to name(c.proposedByName, c.proposedBy), *decided(c.decidedByName, c.decidedBy, c.decisionNote)),
        proposedByName = name(c.proposedByName, c.proposedBy),
    )

    fun correction(c: CorrectionDto) = DecisionItem(
        DecisionKinds.CORRECTION, c.id,
        T.rowCorrection(num(c.oldReading), num(c.newReading), c.machineCode ?: c.machineName ?: DisplayNames.shortId(c.machineId).orEmpty()), c.reason,
        c.proposedAt, c.proposedBy, c.status, c.status == "PROPOSED",
        fields(T.F_MACHINE to DisplayNames.machine(c.machineCode, c.machineName, c.machineId), T.F_JOB to DisplayNames.of(c.jobNumber, c.jobId),
            T.F_OLD_READING to num(c.oldReading), T.F_NEW_READING to num(c.newReading),
            T.F_PROPOSED_BY to name(c.proposedByName, c.proposedBy), *decided(c.decidedByName, c.decidedBy, c.decisionNote)),
        proposedByName = name(c.proposedByName, c.proposedBy),
    )

    /** More received than declared ("Surplus to explain"); older servers send no kind, a negative amount means the same. */
    fun isSurplus(v: CashVarianceDto): Boolean =
        v.kind == "SURPLUS" || (v.kind == null && (v.amount.toBigDecimalOrNull()?.signum() ?: 0) < 0)

    fun writeOff(v: CashVarianceDto): DecisionItem {
        val surplus = isSurplus(v)
        val difference = if (surplus) money(v.amount.removePrefix("-"), v.currency) else money(v.amount, v.currency)
        return writeOffItem(v, if (surplus) T.rowSurplus(difference) else T.rowWriteOff(difference),
            (if (surplus) T.VARIANCE_SURPLUS else T.F_DIFFERENCE) to difference)
    }

    private fun writeOffItem(v: CashVarianceDto, headline: String, difference: Pair<String, String>) = DecisionItem(
        DecisionKinds.WRITE_OFF, v.id, headline, v.proposalNote, v.proposedAt ?: v.openedAt, v.proposedBy, v.status,
        v.status == "WRITE_OFF_PROPOSED",
        fields(T.F_CUSTODIAN to name(v.staffMemberName, v.staffMemberId), T.F_COUNTERPARTY to name(v.counterpartyStaffName, v.counterpartyStaffId),
            T.F_SOURCE to OwnerFormat.humanize(v.sourceType), T.F_DECLARED to money(v.declaredAmount, v.currency),
            T.F_RECEIVED to money(v.receivedAmount, v.currency), difference,
            T.F_PROPOSED_BY to name(v.proposedByName, v.proposedBy), T.F_DECIDED_BY to name(v.resolvedByName, v.resolvedBy),
            T.F_DECISION_NOTE to v.resolutionNote),
        proposedByName = name(v.proposedByName, v.proposedBy),
    )

    fun retention(r: CashRetentionDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.RETENTION, r.id, T.rowRetention(money(r.amount, r.currency)), r.reason, r.createdAt, r.createdBy, r.status, r.status == "PENDING",
        fields(T.F_CUSTODIAN to name(r.staffMemberName, r.staffMemberId), T.F_AMOUNT to money(r.amount, r.currency),
            T.F_VALID_UNTIL to r.validUntil?.let { date(it, zone) }, T.F_REQUESTED_BY to name(r.createdByName, r.createdBy),
            *decided(r.decidedByName, r.decidedBy, r.decisionNote)),
        proposedByName = name(r.createdByName, r.createdBy),
    )

    fun adjustment(a: CustodyAdjustmentDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.ADJUSTMENT, a.id, T.rowAdjustment(OwnerFormat.humanize(a.kind), money(a.amount, a.currency)), a.reason, a.createdAt, a.createdBy,
        a.status, a.status == "PENDING",
        fields(T.F_CUSTODIAN to name(a.staffMemberName, a.staffMemberId), T.F_KIND to OwnerFormat.humanize(a.kind),
            T.F_AMOUNT to money(a.amount, a.currency), T.F_WHEN to date(a.occurredAt, zone),
            T.F_PROPOSED_BY to name(a.createdByName, a.createdBy), *decided(a.decidedByName, a.decidedBy, a.decisionNote)),
        proposedByName = name(a.createdByName, a.createdBy),
    )

    fun outcome(code: String): String = when (code) {
        "APPROVED_NON_CUSTOMER" -> T.OUTCOME_NON_CUSTOMER
        "IDENTIFIED_VARIANCE" -> T.OUTCOME_VARIANCE
        else -> OwnerFormat.humanize(code)
    }

    /** A meter decision needs a note of at least 5 characters; elsewhere a rejection needs a note. */
    fun canDecide(kind: DecisionKind, approve: Boolean, note: String): Boolean =
        if (kind.meter) note.trim().length >= METER_NOTE_MIN else approve || note.isNotBlank()

    const val METER_NOTE_MIN = 5
}
