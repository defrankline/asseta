package com.asseta.supervisor.ui

import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.sync.data.WaitingReason
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** The wording below is the iOS app's (AssetaField); both apps must show the same text. */
class FieldTextsTest {
    private fun payload(text: String) = Json.parseToJsonElement(text).jsonObject

    @Test
    fun outboxTitlesMatchIos() {
        assertEquals("Cash handover", FieldTexts.outboxTitle(OpTypes.CASH_HANDOVER, null))
        assertEquals("Fuel event", FieldTexts.outboxTitle(OpTypes.FUEL_EVENT, payload("""{"event_type":"ISSUE","litres":"40"}""")))
        assertEquals("JOB_TRANSITION", FieldTexts.outboxTitle("JOB_TRANSITION", null)) // ADR-008: no job items any more
    }

    @Test
    fun syncWording() {
        assertEquals("Held", FieldTexts.syncState(ClientOperationStatus.QUARANTINED))
        assertEquals("Rejected", FieldTexts.syncState(ClientOperationStatus.FAILED))
        assertEquals("Waiting for its photo/receipt upload", FieldTexts.waiting(WaitingReason.UPLOAD))
        assertEquals("You can sign in again at any time.", FieldTexts.signOutMessage(0))
        assertEquals(
            "3 item(s) are not synced yet. They stay encrypted on this phone and sync after you sign in again.",
            FieldTexts.signOutMessage(3),
        )
        assertNull(FieldTexts.lastSyncProblem(null))
        assertEquals("Sync failed: Offline or server unreachable. It will retry automatically.", FieldTexts.lastSyncProblem("NETWORK"))
        assertEquals("Server problem: BAD_SERVER_RESPONSE. It will retry automatically.", FieldTexts.lastSyncProblem("BAD_SERVER_RESPONSE"))
    }

    @Test
    fun clockSkewIsDescribedInMinutesOrHours() {
        assertEquals("10 minutes fast", FieldTexts.describeSkew(600))
        assertEquals("119 minutes slow", FieldTexts.describeSkew(-119 * 60))
        assertEquals("3 hours fast", FieldTexts.describeSkew(3 * 3_600 + 59))
        assertEquals(
            "This phone's clock is 10 minutes fast compared with Asseta's server. Set the date and time to automatic. " +
                "Readings still record the phone's own time.",
            FieldTexts.clockTamper(600),
        )
    }

    @Test
    fun meterPrecisionAndGpsFailures() {
        assertEquals("Whole hours", FieldTexts.meterPrecision(0))
        assertEquals("2 decimal place(s)", FieldTexts.meterPrecision(2))
        assertEquals("No GPS fix within 20 seconds", FieldTexts.gpsFailure(GpsOutcome.Timeout))
        assertEquals("Location services are turned off", FieldTexts.gpsFailure(GpsOutcome.Disabled))
    }
}
