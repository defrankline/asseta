package com.asseta.core.domain.policy

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class PolicySelectorTest {
    private val now = Instant.parse("2026-10-21T10:00:00Z")
    private val grant = now.plusSeconds(3600)

    private fun values(opening: String = "AUTOMATIC") = Json.parseToJsonElement(
        """{"opening_mode":"$opening","closing_mode":"MANUAL","manual_photo_required":true,"min_ocr_confidence":0.85,
           "max_recapture_attempts":2,"manual_correction_requires_review":true,"gps_enforcement":"SOFT",
           "gps_max_accuracy_m":50.0,"gps_max_age_seconds":120}""",
    ).jsonObject

    private fun snap(scope: String, valid: Instant = now.plusSeconds(60), v: JsonObject = values(), ids: List<String> = listOf(scope)) =
        PolicySnapshot("METER_CAPTURE", scope, ids, "stamp", v, valid)

    @Test
    fun machineSnapshotWinsOverTenant() {
        val d = PolicySelector.select(listOf(snap("tenant"), snap("machine:m1", v = values("MANUAL"))), "m1", now, grant)
        d as CapturePolicyDecision.Allowed
        assertEquals("machine:m1", d.snapshot.scopeKey)
        assertEquals(CaptureMode.MANUAL, d.policy.openingMode)
        assertEquals(listOf("machine:m1"), d.snapshot.versionIds)
    }

    @Test
    fun tenantSnapshotIsTheFallback() {
        val d = PolicySelector.select(listOf(snap("tenant"), snap("machine:other")), "m1", now, grant)
        assertEquals("tenant", (d as CapturePolicyDecision.Allowed).snapshot.scopeKey)
        assertEquals(CaptureMode.AUTOMATIC, d.policy.requiredMode(ReadingKind.OPENING))
        assertEquals(CaptureMode.MANUAL, d.policy.requiredMode(ReadingKind.CLOSING))
    }

    @Test
    fun expiredSnapshotBlocks() {
        val d = PolicySelector.select(listOf(snap("tenant", valid = now.minusSeconds(1))), "m1", now, grant)
        assertEquals(CapturePolicyDecision.Blocked(BlockReason.SNAPSHOT_EXPIRED), d)
        assertTrue((d as CapturePolicyDecision.Blocked).message.startsWith("Connect to refresh rules"))
        // Exactly at valid_until is still allowed (now > valid_until blocks).
        assertTrue(PolicySelector.select(listOf(snap("tenant", valid = now)), "m1", now, grant) is CapturePolicyDecision.Allowed)
    }

    @Test
    fun offlineGrantBoundsOfflineOperation() {
        assertEquals(
            CapturePolicyDecision.Blocked(BlockReason.OFFLINE_GRANT_EXPIRED),
            PolicySelector.select(listOf(snap("tenant")), "m1", now, now.minusSeconds(1)),
        )
        assertEquals(
            CapturePolicyDecision.Blocked(BlockReason.OFFLINE_GRANT_EXPIRED),
            PolicySelector.select(listOf(snap("tenant")), "m1", now, null),
        )
    }

    @Test
    fun missingOrUnreadableSnapshotBlocks() {
        assertEquals(CapturePolicyDecision.Blocked(BlockReason.NO_SNAPSHOT), PolicySelector.select(emptyList(), "m1", now, grant))
        val other = PolicySnapshot("TRACKING", "tenant", emptyList(), "s", values(), now.plusSeconds(60))
        assertEquals(CapturePolicyDecision.Blocked(BlockReason.NO_SNAPSHOT), PolicySelector.select(listOf(other), "m1", now, grant))
        val broken = snap("tenant", v = JsonObject(values().filterKeys { it != "closing_mode" }))
        assertEquals(CapturePolicyDecision.Blocked(BlockReason.POLICY_UNREADABLE), PolicySelector.select(listOf(broken), "m1", now, grant))
    }
}
