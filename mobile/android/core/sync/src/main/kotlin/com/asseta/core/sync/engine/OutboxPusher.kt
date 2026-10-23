package com.asseta.core.sync.engine

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.sync.OutboxTransitions
import com.asseta.core.domain.sync.PushOutcome
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.OperationIn
import com.asseta.core.model.sync.OperationResultDto
import com.asseta.core.model.sync.PushIn
import com.asseta.core.model.sync.PushResultDto
import com.asseta.core.network.SyncApi
import com.asseta.core.sync.SyncClock
import com.asseta.core.sync.data.IsoTime
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull

data class PushSummary(val sent: Int = 0, val acked: Int = 0, val deferred: Int = 0, val problems: Int = 0)

/**
 * Pushes the outbox in bounded batches with `device_now`. Each op is marked SENT before the request; per-op results
 * are applied through the domain state machine; a transport failure returns the whole batch to PENDING (the retry is
 * idempotent by operation id). Nothing becomes ACKED without a server ACKED/DUPLICATE result.
 */
class OutboxPusher(
    private val api: SyncApi,
    private val db: () -> AssetaDatabase,
    private val clock: SyncClock,
    private val json: Json,
) {
    /** Pushes [ownerSub]'s operations only (the token in use is theirs); other users' operations stay held. */
    suspend fun pushAll(tenantId: String, ownerSub: String, maxBatch: Int): PushSummary {
        var summary = PushSummary()
        repeat(MAX_ROUNDS) {
            val ops = db().clientOperationDao()
            val batch = ops.dispatchable(tenantId, ownerSub, maxBatch.coerceIn(1, MAX_BATCH))
            if (batch.isEmpty()) return summary
            val round = pushBatch(tenantId, batch)
            summary = PushSummary(
                summary.sent + round.sent, summary.acked + round.acked,
                summary.deferred + round.deferred, summary.problems + round.problems,
            )
            if (round.acked == 0) return summary // only deferrals/problems: no new parents ACKED, stop this run
        }
        return summary
    }

    private suspend fun pushBatch(tenantId: String, batch: List<ClientOperationEntity>): PushSummary {
        val ops = db().clientOperationDao()
        val operations = batch.map { op ->
            val deps = (ops.dependenciesOf(op.id) + listOfNotNull(op.dependsOn)).distinct()
            OperationIn(op.id, op.opType, IsoTime.format(op.createdAtDevice), deps, json.parseToJsonElement(op.payloadJson).jsonObject)
        }
        val now = clock.nowMs()
        batch.forEach { ops.markSent(it.id, now) }
        val response = try {
            api.push(tenantId, PushIn(IsoTime.format(now), operations))
        } catch (e: Throwable) {
            batch.forEach { ops.returnToPending(it.id, TRANSPORT, e.javaClass.simpleName) }
            throw e
        }
        val receivedElapsed = clock.elapsedRealtimeMs()
        return applyResults(tenantId, batch, response, receivedElapsed)
    }

    private suspend fun applyResults(
        tenantId: String,
        batch: List<ClientOperationEntity>,
        response: PushResultDto,
        receivedElapsed: Long,
    ): PushSummary {
        val database = db()
        return database.inTransaction {
            val ops = database.clientOperationDao()
            val byId = response.results.associateBy { it.id }
            var acked = 0
            var deferred = 0
            var problems = 0
            batch.forEach { op ->
                val result = byId[op.id]
                if (result == null) { // no outcome for this op: keep it and resend later
                    ops.returnToPending(op.id, "NO_RESULT", null)
                    deferred++
                    return@forEach
                }
                when (apply(op.id, result)) {
                    PushOutcome.ACKED, PushOutcome.DUPLICATE -> acked++
                    PushOutcome.DEFERRED, PushOutcome.TRANSPORT_FAILURE -> deferred++
                    else -> problems++
                }
            }
            val states = database.syncStateDao()
            val state = states.get(tenantId) ?: SyncStateEntity(tenantId)
            states.put(
                state.copy(
                    serverTime = IsoTime.parse(response.serverTime).toEpochMilli(),
                    serverTimeElapsed = receivedElapsed,
                    clockOffsetS = response.clockOffsetS,
                    serverClockAlert = response.clockSkewAlert,
                ),
            )
            PushSummary(batch.size, acked, deferred, problems)
        }
    }

    private suspend fun apply(id: String, result: OperationResultDto): PushOutcome {
        val ops = db().clientOperationDao()
        val error = result.error ?: result.result["error"] as? JsonObject
        val code = error?.get("code")?.jsonPrimitive?.contentOrNull
        val message = error?.get("message")?.jsonPrimitive?.contentOrNull
        val serverState = result.result["server_state"] as? JsonObject
        val outcome = OutboxTransitions.outcomeOf(result.status, code, !serverState.isNullOrEmpty())
        val resultJson = json.encodeToString(result.result)
        when (OutboxTransitions.next(ClientOperationStatus.SENT, outcome)) {
            ClientOperationStatus.ACKED -> ops.ackWithResult(id, resultJson, revisionOf(result.result))
            ClientOperationStatus.PENDING -> ops.returnToPending(id, code ?: result.status, message)
            ClientOperationStatus.CONFLICT -> ops.markConflict(id, code, message, resultJson)
            ClientOperationStatus.FAILED -> ops.markRejected(id, code, message, resultJson)
            ClientOperationStatus.QUARANTINED -> ops.markQuarantined(id, code, message, resultJson)
            else -> ops.returnToPending(id, code ?: result.status, message)
        }
        return outcome
    }

    /** The applied entity's server version, when the result carries one (job/transition results do). */
    private fun revisionOf(result: JsonObject): Long? =
        (result["entity"] as? JsonObject)?.let { (it["sync_revision"] ?: it["version"])?.jsonPrimitive?.longOrNull }

    private companion object {
        const val MAX_ROUNDS = 50
        const val MAX_BATCH = 100
        const val TRANSPORT = "TRANSPORT"
    }
}
