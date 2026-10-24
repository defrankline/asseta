package com.asseta.owner.ui.accountability

import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerFormat
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
) {
    DISCOUNT(DecisionKinds.DISCOUNT, T.DISCOUNTS, T.DISCOUNTS_EMPTY, T.TITLE_DISCOUNT, OwnerAction.DECIDE_DISCOUNT, false, "PROPOSED", { it.hoursRead }),
    CREDIT(DecisionKinds.CREDIT, T.CREDIT, T.CREDIT_EMPTY, T.TITLE_CREDIT, OwnerAction.DECIDE_CREDIT, false, "PROPOSED", { it.hoursRead }),
    HOURS_TRANSFER(DecisionKinds.HOURS_TRANSFER, T.HOURS_TRANSFERS, T.HOURS_TRANSFERS_EMPTY, T.TITLE_HOURS_TRANSFER, OwnerAction.DECIDE_HOURS_TRANSFER, false, "PENDING", { it.hoursRead }),
    CANCELLATION(DecisionKinds.CANCELLATION, T.CANCELLATIONS, T.CANCELLATIONS_EMPTY, T.TITLE_CANCELLATION, OwnerAction.DECIDE_HOURS_CANCELLATION, false, "PENDING", { it.hoursRead }),
    BASELINE(DecisionKinds.BASELINE, T.BASELINES, T.BASELINES_EMPTY, T.TITLE_BASELINE, OwnerAction.DECIDE_BASELINE, true, "PROPOSED", { it.meterEvidence }),
    CLASSIFICATION(DecisionKinds.CLASSIFICATION, T.CLASSIFICATIONS, T.CLASSIFICATIONS_EMPTY, T.TITLE_CLASSIFICATION, OwnerAction.DECIDE_CLASSIFICATION, true, "PROPOSED", { it.meterEvidence }),
    CORRECTION(DecisionKinds.CORRECTION, T.CORRECTIONS, T.CORRECTIONS_EMPTY, T.TITLE_CORRECTION, OwnerAction.DECIDE_CORRECTION, true, "PROPOSED", { it.meterEvidence }),
    WRITE_OFF(DecisionKinds.WRITE_OFF, T.WRITE_OFFS, T.WRITE_OFFS_EMPTY, T.TITLE_WRITE_OFF, OwnerAction.DECIDE_WRITE_OFF, false, "WRITE_OFF_PROPOSED", { it.finance }),
    RETENTION(DecisionKinds.RETENTION, T.RETENTIONS, T.RETENTIONS_EMPTY, T.TITLE_RETENTION, OwnerAction.DECIDE_RETENTION, false, "PENDING", { it.custodyRead }),
    ADJUSTMENT(DecisionKinds.ADJUSTMENT, T.ADJUSTMENTS, T.ADJUSTMENTS_EMPTY, T.TITLE_ADJUSTMENT, OwnerAction.DECIDE_ADJUSTMENT, false, "PENDING", { it.finance });

    fun visibleTo(features: OwnerFeatures): Boolean = visible(features)

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

    fun discount(d: DiscountDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.DISCOUNT, d.id, T.rowDiscount(num(d.percent)), d.reason, d.proposedAt, d.proposedBy, d.status, d.status == "PROPOSED",
        fields(T.F_DISCOUNT to "${num(d.percent)}%", T.F_EFFECTIVE_FROM to date(d.effectiveFrom, zone), T.F_EFFECTIVE_TO to d.effectiveTo?.let { date(it, zone) }),
    )

    fun credit(c: CreditArrangementDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.CREDIT, c.id, T.rowCredit(money(c.limitAmount, c.currency)), c.reason, c.proposedAt, c.proposedBy, c.status, c.status == "PROPOSED",
        fields(T.F_CREDIT_LIMIT to money(c.limitAmount, c.currency), T.F_TERMS to c.terms, T.F_EFFECTIVE_FROM to date(c.effectiveFrom, zone),
            T.F_EFFECTIVE_TO to c.effectiveTo?.let { date(it, zone) }),
    )

    fun hoursTransfer(t: HoursTransferDto, machines: Map<String, String>) = DecisionItem(
        DecisionKinds.HOURS_TRANSFER, t.id, T.rowHoursTransfer(num(t.hours)), t.reason, t.requestedAt, t.requestedBy, t.status, t.status == "PENDING",
        fields(T.F_HOURS to num(t.hours), T.F_FROM_MACHINE to machines[t.fromMachineId], T.F_TO_MACHINE to machines[t.toMachineId]),
    )

    fun cancellation(c: HoursCancellationDto) = DecisionItem(
        DecisionKinds.CANCELLATION, c.id, T.ROW_CANCELLATION, c.reason, c.requestedAt, c.requestedBy, c.status, c.status == "PENDING", emptyList(),
    )

    fun baseline(b: BaselineDto, zone: ZoneId): DecisionItem {
        val machine = b.machineCode ?: b.machineName.orEmpty()
        return DecisionItem(
            DecisionKinds.BASELINE, b.id, T.rowBaseline(num(b.reading), machine), b.note, b.proposedAt, b.proposedBy, b.status, b.status == "PROPOSED",
            fields(T.F_MACHINE to listOfNotNull(b.machineCode, b.machineName).joinToString(" · "), T.F_READING to num(b.reading),
                T.F_PROPOSED_BY to b.proposedByName, T.F_CAPTURED to date(b.capturedAt, zone)),
            photoAttachmentId = b.photoAttachmentId,
        )
    }

    fun classification(c: ClassificationDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.CLASSIFICATION, c.id, T.rowClassification(num(c.hours), c.reasonName ?: OwnerFormat.humanize(c.outcome)), c.note,
        c.proposedAt, c.proposedBy, c.status, c.status == "PROPOSED",
        fields(T.F_MACHINE to c.machineCode, T.F_HOURS to num(c.hours), T.F_PERIOD to "${date(c.startAt, zone)} – ${date(c.endAt, zone)}",
            T.F_CATEGORY to c.reasonName, T.F_OUTCOME to outcome(c.outcome), T.F_PROPOSED_BY to c.proposedByName),
    )

    fun correction(c: CorrectionDto) = DecisionItem(
        DecisionKinds.CORRECTION, c.id, T.rowCorrection(num(c.oldReading), num(c.newReading), c.machineCode.orEmpty()), c.reason,
        c.proposedAt, c.proposedBy, c.status, c.status == "PROPOSED",
        fields(T.F_MACHINE to c.machineCode, T.F_OLD_READING to num(c.oldReading), T.F_NEW_READING to num(c.newReading), T.F_PROPOSED_BY to c.proposedByName),
    )

    fun writeOff(v: CashVarianceDto) = DecisionItem(
        DecisionKinds.WRITE_OFF, v.id, T.rowWriteOff(money(v.amount, v.currency)), v.proposalNote, v.proposedAt, v.proposedBy, v.status,
        v.status == "WRITE_OFF_PROPOSED",
        fields(T.F_SOURCE to OwnerFormat.humanize(v.sourceType), T.F_DECLARED to money(v.declaredAmount, v.currency),
            T.F_RECEIVED to money(v.receivedAmount, v.currency), T.F_DIFFERENCE to money(v.amount, v.currency)),
    )

    fun retention(r: CashRetentionDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.RETENTION, r.id, T.rowRetention(money(r.amount, r.currency)), r.reason, r.createdAt, r.createdBy, r.status, r.status == "PENDING",
        fields(T.F_AMOUNT to money(r.amount, r.currency), T.F_VALID_UNTIL to r.validUntil?.let { date(it, zone) }),
    )

    fun adjustment(a: CustodyAdjustmentDto, zone: ZoneId) = DecisionItem(
        DecisionKinds.ADJUSTMENT, a.id, T.rowAdjustment(OwnerFormat.humanize(a.kind), money(a.amount, a.currency)), a.reason, a.createdAt, a.createdBy,
        a.status, a.status == "PENDING",
        fields(T.F_KIND to OwnerFormat.humanize(a.kind), T.F_AMOUNT to money(a.amount, a.currency), T.F_WHEN to date(a.occurredAt, zone)),
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
