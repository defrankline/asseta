package com.asseta.core.domain.sync

import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.ClientOperationStatus.FAILED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.ClientOperationStatus.QUARANTINED
import com.asseta.core.model.ClientOperationStatus.SENT

/** What happened to one operation of a push (server per-op status, or a transport failure of the whole batch). */
enum class PushOutcome { ACKED, DUPLICATE, DEFERRED, CONFLICT, REJECTED, QUARANTINED, TRANSPORT_FAILURE }

/**
 * The outbox state machine. Only a SENT operation can receive an outcome; everything else is illegal (null).
 * Nothing becomes ACKED without a server ACK/DUPLICATE; DEFERRED and transport failures go back to PENDING.
 */
object OutboxTransitions {
    /** Statuses the dispatcher may (re)send. QUARANTINED ops are resent so they apply after reactivation. */
    val DISPATCHABLE: Set<ClientOperationStatus> = setOf(PENDING, QUARANTINED)

    fun canSend(status: ClientOperationStatus): Boolean = status in DISPATCHABLE

    fun next(current: ClientOperationStatus, outcome: PushOutcome): ClientOperationStatus? {
        if (current != SENT) return null
        return when (outcome) {
            PushOutcome.ACKED, PushOutcome.DUPLICATE -> ACKED
            PushOutcome.DEFERRED, PushOutcome.TRANSPORT_FAILURE -> PENDING
            PushOutcome.CONFLICT -> CONFLICT
            PushOutcome.REJECTED -> FAILED
            PushOutcome.QUARANTINED -> QUARANTINED
        }
    }

    /**
     * Maps a server result to an outcome. A DUPLICATE replays the *stored* outcome: with no error it was applied
     * (ACKED); with `SUBSCRIPTION_READ_ONLY` it is still quarantined; with `server_state` it was a conflict; any other
     * stored error was a rejection. Treating those as ACKED would hide failures and stall dependants forever.
     */
    fun outcomeOf(wireStatus: String, errorCode: String?, hasServerState: Boolean): PushOutcome = when (wireStatus) {
        "ACKED" -> PushOutcome.ACKED
        "DEFERRED" -> PushOutcome.DEFERRED
        "CONFLICT" -> PushOutcome.CONFLICT
        "REJECTED" -> PushOutcome.REJECTED
        "QUARANTINED" -> PushOutcome.QUARANTINED
        "DUPLICATE" -> when {
            errorCode == null -> PushOutcome.DUPLICATE
            errorCode == SUBSCRIPTION_READ_ONLY -> PushOutcome.QUARANTINED
            hasServerState -> PushOutcome.CONFLICT
            else -> PushOutcome.REJECTED
        }
        else -> PushOutcome.DEFERRED // unknown future status: keep the op and retry, never drop or ack it
    }

    const val SUBSCRIPTION_READ_ONLY = "SUBSCRIPTION_READ_ONLY"
}
