package com.asseta.core.domain.sync

import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.ClientOperationStatus.FAILED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.ClientOperationStatus.QUARANTINED
import com.asseta.core.model.ClientOperationStatus.SENT
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncRulesTest {
    @Test
    fun everyPushOutcomeFromSent() {
        val expected = mapOf(
            PushOutcome.ACKED to ACKED, PushOutcome.DUPLICATE to ACKED, PushOutcome.DEFERRED to PENDING,
            PushOutcome.CONFLICT to CONFLICT, PushOutcome.REJECTED to FAILED, PushOutcome.QUARANTINED to QUARANTINED,
            PushOutcome.TRANSPORT_FAILURE to PENDING,
        )
        PushOutcome.entries.forEach { assertEquals(it.name, expected[it], OutboxTransitions.next(SENT, it)) }
    }

    @Test
    fun outcomesOnlyApplyToSentOperations() {
        ClientOperationStatus.entries.filter { it != SENT }.forEach { status ->
            PushOutcome.entries.forEach { assertNull("$status/$it", OutboxTransitions.next(status, it)) }
        }
        assertTrue(OutboxTransitions.canSend(PENDING))
        assertTrue(OutboxTransitions.canSend(QUARANTINED))
        listOf(SENT, ACKED, FAILED, CONFLICT).forEach { assertFalse(OutboxTransitions.canSend(it)) }
    }

    @Test
    fun wireStatusesMapToOutcomes() {
        assertEquals(PushOutcome.ACKED, OutboxTransitions.outcomeOf("ACKED", null, false))
        assertEquals(PushOutcome.DUPLICATE, OutboxTransitions.outcomeOf("DUPLICATE", null, false))
        assertEquals(PushOutcome.QUARANTINED, OutboxTransitions.outcomeOf("DUPLICATE", "SUBSCRIPTION_READ_ONLY", false))
        assertEquals(PushOutcome.CONFLICT, OutboxTransitions.outcomeOf("DUPLICATE", "INVALID_JOB_TRANSITION", true))
        assertEquals(PushOutcome.REJECTED, OutboxTransitions.outcomeOf("DUPLICATE", "VALIDATION_FAILED", false))
        assertEquals(PushOutcome.DEFERRED, OutboxTransitions.outcomeOf("DEFERRED", "DEPENDENCY_PENDING", false))
        assertEquals(PushOutcome.CONFLICT, OutboxTransitions.outcomeOf("CONFLICT", "MACHINE_BUSY", true))
        assertEquals(PushOutcome.REJECTED, OutboxTransitions.outcomeOf("REJECTED", "PERMISSION_DENIED", false))
        assertEquals(PushOutcome.QUARANTINED, OutboxTransitions.outcomeOf("QUARANTINED", "SUBSCRIPTION_READ_ONLY", false))
        assertEquals(PushOutcome.DEFERRED, OutboxTransitions.outcomeOf("SOMETHING_NEW", null, false))
    }

    @Test
    fun backoffIsExponentialBoundedAndJittered() {
        val b = Backoff(baseMs = 1_000, maxMs = 60_000)
        assertEquals(0L, b.delayFor(0, 0.5))
        assertEquals(1_000L, b.capFor(1))
        assertEquals(8_000L, b.capFor(4))
        assertEquals(60_000L, b.capFor(20))
        assertEquals(60_000L, b.capFor(1_000))
        assertEquals(4_000L, b.delayFor(4, 0.0))
        assertEquals(8_000L, b.delayFor(4, 1.0))
        val d = b.delayFor(4, 0.37)
        assertTrue(d in 4_000L..8_000L)
    }

    @Test
    fun clockTamperDetection() {
        val anchor = ClockAnchor(serverEpochMs = 1_000_000_000L, elapsedRealtimeMs = 50_000L)
        // 10 minutes elapsed monotonic, wall clock matches.
        assertEquals(ClockStatus.Checked(0, false), ClockCheck.evaluate(anchor, 1_000_600_000L, 650_000L))
        // Wall clock set 1 hour ahead.
        assertEquals(ClockStatus.Checked(3600, true), ClockCheck.evaluate(anchor, 1_004_200_000L, 650_000L))
        // Set 6 minutes back -> alert; 4 minutes -> within 300 s tolerance.
        assertTrue((ClockCheck.evaluate(anchor, 1_000_240_000L, 650_000L) as ClockStatus.Checked).alert)
        assertFalse((ClockCheck.evaluate(anchor, 1_000_360_000L, 650_000L) as ClockStatus.Checked).alert)
        assertEquals(ClockStatus.Unknown, ClockCheck.evaluate(null, 0, 0))
        assertEquals(ClockStatus.Unknown, ClockCheck.evaluate(anchor, 1_000_000_000L, 10_000L)) // rebooted
    }

    @Test
    fun jobDependencyChain() {
        fun op(id: String, kind: JobOpKind, t: Long, s: ClientOperationStatus = PENDING) = LocalJobOp(id, kind, s, t)
        val P = JobOperationPlanner
        assertEquals(emptyList<String>(), P.dependenciesFor(JobOpKind.OPENING_CAPTURE, emptyList()))
        val ops = mutableListOf(op("open1", JobOpKind.OPENING_CAPTURE, 1, CONFLICT), op("open2", JobOpKind.OPENING_CAPTURE, 2))
        assertEquals(listOf("open2"), P.dependenciesFor(JobOpKind.START, ops)) // rejected/conflicted capture is not a parent
        ops += op("start", JobOpKind.START, 3)
        assertEquals(listOf("start"), P.dependenciesFor(JobOpKind.ACTIVITY, ops))
        assertEquals(listOf("start"), P.dependenciesFor(JobOpKind.CLOSING_CAPTURE, ops))
        ops += op("act1", JobOpKind.ACTIVITY, 4)
        ops += op("act2", JobOpKind.ACTIVITY, 5, ACKED)
        ops += op("close", JobOpKind.CLOSING_CAPTURE, 6)
        assertEquals(listOf("close"), P.dependenciesFor(JobOpKind.ACKNOWLEDGEMENT, ops))
        ops += op("ack", JobOpKind.ACKNOWLEDGEMENT, 7)
        assertEquals(listOf("close", "ack", "act1"), P.dependenciesFor(JobOpKind.COMPLETE, ops))
        val many = ops + (1..40).map { op("a$it", JobOpKind.ACTIVITY, 100L + it) }
        assertEquals(JobOperationPlanner.MAX_DEPENDENCIES, P.dependenciesFor(JobOpKind.COMPLETE, many).size)
        assertTrue(P.hasLive(JobOpKind.START, ops))
        assertFalse(P.hasLive(JobOpKind.COMPLETE, ops))
    }
}
