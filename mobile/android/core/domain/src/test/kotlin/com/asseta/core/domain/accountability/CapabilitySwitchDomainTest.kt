package com.asseta.core.domain.accountability

import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.SyncCapabilities
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Follow-up F1: ENGINE_HOURS and CASH_CUSTODY switched off in `/me` hide their Supervisor entry points. */
class CapabilitySwitchDomainTest {
    private val caps = setOf(
        SyncCapabilities.OP_CASH_TRANSFER, SyncCapabilities.OP_CASH_RETENTION_REQUEST, SyncCapabilities.METER_DAILY_READING,
        SyncCapabilities.OP_METER_BASELINE, SyncCapabilities.OP_METER_CORRECTION,
    )
    private val perms = setOf(FieldAccess.COLLECTION_RECORD, FieldAccess.METER_CAPTURE)
    private val cash = CashCustodyPolicy.fromValues(
        buildJsonObject {
            listOf(
                "recorders_may_record_for_others", "transfer_ack_required", "recorder_receiver_counts_as_ack", "float_ack_required",
                "remit_full_balance", "retention_allowed",
            ).forEach { put(it, JsonPrimitive(true)) }
        },
    )
    private val on = FieldAccess(caps, perms, cash = cash)

    @Test
    fun `everything shows while no switch is off`() {
        assertTrue(on.transferCash && on.acknowledgeCash && on.recordForOthers && on.askToKeepCash && on.retentionOffline)
        assertTrue(on.dailyReading && on.proposeBaseline && on.proposeCorrection)
    }

    @Test
    fun `engine hours off hides daily reading, baseline and correction only`() {
        val off = on.copy(disabled = setOf(TenantAccess.ENGINE_HOURS))
        assertFalse(off.engineHours)
        assertFalse(off.dailyReading)
        assertFalse(off.proposeBaseline)
        assertFalse(off.proposeCorrection)
        assertTrue(off.transferCash && off.askToKeepCash && off.recordForOthers)
    }

    @Test
    fun `cash custody off hides transfer, acknowledgement, keep cash and recording for others only`() {
        val off = on.copy(disabled = setOf(TenantAccess.CASH_CUSTODY))
        assertFalse(off.cashCustody)
        assertFalse(off.transferCash)
        assertFalse(off.acknowledgeCash)
        assertFalse(off.recordForOthers)
        assertFalse(off.askToKeepCash)
        assertFalse(off.retentionOffline)
        assertTrue(off.dailyReading && off.proposeBaseline && off.proposeCorrection)
    }
}
