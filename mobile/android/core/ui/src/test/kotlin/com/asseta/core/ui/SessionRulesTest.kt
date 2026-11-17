package com.asseta.core.ui

import com.asseta.core.auth.PasswordChange
import com.asseta.core.auth.PasswordChangeResult
import com.asseta.core.model.MeResponse
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.TenantAccessState
import com.asseta.core.network.ApiException
import com.asseta.core.ui.session.PasswordChangeState
import com.asseta.core.ui.session.PasswordChangeText
import com.asseta.core.ui.session.SessionRules
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
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

    @Test
    fun `password change success confirms, cancel shows nothing, failure explains`() {
        assertEquals(PasswordChangeState.Changed, SessionRules.passwordChangeState(PasswordChangeResult.Changed))
        assertEquals(PasswordChangeState.Idle, SessionRules.passwordChangeState(PasswordChangeResult.Cancelled))
        assertEquals(
            PasswordChangeState.Failed(PasswordChange.FAILED_MESSAGE),
            SessionRules.passwordChangeState(PasswordChangeResult.Failed(PasswordChange.FAILED_MESSAGE)),
        )
        assertEquals("Password changed.", PasswordChangeText.CHANGED)
    }

    @Test
    fun `only a refusal by the sign-in server ends the session`() {
        val unauthorized = ApiException(401, "NOT_AUTHENTICATED", "no", "cid")
        // The token endpoint refused the refresh token: the auth layer holds no session any more.
        assertTrue(SessionRules.endsSession(unauthorized, stillSignedIn = false))
        // A 401 the session survived (refreshed and retried) keeps it.
        assertFalse(SessionRules.endsSession(unauthorized, stillSignedIn = true))
        // Network failures and server trouble never end it.
        assertFalse(SessionRules.endsSession(IOException("timeout"), stillSignedIn = true))
        assertFalse(SessionRules.endsSession(com.asseta.core.network.TokenUnavailableException("offline"), stillSignedIn = true))
        assertFalse(SessionRules.endsSession(ApiException(503, "HTTP_503", "down", null), stillSignedIn = true))
        assertFalse(SessionRules.endsSession(ApiException(502, "HTTP_502", "bad gateway", null), stillSignedIn = false))
    }
}
