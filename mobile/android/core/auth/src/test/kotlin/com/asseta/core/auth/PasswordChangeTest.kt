package com.asseta.core.auth

import android.net.Uri
import net.openid.appauth.AuthorizationException
import net.openid.appauth.AuthorizationRequest
import net.openid.appauth.AuthorizationResponse
import net.openid.appauth.AuthorizationServiceConfiguration
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** Keycloak `kc_action=UPDATE_PASSWORD`: the sign-in request plus one parameter, and the callback status mapping. */
@RunWith(RobolectricTestRunner::class)
class PasswordChangeTest {
    private val config = AuthConfig("https://id.example.com/realms/asseta", "asseta-mobile", "com.asseta.owner", false)
    private val serviceConfig = AuthorizationServiceConfiguration(
        Uri.parse("https://id.example.com/realms/asseta/protocol/openid-connect/auth"),
        Uri.parse("https://id.example.com/realms/asseta/protocol/openid-connect/token"),
    )

    private fun callback(request: AuthorizationRequest, query: String): AuthorizationResponse =
        AuthorizationResponse.Builder(request)
            .fromUri(Uri.parse("${config.redirectUri}?state=${request.state}&$query"))
            .build()

    @Test
    fun `change password request adds kc_action and keeps the sign-in parameters`() {
        val login = PasswordChange.authorizationRequest(serviceConfig, config)
        val change = PasswordChange.authorizationRequest(serviceConfig, config, PasswordChange.UPDATE_PASSWORD)

        assertEquals(mapOf("kc_action" to "UPDATE_PASSWORD"), change.additionalParameters)
        assertFalse(login.additionalParameters.containsKey("kc_action"))
        assertEquals("UPDATE_PASSWORD", change.toUri().getQueryParameter("kc_action"))
        for (request in listOf(login, change)) {
            assertEquals("asseta-mobile", request.clientId)
            assertEquals("code", request.responseType)
            assertEquals("com.asseta.owner:/oauth2redirect", request.redirectUri.toString())
            assertEquals(setOf("openid", "profile", "email"), request.scopeSet)
            assertEquals("S256", request.codeVerifierChallengeMethod)
            assertNotNull(request.codeVerifier)
            assertNotNull(request.nonce)
        }
        assertEquals("S256", change.toUri().getQueryParameter("code_challenge_method"))
        assertEquals(change.codeVerifierChallenge, change.toUri().getQueryParameter("code_challenge"))
    }

    @Test
    fun `callback status maps to the result`() {
        val request = PasswordChange.authorizationRequest(serviceConfig, config, PasswordChange.UPDATE_PASSWORD)
        assertEquals(
            PasswordChangeResult.Changed,
            PasswordChange.resultFor(callback(request, "code=abc&kc_action_status=success"), null),
        )
        assertEquals(
            PasswordChangeResult.Cancelled,
            PasswordChange.resultFor(callback(request, "code=abc&kc_action_status=cancelled"), null),
        )
        assertEquals(
            PasswordChangeResult.Failed(PasswordChange.FAILED_MESSAGE),
            PasswordChange.resultFor(callback(request, "code=abc&kc_action_status=error"), null),
        )
        // A code without any action status means Keycloak did not confirm the change.
        assertEquals(
            PasswordChangeResult.Failed(PasswordChange.FAILED_MESSAGE),
            PasswordChange.resultFor(callback(request, "code=abc"), null),
        )
    }

    @Test
    fun `closed browser is a cancel and an error redirect is a failure`() {
        assertEquals(
            PasswordChangeResult.Cancelled,
            PasswordChange.resultFor(null, AuthorizationException.GeneralErrors.USER_CANCELED_AUTH_FLOW),
        )
        assertEquals(PasswordChangeResult.Cancelled, PasswordChange.resultFor(null, null))
        assertEquals(
            PasswordChangeResult.Failed(PasswordChange.FAILED_MESSAGE),
            PasswordChange.resultFor(null, AuthorizationException.AuthorizationRequestErrors.ACCESS_DENIED),
        )
        assertEquals(
            PasswordChangeResult.Failed(PasswordChange.FAILED_MESSAGE),
            PasswordChange.resultFor(null, AuthorizationException.GeneralErrors.NETWORK_ERROR),
        )
    }
}
