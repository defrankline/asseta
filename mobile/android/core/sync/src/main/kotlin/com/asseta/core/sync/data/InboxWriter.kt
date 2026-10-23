package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.InboxRecordEntity
import com.asseta.core.database.InboxRecordEntity.Companion.ACKNOWLEDGEMENT
import com.asseta.core.database.InboxRecordEntity.Companion.CASH_COLLECTION
import com.asseta.core.database.InboxRecordEntity.Companion.CASH_HANDOVER
import com.asseta.core.database.InboxRecordEntity.Companion.EXPENSE
import com.asseta.core.database.InboxRecordEntity.Companion.FUEL_EVENT
import com.asseta.core.database.InboxRecordEntity.Companion.JOB_ACTIVITY
import com.asseta.core.database.InboxRecordEntity.Companion.METER_CAPTURE
import com.asseta.core.database.InboxRecordEntity.Companion.METER_RESET
import com.asseta.core.model.sync.SyncAcknowledgementDto
import com.asseta.core.model.sync.SyncCashCollectionDto
import com.asseta.core.model.sync.SyncCashHandoverDto
import com.asseta.core.model.sync.SyncData
import com.asseta.core.model.sync.SyncExpenseDto
import com.asseta.core.model.sync.SyncFuelEventDto
import com.asseta.core.model.sync.SyncJobActivityDto
import com.asseta.core.model.sync.SyncMeterCaptureDto
import com.asseta.core.model.sync.SyncMeterResetDto
import kotlinx.serialization.json.Json

/**
 * Writes the supervisor inbox lists of a pull (`SyncData.my_*`) into `inbox_record`, upserting by (kind, id,
 * sync_revision), then drops finished records older than the server's 30-day window. Lists the server did not send
 * (older server without SUPERVISOR_INBOX_V1) leave the stored inbox untouched.
 */
class InboxWriter(private val json: Json, private val nowMs: () -> Long = System::currentTimeMillis) {

    suspend fun apply(database: AssetaDatabase, tenantId: String, data: SyncData) {
        val records = records(tenantId, data)
        val inbox = database.inboxDao()
        if (records.isNotEmpty()) inbox.upsert(records)
        if (data.hasInbox) inbox.prune(tenantId, nowMs() - WINDOW_MS, InboxRecordEntity.OPEN_STATUSES)
    }

    fun records(tenantId: String, data: SyncData): List<InboxRecordEntity> = buildList {
        data.myMeterCaptures?.forEach { c ->
            val status = if (c.reviewStatus == "PENDING_REVIEW") c.reviewStatus else c.state
            add(row(METER_CAPTURE, c.id, tenantId, c.id, c.jobId, c.machineId, status, c.capturedAt, c.syncRevision,
                json.encodeToString(SyncMeterCaptureDto.serializer(), c)))
        }
        data.myMeterResets?.forEach { r ->
            add(row(METER_RESET, r.id, tenantId, null, null, r.machineId, r.status, r.createdAt, r.syncRevision,
                json.encodeToString(SyncMeterResetDto.serializer(), r)))
        }
        data.myJobActivities?.forEach { a ->
            add(row(JOB_ACTIVITY, a.id, tenantId, a.clientId, a.jobId, null, null, a.startedAt, a.syncRevision,
                json.encodeToString(SyncJobActivityDto.serializer(), a)))
        }
        data.myAcknowledgements?.forEach { a ->
            add(row(ACKNOWLEDGEMENT, a.id, tenantId, a.clientId, a.jobId, null, null, a.capturedAt, a.syncRevision,
                json.encodeToString(SyncAcknowledgementDto.serializer(), a)))
        }
        data.myExpenses?.forEach { e ->
            add(row(EXPENSE, e.id, tenantId, e.clientId, e.jobId, e.machineId, e.status, e.incurredAt, e.syncRevision,
                json.encodeToString(SyncExpenseDto.serializer(), e)))
        }
        data.myFuelEvents?.forEach { f ->
            add(row(FUEL_EVENT, f.id, tenantId, f.clientId, f.jobId, f.machineId, null, f.occurredAt, f.syncRevision,
                json.encodeToString(SyncFuelEventDto.serializer(), f)))
        }
        data.myCashCollections?.forEach { p ->
            add(row(CASH_COLLECTION, p.id, tenantId, p.clientId, null, null, p.status, p.receivedAt, p.syncRevision,
                json.encodeToString(SyncCashCollectionDto.serializer(), p)))
        }
        data.myCashHandovers?.forEach { h ->
            add(row(CASH_HANDOVER, h.id, tenantId, h.clientId, null, null, h.status, h.handedAt, h.syncRevision,
                json.encodeToString(SyncCashHandoverDto.serializer(), h)))
        }
    }

    private fun row(
        kind: String, id: String, tenantId: String, clientId: String?, jobId: String?, machineId: String?, status: String?,
        at: String, revision: Long, body: String,
    ) = InboxRecordEntity(kind, id, tenantId, clientId, jobId, machineId, status,
        runCatching { IsoTime.parse(at).toEpochMilli() }.getOrDefault(0L), revision, body)

    companion object {
        const val WINDOW_MS = 30L * 24 * 60 * 60 * 1000
    }
}

/** Whether the server sent any inbox list (SUPERVISOR_INBOX_V1). */
val SyncData.hasInbox: Boolean
    get() = listOf(myMeterCaptures, myMeterResets, myJobActivities, myAcknowledgements, myExpenses, myFuelEvents,
        myCashCollections, myCashHandovers).any { it != null }
