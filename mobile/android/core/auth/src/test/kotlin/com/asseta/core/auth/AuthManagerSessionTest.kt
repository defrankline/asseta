package com.asseta.core.auth

import android.net.Uri
import android.os.Looper
import org.robolectric.RuntimeEnvironment
import com.asseta.core.network.TokenUnavailableException
import com.asseta.core.security.SecretCipher
import com.asseta.core.security.SecretFileStore
import com.asseta.core.security.SecureTokenStore
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import net.openid.appauth.AuthState
import net.openid.appauth.AuthorizationServiceConfiguration
import net.openid.appauth.AuthorizationResponse
import net.openid.appauth.TokenResponse
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf

/**
 * The session against a scripted Keycloak token endpoint: rotated refresh tokens are saved, an authoritative refusal
 * ends the session, and a network failure or server trouble never does.
 */
@RunWith(RobolectricTestRunner::class)
class AuthManagerSessionTest {
    @get:Rule val folder = TemporaryFolder()
    private val server = MockWebServer()
    private lateinit var store: SecureTokenStore

    private object PlainCipher : SecretCipher {
        override fun encrypt(plaintext: ByteArray) = plaintext
        override fun decrypt(ciphertext: ByteArray) = ciphertext
    }

    @Before
    fun setUp() {
        server.start()
        store = SecureTokenStore(SecretFileStore(folder.newFolder("secrets"), PlainCipher))
    }

    @After
    fun tearDown() = server.close()

    /** A signed-in session whose access token has expired, its token endpoint at [tokenEndpoint]. */
    private fun signedIn(tokenEndpoint: Uri = Uri.parse(server.url("/realms/asseta/protocol/openid-connect/token").toString())): AuthManager {
        val serviceConfig = AuthorizationServiceConfiguration(Uri.parse("http://localhost/realms/asseta/auth"), tokenEndpoint)
        val config = AuthConfig("http://localhost/realms/asseta", "asseta-mobile", "com.asseta.supervisor", allowInsecureHttp = true)
        val authRequest = PasswordChange.authorizationRequest(serviceConfig, config)
        val authResponse = AuthorizationResponse.Builder(authRequest).setState(authRequest.state).setAuthorizationCode("code").build()
        val tokens = TokenResponse.Builder(authResponse.createTokenExchangeRequest()).setTokenType("Bearer").setAccessToken("access-1")
            .setAccessTokenExpirationTime(System.currentTimeMillis() - 1_000).setRefreshToken("refresh-1").build()
        val state = AuthState(authResponse, null).apply { update(tokens, null) }
        store.write(state.jsonSerializeString())
        return AuthManager(RuntimeEnvironment.getApplication(), config, store)
    }

    /** Calls [block] off the main thread (as OkHttp does) while the main looper delivers AppAuth's callbacks. */
    private fun <T> offMain(block: () -> T): Result<T> {
        var result: Result<T>? = null
        val worker = Thread { result = runCatching(block) }
        worker.start()
        while (worker.isAlive) {
            shadowOf(Looper.getMainLooper()).idle()
            worker.join(10)
        }
        return result!!
    }

    private fun storedRefreshToken(): String? = store.read()?.let { AuthState.jsonDeserialize(it).refreshToken }

    private fun tokens(n: Int) = MockResponse(
        code = 200,
        body = """{"access_token":"access-$n","token_type":"Bearer","expires_in":300,"refresh_token":"refresh-$n","refresh_expires_in":1209600}""",
        headers = okhttp3.Headers.headersOf("Content-Type", "application/json"),
    )

    private fun error(code: Int, body: String) =
        MockResponse(code = code, body = body, headers = okhttp3.Headers.headersOf("Content-Type", "application/json"))

    @Test
    fun `a refresh saves the rotated refresh token`() {
        val auth = signedIn()
        server.enqueue(tokens(2))
        assertEquals("access-2", offMain { auth.accessToken() }.getOrThrow())
        assertTrue(server.takeRequest().body!!.utf8().contains("refresh_token=refresh-1"))
        assertEquals("refresh-2", storedRefreshToken())
        assertTrue(auth.signedIn.value)
        // The next refresh uses the newest token, never the rotated-out one.
        server.enqueue(tokens(3))
        assertEquals("access-3", offMain { auth.refreshedAccessToken("access-2") }.getOrThrow())
        assertTrue(server.takeRequest().body!!.utf8().contains("refresh_token=refresh-2"))
        assertEquals("refresh-3", storedRefreshToken())
    }

    @Test
    fun `invalid_grant from the token endpoint ends the session`() {
        val auth = signedIn()
        server.enqueue(error(400, """{"error":"invalid_grant","error_description":"Offline session not active"}"""))
        assertNull(offMain { auth.accessToken() }.getOrThrow())
        assertFalse(auth.signedIn.value)
        assertNull(store.read())
    }

    @Test
    fun `no connection keeps the session and its tokens`() {
        val closed = server.url("/realms/asseta/protocol/openid-connect/token").toString()
        server.close()
        val auth = signedIn(Uri.parse(closed))
        val failure = offMain { auth.accessToken() }.exceptionOrNull()
        assertTrue("$failure", failure is TokenUnavailableException)
        assertTrue(auth.signedIn.value)
        assertEquals("refresh-1", storedRefreshToken())
    }

    @Test
    fun `server trouble keeps the session and the next refresh works`() {
        val auth = signedIn()
        server.enqueue(error(503, """{"error":"unknown_error"}"""))
        server.enqueue(MockResponse(code = 502, body = "<html>Bad gateway</html>"))
        server.enqueue(tokens(2))
        assertTrue(offMain { auth.accessToken() }.exceptionOrNull() is TokenUnavailableException)
        assertTrue(auth.signedIn.value)
        assertTrue(offMain { auth.accessToken() }.exceptionOrNull() is TokenUnavailableException)
        assertTrue(auth.signedIn.value)
        assertEquals("refresh-1", storedRefreshToken())
        assertEquals("access-2", offMain { auth.accessToken() }.getOrThrow())
        assertEquals("refresh-2", storedRefreshToken())
    }

    @Test
    fun `a valid token is returned without a refresh`() {
        val auth = signedIn()
        server.enqueue(tokens(2))
        assertEquals("access-2", offMain { auth.accessToken() }.getOrThrow())
        assertEquals("access-2", offMain { auth.accessToken() }.getOrThrow())
        assertEquals(1, server.requestCount)
    }

    @Test
    fun `sign-in asks for an offline token`() {
        assertTrue("offline_access" in AuthConfig.DEFAULT_SCOPES)
    }
}
