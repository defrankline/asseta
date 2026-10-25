package com.asseta.supervisor.ui.accountability

import androidx.compose.foundation.lazy.LazyListScope
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.domain.inbox.InboxStatusRules
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.sync.data.FieldAccountabilityCache
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.supervisor.ui.EmptyState
import com.asseta.supervisor.ui.InboxRow
import com.asseta.supervisor.ui.InboxTexts
import com.asseta.supervisor.ui.LocalTime
import com.asseta.supervisor.ui.Route

/** A row of the "Cash to acknowledge" section: a transfer or a float waiting for my answer. */
data class AckRow(val id: String, val isFloat: Boolean, val title: String, val amount: String, val currency: String, val atIso: String)

/** A row of the Transfers segment: the server's transfer, or this phone's transfer not yet synced. */
data class TransferRow(val key: String, val title: String, val amount: String, val currency: String, val status: InboxStatus, val statusText: String?, val atMs: Long)

/** A row of "Requests to keep cash": [key] is the form's client id (the outbox entity id). */
data class RetentionRow(val key: String, val amount: String, val currency: String, val reason: String, val status: InboxStatus, val atMs: Long)

private val T = FieldAccountabilityTexts

/** Pure presentation of the accountability parts of the Money tab (unit-tested). */
object MoneyAccountability {
    /** Transfers to me and floats waiting for my answer, minus those this phone already answered. */
    fun toAcknowledge(cache: FieldAccountabilityCache, me: String?, answered: Set<String>): List<AckRow> {
        val transfers = cache.transfersToAcknowledge(me).filter { it.id !in answered }.map {
            AckRow(it.id, false, FieldAccountabilityTexts.transferFrom(T.colleague(it.fromStaffName, cache.custodianName(it.fromStaffId), it.fromStaffId)),
                it.amountDeclared, it.currency, it.transferredAt)
        }
        val floats = cache.floats.filter { it.ackRequired && it.id !in answered && it.ackStatus != "ACKNOWLEDGED" && it.ackStatus != "DISPUTED" }.map {
            AckRow(it.id, true, FieldAccountabilityTexts.FLOAT_FROM_OFFICE, it.amount, it.currency, it.occurredAt)
        }
        return (transfers + floats).sortedByDescending { it.atIso }
    }

    /** Ids this phone already answered (acknowledgement operations in the outbox). */
    fun answeredIds(ops: List<ClientOperationEntity>): Set<String> = ops.filter {
        it.opType == AccountabilityOps.CASH_TRANSFER_ACKNOWLEDGEMENT || it.opType == AccountabilityOps.CASH_FLOAT_ACKNOWLEDGEMENT
    }.map { it.entityId }.toSet()

    /** My transfers (server copy) and this phone's transfers not yet acknowledged by the server, newest first. */
    fun transfers(cache: FieldAccountabilityCache, me: String?, ops: List<ClientOperationEntity>, payloadOf: (ClientOperationEntity) -> Map<String, String?>): List<TransferRow> {
        val server = cache.transfers.map { t ->
            val outgoing = t.fromStaffId == me
            val title = if (outgoing) {
                T.transferTo(T.colleague(t.toStaffName, cache.custodianName(t.toStaffId), t.toStaffId))
            } else {
                T.transferFromRow(T.colleague(t.fromStaffName, cache.custodianName(t.fromStaffId), t.fromStaffId))
            }
            val status = when (t.status) {
                CashTransferDto.ACKNOWLEDGED -> InboxStatus.ACCEPTED
                CashTransferDto.DISPUTED -> InboxStatus.REJECTED
                else -> InboxStatus.PENDING
            }
            TransferRow(t.id, title, t.amountReceived ?: t.amountDeclared, t.currency, status, FieldAccountabilityTexts.transferStatus(t.status), ms(t.transferredAt))
        }
        val known = cache.transfers.mapNotNull { it.clientId }.toSet()
        val local = ops.filter { it.opType == AccountabilityOps.CASH_TRANSFER && it.entityId !in known }.map { op ->
            val p = payloadOf(op)
            TransferRow(op.id, T.transferTo(T.colleague(null, cache.custodianName(p["to_staff_id"]), p["to_staff_id"])), p["amount"].orEmpty(), p["currency"].orEmpty(),
                InboxStatusRules.combined(op.status, null), null, op.createdAtDevice)
        }
        return (local + server).sortedByDescending { it.atMs }
    }

    /** This phone's requests to keep cash (newest first): amount, and the sync state until the server has it. */
    fun retentions(ops: List<ClientOperationEntity>, payloadOf: (ClientOperationEntity) -> Map<String, String?>): List<RetentionRow> =
        ops.filter { it.opType == AccountabilityOps.CASH_RETENTION_REQUEST }.map { op ->
            val p = payloadOf(op)
            RetentionRow(op.entityId, p["amount"].orEmpty(), p["currency"].orEmpty(), p["reason"].orEmpty(), InboxStatusRules.combined(op.status, null), op.createdAtDevice)
        }.sortedByDescending { it.atMs }

    private fun ms(iso: String): Long = runCatching { java.time.OffsetDateTime.parse(iso).toInstant().toEpochMilli() }.getOrDefault(0L)
}

fun LazyListScope.cashToAcknowledgeSection(rows: List<AckRow>, onRoute: (Route) -> Unit) {
    if (rows.isEmpty()) return
    groupedSection(
        keyPrefix = "to-ack", header = FieldAccountabilityTexts.ACK_SECTION,
        items = rows.map { r ->
            GroupedItem("ack-${r.id}", onClick = { onRoute(Route.CashAck(r.id, r.isFloat)) }) {
                InboxRow(r.title, null, InboxTexts.money(r.amount, r.currency), LocalTime.formatIso(r.atIso))
            }
        },
    )
}

fun LazyListScope.transfersSection(rows: List<TransferRow>, loaded: Boolean) {
    if (loaded && rows.isEmpty()) {
        item(key = "empty-transfers") { EmptyState(FieldAccountabilityTexts.TRANSFERS_EMPTY_TITLE, FieldAccountabilityTexts.TRANSFERS_EMPTY_MESSAGE) }
        return
    }
    groupedSection(
        keyPrefix = "transfers", header = null,
        items = rows.map { r ->
            GroupedItem("t-${r.key}") {
                InboxRow(r.title, r.status, InboxTexts.money(r.amount, r.currency), listOfNotNull(r.statusText, LocalTime.format(r.atMs)).joinToString(" · "))
            }
        },
    )
}

fun LazyListScope.retentionsSection(rows: List<RetentionRow>, onRoute: (Route) -> Unit) {
    if (rows.isEmpty()) return
    groupedSection(
        keyPrefix = "retentions", header = T.MONEY_RETENTIONS,
        items = rows.map { r ->
            GroupedItem("ret-${r.key}", onClick = { onRoute(Route.RetentionStatus(r.key)) }) {
                InboxRow(InboxTexts.money(r.amount, r.currency), r.status, r.reason, LocalTime.format(r.atMs))
            }
        },
    )
}
