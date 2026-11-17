package com.asseta.core.auth

import android.content.Context
import android.content.Intent
import androidx.core.net.toUri
import android.os.Looper
import com.asseta.core.model.SyncAccount
import com.asseta.core.network.AccessTokenProvider
import com.asseta.core.network.TokenUnavailableException
import com.asseta.core.security.SecureTokenStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.suspendCancellableCoroutine
import net.openid.appauth.AppAuthConfiguration
import net.openid.appauth.AuthState
import net.openid.appauth.AuthorizationException
import net.openid.appauth.AuthorizationResponse
import net.openid.appauth.AuthorizationService
import net.openid.appauth.AuthorizationServiceConfiguration
import net.openid.appauth.EndSessionRequest
import java.net.URLEncoder
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Raised when login/refresh fails; [reason] is user-presentable, details stay in [cause]. */
class AuthFailure(val reason: String, cause: Throwable? = null) : Exception(reason, cause)

/**
 * OIDC Authorization Code + PKCE against Keycloak via AppAuth (system browser / Custom Tabs, no WebView).
 * The serialized [AuthState] is persisted only through the Keystore-encrypted [SecureTokenStore].
 *
 * The app asks for `offline_access`, so it holds an offline refresh token that outlives the 30-minute browser session
 * (Keycloak's offline idle timeout, 14 days, matches the DEVICE_SYNC offline grant). Keycloak rotates refresh tokens
 * (`revokeRefreshToken`): every refresh result is saved as one atomic file write, by the persistence thread, whether or
 * not the caller is still waiting. Only the token endpoint's refusal ([RefreshPolicy]) ends the session.
 */
