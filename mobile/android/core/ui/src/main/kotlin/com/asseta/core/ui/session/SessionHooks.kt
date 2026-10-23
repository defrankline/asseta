package com.asseta.core.ui.session

import androidx.compose.runtime.staticCompositionLocalOf
import com.asseta.core.model.MeResponse

/**
 * App-specific reactions to session changes (e.g. the Owner app wipes its offline cache on sign-out and drops
 * cached data of tenants the user can no longer enter). Defaults do nothing, so the Supervisor keeps its behaviour.
 */
interface SessionHooks {
    /** Runs (bounded by a timeout) before a user-initiated sign-out clears tokens, while API calls still work. */
    suspend fun beforeSignOut() {}

    /** After any sign-out: user, forced (device wipe notice) or an ended session (401). */
    fun onSignedOut() {}

    /**
     * Text of a "Sign out?" confirmation shown before a user-initiated sign-out (e.g. the Supervisor warns about
     * unsynced items); null signs out without asking.
     */
    suspend fun signOutConfirmation(): String? = null

    /** After `/me` loaded; [me] is the server's current view of the user's tenants. */
    fun onProfile(me: MeResponse) {}
}

object NoSessionHooks : SessionHooks

/** Session actions for screens inside the app home (e.g. a Settings "Sign out" button). */
data class SessionActions(
    val signOut: () -> Unit = {},
    val switchTenant: () -> Unit = {},
    /** The API answered 401: end the session with an explanation. */
    val sessionExpired: () -> Unit = {},
    /** Re-read `/me` (e.g. after a tenant access refusal). */
    val refreshProfile: () -> Unit = {},
    /** Enter another tenant (e.g. a notification tap for a different company); ignored unless enterable. */
    val selectTenant: (String) -> Unit = {},
    /** Opens Keycloak's password page; the result is shown by the session shell. */
    val changePassword: () -> Unit = {},
    /** True while the password page is open (the action is disabled meanwhile). */
    val changingPassword: Boolean = false,
)

val LocalSessionActions = staticCompositionLocalOf { SessionActions() }
