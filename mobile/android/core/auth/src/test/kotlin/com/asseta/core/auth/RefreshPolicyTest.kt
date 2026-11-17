package com.asseta.core.auth

import net.openid.appauth.AuthorizationException
import org.junit.Assert.assertEquals
import org.junit.Test

/** Only the token endpoint's refusal ends a session; anything else is tried again later. */
class RefreshPolicyTest {
    private val oauth = AuthorizationException.TYPE_OAUTH_TOKEN_ERROR
    private val general = AuthorizationException.TYPE_GENERAL_ERROR

    @Test
    fun `no error keeps going`() = assertEquals(RefreshOutcome.OK, RefreshPolicy.classify(null, null))

    @Test
    fun `a refusal by the token endpoint ends the session`() {
        for (code in listOf("invalid_grant", "invalid_client", "unauthorized_client", "invalid_request", "invalid_scope")) {
            assertEquals(code, RefreshOutcome.SESSION_ENDED, RefreshPolicy.classify(oauth, code))
        }
    }

    @Test
    fun `network failures and server trouble keep the session`() {
        // AppAuth's general errors: no connection, timeout, DNS, unreadable body (proxy or captive-portal page).
        assertEquals(RefreshOutcome.TRY_LATER, RefreshPolicy.classify(general, null))
        assertEquals(RefreshOutcome.TRY_LATER, RefreshPolicy.classify(general, "invalid_grant"))
        // A failing Keycloak answering 5xx with an OAuth body.
        for (code in listOf("server_error", "temporarily_unavailable", "unknown_error", "", null)) {
            assertEquals(code, RefreshOutcome.TRY_LATER, RefreshPolicy.classify(oauth, code))
        }
    }
}
