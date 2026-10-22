package com.asseta.core.domain.owner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FreshnessTest {
    private val now = 1_000_000_000L

    @Test
    fun `live only when server says live in a fresh live response`() {
        assertEquals(Connectivity.LIVE, Freshness.displayConnectivity("LIVE", true, DataSource.LIVE, now - 10_000, now))
        assertEquals(Connectivity.RECENT, Freshness.displayConnectivity("LIVE", true, DataSource.CACHE, now - 10_000, now))
        assertEquals(Connectivity.RECENT, Freshness.displayConnectivity("LIVE", true, DataSource.LIVE, now - 5 * 60_000, now))
        assertEquals(Connectivity.RECENT, Freshness.displayConnectivity("LIVE", false, DataSource.LIVE, now, now))
    }

    @Test
    fun `non live values pass through and unknown fails safe`() {
        assertEquals(Connectivity.OFFLINE, Freshness.displayConnectivity("OFFLINE", false, DataSource.CACHE, now, now))
        assertEquals(Connectivity.UNKNOWN, Freshness.displayConnectivity("SATELLITE", true, DataSource.LIVE, now, now))
    }

    @Test
    fun `age labels`() {
        assertEquals("never", Freshness.ageLabel(null))
        assertEquals("just now", Freshness.ageLabel(30))
        assertEquals("5 min ago", Freshness.ageLabel(300))
        assertEquals("3 h ago", Freshness.ageLabel(3 * 3600 + 5))
        assertEquals("2 d ago", Freshness.ageLabel(2 * 86_400 + 1))
        assertEquals(0L, Freshness.ageSeconds(now + 5000, now))
    }
}

class SnapshotPolicyTest {
    private val policy = SnapshotPolicy()
    private val day = 86_400_000L

    @Test
    fun `seven day bound`() {
        assertFalse(policy.isExpired(0, 7 * day))
        assertTrue(policy.isExpired(0, 7 * day + 1))
        assertEquals(day, policy.purgeBefore(8 * day))
        assertFalse(policy.cacheable(policy.maxPayloadBytes + 1))
    }

    @Test
    fun `only network failures fall back to unexpired cache`() {
        assertEquals(FallbackDecision.UseCache, OfflineFallback.decide(FailureKind.NETWORK, 10, 20, policy))
        assertEquals(FallbackDecision.ShowError, OfflineFallback.decide(FailureKind.NETWORK, null, 20, policy))
        assertEquals(FallbackDecision.ShowError, OfflineFallback.decide(FailureKind.NETWORK, 0, 8 * day, policy))
        assertEquals(FallbackDecision.ShowError, OfflineFallback.decide(FailureKind.SERVER, 10, 20, policy))
    }

    @Test
    fun `classification of refusals`() {
        assertEquals(FailureKind.NETWORK, OfflineFallback.classify(null, null))
        assertEquals(FailureKind.UNAUTHENTICATED, OfflineFallback.classify(401, "NOT_AUTHENTICATED"))
        assertEquals(FailureKind.TENANT_REVOKED, OfflineFallback.classify(403, "TENANT_ACCESS_DENIED"))
        assertEquals(FailureKind.SERVER, OfflineFallback.classify(403, "PERMISSION_DENIED"))
        assertEquals(FallbackDecision.WipeTenant, OfflineFallback.decide(FailureKind.TENANT_REVOKED, 10, 20, policy))
        assertEquals(FallbackDecision.EndSession, OfflineFallback.decide(FailureKind.UNAUTHENTICATED, 10, 20, policy))
    }
}

class MutationGateTest {
    private val perms = setOf("tenant.fleet.alert_manage")

    @Test
    fun `offline or cached data blocks mutations`() {
        assertTrue(MutationGate.check(OwnerAction.ACKNOWLEDGE_ALERT, false, DataSource.LIVE, perms, false) is MutationCheck.Blocked)
        assertTrue(MutationGate.check(OwnerAction.ACKNOWLEDGE_ALERT, true, DataSource.CACHE, perms, false) is MutationCheck.Blocked)
        assertEquals(MutationCheck.Allowed, MutationGate.check(OwnerAction.ACKNOWLEDGE_ALERT, true, DataSource.LIVE, perms, false))
    }

    @Test
    fun `permission and read only tenant block mutations`() {
        val noPerm = MutationGate.check(OwnerAction.DECIDE_APPROVAL, true, DataSource.LIVE, perms, false)
        assertEquals("You do not have permission to do this.", (noPerm as MutationCheck.Blocked).reason)
        assertTrue(MutationGate.check(OwnerAction.RESOLVE_ALERT, true, DataSource.LIVE, perms, true) is MutationCheck.Blocked)
        assertFalse(MutationGate.resolveNoteValid("   "))
    }
}

class OwnerErrorsTest {
    @Test
    fun `segregation of duties is explained and reload codes`() {
        assertTrue(OwnerErrors.message("SEGREGATION_OF_DUTIES", "x").startsWith("Segregation of duties"))
        assertEquals("server text", OwnerErrors.message("SOMETHING_NEW", "server text"))
        assertTrue(OwnerErrors.needsReload("APPROVAL_ALREADY_DECIDED"))
        assertFalse(OwnerErrors.needsReload("SEGREGATION_OF_DUTIES"))
    }
}
