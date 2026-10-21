package com.asseta.core.ui

import com.asseta.core.model.MeResponse
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.TenantAccessState
import com.asseta.core.network.ApiException
import com.asseta.core.ui.session.SessionRules
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.IOException
import java.util.UUID

class SessionRulesTest {
    private fun tenant(state: TenantAccessState) = TenantAccess(UUID.randomUUID(), "T", "ACTIVE", state)
    private fun me(vararg tenants: TenantAccess) = MeResponse(UUID.randomUUID(), "e", "d", tenants = tenants.toList())

    @Test
    fun `keeps previous selection only while still enterable`() {
        val a = tenant(TenantAccessState.FULL)
        val b = tenant(TenantAccessState.READ_ONLY)
        assertEquals(b.tenantId.toString(), SessionRules.resolveSelection(me(a, b), b.tenantId.toString()))
        val blocked = b.copy(accessState = TenantAccessState.BLOCKED)
        assertEquals(a.tenantId.toString(), SessionRules.resolveSelection(me(a, blocked), b.tenantId.toString()))
    }

    @Test
    fun `no auto selection when ambiguous or nothing enterable`() {
        assertNull(SessionRules.resolveSelection(me(tenant(TenantAccessState.FULL), tenant(TenantAccessState.FULL)), null))
        assertNull(SessionRules.resolveSelection(me(tenant(TenantAccessState.BLOCKED), tenant(TenantAccessState.UNKNOWN)), null))
    }

    @Test
    fun `error mapping keeps server reference`() {
        val api = SessionRules.toUiError(ApiException(403, "PERMISSION_DENIED", "No access", "cid"))
        assertEquals("No access", api.message)
        assertEquals("cid", api.reference)
        assertNull(SessionRules.toUiError(IOException("x")).reference)
    }
}