class AuthManager(
    context: Context,
    private val config: AuthConfig,
    private val tokenStore: SecureTokenStore,
) : AccessTokenProvider {

    private val connectionBuilder = HttpConnectionBuilder(config.allowInsecureHttp)
    private val service = AuthorizationService(
        context.applicationContext,
        AppAuthConfiguration.Builder().setConnectionBuilder(connectionBuilder)
            .setSkipIssuerHttpsCheck(config.allowInsecureHttp) // local Keycloak issuer is http (debug only)
            .build(),
    )
    private val lock = Any()
    private val writeLock = Any()
    private var state: AuthState = restore()
    private val _signedIn = MutableStateFlow(state.isAuthorized)

    /** Saves refresh results in order (newest last), off the main thread. */
    private val background: ExecutorService = Executors.newSingleThreadExecutor { r ->
        Thread(r, "asseta-auth").apply { isDaemon = true }
    }

    /** True while a refreshable session exists. Server responses (401/403) remain authoritative. */
    val signedIn: StateFlow<Boolean> = _signedIn.asStateFlow()

    /**
     * The signed-in user (ID token `sub`, falling back to the access token), or null when signed out. Identifies the
     * owner of this phone's local field data; never used for authorization.
     */
    fun account(): SyncAccount? {
        val current = synchronized(lock) { state }
        if (!current.isAuthorized) return null
        return AccountClaims.fromJwt(current.idToken) ?: AccountClaims.fromJwt(current.accessToken)
    }

    private fun restore(): AuthState =
        tokenStore.read()?.let { runCatching { AuthState.jsonDeserialize(it) }.getOrNull() } ?: AuthState()

    /**
     * Makes [newState] the session and saves it (one atomic file replace), unless [onlyIf] is given and another sign-in
     * or sign-out replaced that session meanwhile. Writes are serialized by [writeLock] so the file always ends with the
     * newest state; [lock] is held only for the in-memory swap, so readers ([account]) never wait on disk or Keystore.
     */
    private fun persist(newState: AuthState, onlyIf: AuthState? = null): Boolean = synchronized(writeLock) {
        synchronized(lock) {
            if (onlyIf != null && state !== onlyIf) return false
            state = newState
            _signedIn.value = newState.isAuthorized
        }
        if (newState.isAuthorized) tokenStore.write(newState.jsonSerializeString()) else tokenStore.clear()
        true
    }

    private suspend fun discover(): AuthorizationServiceConfiguration = suspendCancellableCoroutine { cont ->
        AuthorizationServiceConfiguration.fetchFromIssuer(config.issuer.toUri(), { cfg, ex ->
            when {
                cfg != null -> cont.resume(cfg)
                else -> cont.resumeWithException(AuthFailure("Cannot reach the sign-in server", ex))
            }
        }, connectionBuilder)
    }

    /** Builds the browser intent for login (PKCE challenge and state/nonce are generated by AppAuth). */
    suspend fun createLoginIntent(): Intent =
        service.getAuthorizationRequestIntent(PasswordChange.authorizationRequest(discover(), config))

    /**
     * Builds the browser intent for "Change password": the sign-in request plus `kc_action=UPDATE_PASSWORD`, so the
     * password is only ever entered on Keycloak's own page.
     */
    suspend fun createChangePasswordIntent(): Intent = service.getAuthorizationRequestIntent(
        PasswordChange.authorizationRequest(discover(), config, PasswordChange.UPDATE_PASSWORD),
    )

    /** Completes login from the activity result: validates the response and exchanges the code for tokens. */
    suspend fun completeLogin(result: Intent?) {
        if (result == null) throw AuthFailure("Sign-in was cancelled")
        val response = AuthorizationResponse.fromIntent(result)
        val error = AuthorizationException.fromIntent(result)
        if (response == null) throw AuthFailure(error?.errorDescription ?: "Sign-in was cancelled", error)
        exchange(response, error)
    }

    /**
     * Completes "Change password" from the activity result. A returned code is exchanged and replaces the stored
     * tokens exactly like sign-in; the result comes from Keycloak's `kc_action_status`. The current session is kept
     * whatever the outcome. Throws [AuthFailure] when the code exchange fails.
     */
    suspend fun completeChangePassword(result: Intent?): PasswordChangeResult {
        if (result == null) return PasswordChangeResult.Cancelled
        val response = AuthorizationResponse.fromIntent(result)
        val error = AuthorizationException.fromIntent(result)
        if (response?.authorizationCode != null) exchange(response, error)
        return PasswordChange.resultFor(response, error)
    }

    /** Exchanges the authorization code (AppAuth validates the ID token) and persists the new tokens. */
    private suspend fun exchange(response: AuthorizationResponse, error: AuthorizationException?) {
        val newState = AuthState(response, error)
        suspendCancellableCoroutine { cont ->
            service.performTokenRequest(response.createTokenExchangeRequest()) { tokens, ex ->
                newState.update(tokens, ex)
                if (tokens != null) cont.resume(Unit) else cont.resumeWithException(AuthFailure("Token exchange failed", ex))
            }
        }
        persist(newState)
    }

    /**
     * Returns a fresh access token, refreshing with the refresh token when expired; null when signed out (or the
     * sign-in server just refused the session). Throws [TokenUnavailableException] when the session is kept but no token
     * can be had now (offline, timeout, server trouble). Blocks the calling thread: OkHttp threads only, never main.
     */
    override fun accessToken(): String? = freshToken(rejected = null)

    /** The API refused [rejected] (401): a token refreshed since, or a forced refresh now (same rules as [accessToken]). */
    override fun refreshedAccessToken(rejected: String): String? = freshToken(rejected)

    private fun freshToken(rejected: String?): String? {
        check(Looper.myLooper() != Looper.getMainLooper()) { "accessToken() must not be called on the main thread" }
        val current = synchronized(lock) { state }
        if (!current.isAuthorized) return null
        if (rejected != null) {
            // Another call may have refreshed since `rejected` was handed out.
            current.accessToken?.takeIf { it != rejected }?.let { return it }
            current.needsTokenRefresh = true
        }
        if (current.needsTokenRefresh && current.refreshToken == null) {
            // Nothing to refresh with: the session cannot continue (a server always issues one; kept for safety).
            persist(AuthState(), onlyIf = current)
            return null
        }
        val before = current.lastTokenResponse
        val latch = CountDownLatch(1)
        var token: String? = null
        var failure: AuthorizationException? = null
        // AppAuth coalesces concurrent refreshes on one AuthState, so a rotated refresh token is never sent twice.
        current.performActionWithFreshTokens(service) { accessToken, _, ex ->
            val finish = {
                settle(current, refreshed = current.lastTokenResponse !== before, ex)
                token = accessToken
                failure = ex
                latch.countDown()
            }
            // A refresh result is saved on the persistence thread (AppAuth answers it on the main thread), even if this
            // caller stops waiting: a rotated refresh token must never be lost.
            if (ex == null && current.lastTokenResponse === before) finish() else background.execute(finish)
        }
        if (!latch.await(REFRESH_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
            throw TokenUnavailableException("The sign-in server did not answer in time")
        }
        return when (RefreshPolicy.classify(failure)) {
            RefreshOutcome.OK -> token
            RefreshOutcome.SESSION_ENDED -> null
            RefreshOutcome.TRY_LATER -> throw TokenUnavailableException("Cannot refresh the session now", failure)
        }
    }

    /** Applies a refresh result to the stored session, unless another sign-in or a sign-out replaced it meanwhile. */
    private fun settle(current: AuthState, refreshed: Boolean, ex: AuthorizationException?) {
        when (RefreshPolicy.classify(ex)) {
            // New (rotated) tokens: saved at once, in arrival order.
            RefreshOutcome.OK -> if (refreshed) runCatching { persist(current, onlyIf = current) }
            RefreshOutcome.SESSION_ENDED -> runCatching { persist(AuthState(), onlyIf = current) }
            // AppAuth marks the in-memory state failed on any OAuth error body; the saved tokens are still the newest,
            // so they come back (a network error leaves the state untouched).
            RefreshOutcome.TRY_LATER -> if (!current.isAuthorized) synchronized(writeLock) {
                val saved = restore()
                synchronized(lock) {
                    if (state === current) {
                        state = saved
                        _signedIn.value = saved.isAuthorized
                    }
                }
            }
        }
    }

    /**
     * Clears the local session and returns an intent that ends the Keycloak SSO session in the browser
     * (null when the provider exposes no end-session endpoint). The offline session the refresh token belongs to is
     * ended in the background (best effort; it otherwise expires after the offline idle timeout).
     */
    fun logout(): Intent? {
        val previous = synchronized(lock) { state }
        persist(AuthState())
        val serviceConfig = previous.authorizationServiceConfiguration ?: return null
        endOfflineSession(serviceConfig, previous.refreshToken)
        if (serviceConfig.endSessionEndpoint == null) return null
        val request = EndSessionRequest.Builder(serviceConfig)
            .setIdTokenHint(previous.idToken)
            .setPostLogoutRedirectUri(config.postLogoutRedirectUri.toUri())
            .build()
        return service.getEndSessionRequestIntent(request)
    }

    /** Back-channel logout with the refresh token (Keycloak's end-session endpoint, as the iOS apps do). */
    private fun endOfflineSession(serviceConfig: AuthorizationServiceConfiguration, refreshToken: String?) {
        val endpoint = serviceConfig.endSessionEndpoint ?: return
        if (refreshToken.isNullOrBlank()) return
        // Its own thread: a slow sign-in server must never hold up saving a refresh result.
        thread(isDaemon = true, name = "asseta-auth-logout") {
            runCatching {
                val connection = connectionBuilder.openConnection(endpoint)
                try {
                    connection.requestMethod = "POST"
                    connection.doOutput = true
                    connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
                    val body = "client_id=${encode(config.clientId)}&refresh_token=${encode(refreshToken)}"
                    connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                    connection.responseCode
                } finally {
                    connection.disconnect()
                }
            }
        }
    }

    private fun encode(value: String) = URLEncoder.encode(value, "UTF-8")

    private companion object {
        const val REFRESH_TIMEOUT_SECONDS = 30L
    }
}
