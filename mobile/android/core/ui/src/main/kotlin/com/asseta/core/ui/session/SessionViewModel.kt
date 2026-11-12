package com.asseta.core.ui.session

import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.auth.AuthFailure
import com.asseta.core.auth.AuthManager
import com.asseta.core.auth.PasswordChange
import com.asseta.core.auth.SelectedTenantStore
import com.asseta.core.model.AccountDeletionRequest
import com.asseta.core.network.ApiException
import com.asseta.core.network.AssetaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

class SessionViewModel(
    private val auth: AuthManager,
    private val api: AssetaApi,
    private val tenants: SelectedTenantStore,
    private val notice: SessionNotice? = null,
    private val hooks: SessionHooks = NoSessionHooks,
) : ViewModel() {

    private val _state = MutableStateFlow<SessionState>(SessionState.SignedOut())
    val state: StateFlow<SessionState> = _state.asStateFlow()

    private val _passwordChange = MutableStateFlow<PasswordChangeState>(PasswordChangeState.Idle)
    val passwordChange: StateFlow<PasswordChangeState> = _passwordChange.asStateFlow()

    init {
        if (auth.signedIn.value) loadProfile()
        // A forced sign-out (device revoked + wiped, possibly by background sync) ends the session with its reason.
        notice?.let { n ->
            viewModelScope.launch {
                n.pending.collect { message ->
                    if (message != null) {
                        tenants.clear()
                        auth.logout()
                        hooks.onSignedOut()
                        _state.value = SessionState.SignedOut(UiError(n.consume() ?: message))
                    }
                }
            }
        }
    }

    /** Resolves Keycloak discovery and hands back the browser intent to launch. */
    fun startLogin(launch: (Intent) -> Unit) {
        _state.value = SessionState.SignedOut(busy = true)
        viewModelScope.launch {
            runCatching { auth.createLoginIntent() }
                .onSuccess(launch)
                .onFailure { _state.value = SessionState.SignedOut(SessionRules.toUiError(it.unwrapAuth())) }
        }
    }

    fun onLoginResult(data: Intent?) {
        viewModelScope.launch {
            runCatching { auth.completeLogin(data) }
                .onSuccess { loadProfile() }
                .onFailure { _state.value = SessionState.SignedOut(SessionRules.toUiError(it.unwrapAuth())) }
        }
    }

    fun loadProfile() {
        _state.value = SessionState.LoadingProfile
        viewModelScope.launch {
            runCatching { api.me() }
                .onSuccess { me ->
                    val selected = SessionRules.resolveSelection(me, tenants.tenantId())
                    if (selected == null) tenants.clear() else tenants.select(selected)
                    withTimeoutOrNull(BEFORE_HOME_TIMEOUT_MS) { runCatching { hooks.beforeHome(me) } }
                    hooks.onProfile(me)
                    _state.value = SessionState.Ready(me, selected)
                }
                .onFailure { e ->
                    if (e is ApiException && e.isUserInactive) {
                        notice?.consume()
                        signOutLocally(AccountDeletionText.INACTIVE)
                    } else if (e is ApiException && e.isUnauthenticated) {
                        endSession(e.correlationId)
                    } else {
                        _state.value = SessionState.ProfileError(SessionRules.toUiError(e))
                    }
                }
        }
    }

    /**
     * "Change password": opens Keycloak's own password page (kc_action=UPDATE_PASSWORD). The app never handles the
     * password; the user stays signed in whatever the outcome.
     */
    fun startPasswordChange(launch: (Intent) -> Unit) {
        if (_passwordChange.value == PasswordChangeState.InProgress) return
        _passwordChange.value = PasswordChangeState.InProgress
        viewModelScope.launch {
            runCatching { auth.createChangePasswordIntent() }
                .onSuccess(launch)
                .onFailure { _passwordChange.value = PasswordChangeState.Failed(PasswordChange.FAILED_MESSAGE) }
        }
    }

    fun onPasswordChangeResult(data: Intent?) {
        viewModelScope.launch {
            _passwordChange.value = runCatching { auth.completeChangePassword(data) }.fold(
                onSuccess = SessionRules::passwordChangeState,
                onFailure = { PasswordChangeState.Failed(PasswordChange.FAILED_MESSAGE) },
            )
        }
    }

    /** The user acknowledged the "Password changed." / failure message. */
    fun dismissPasswordChange() {
        _passwordChange.value = PasswordChangeState.Idle
    }

    /** Returns to the tenant list (the selection is kept until another tenant is chosen). */
    fun showTenantPicker() {
        val ready = _state.value as? SessionState.Ready ?: return
        _state.value = ready.copy(selectedTenantId = null)
    }

    fun selectTenant(tenantId: String) {
        val ready = _state.value as? SessionState.Ready ?: return
        val tenant = ready.me.tenants.firstOrNull { it.tenantId.toString() == tenantId } ?: return
        if (!tenant.accessState.canEnter) return
        tenants.select(tenantId)
        _state.value = ready.copy(selectedTenantId = tenantId)
    }

    /** Returns the Keycloak end-session intent (if any) after clearing local session state. */
    fun logout(): Intent? {
        tenants.clear()
        val intent = auth.logout()
        hooks.onSignedOut()
        _state.value = SessionState.SignedOut()
        return intent
    }

    /** User sign-out: app hooks first (bounded, e.g. deactivate this device's push token), then [logout]. */
    fun signOut(launch: (Intent) -> Unit) {
        viewModelScope.launch {
            withTimeoutOrNull(SIGN_OUT_HOOK_TIMEOUT_MS) { runCatching { hooks.beforeSignOut() } }
            logout()?.let(launch)
        }
    }

    /** `POST /me/account-deletion` (no tenant): the login is deleted for good; throws the server's refusal. */
    suspend fun deleteAccount(reason: String?) {
        api.deleteMyAccount(AccountDeletionRequest(confirm = true, reason = reason))
    }

    /**
     * The account was deleted: the app erases what only it could use, then the same local sign-out as always (tokens,
     * company, push, the app's sign-out wipe). No Keycloak end-session page: the session no longer exists.
     */
    fun accountDeleted() {
        viewModelScope.launch {
            withTimeoutOrNull(SIGN_OUT_HOOK_TIMEOUT_MS) { runCatching { hooks.onAccountDeleted() } }
            signOutLocally(AccountDeletionText.DELETED)
        }
    }

    private fun signOutLocally(message: String) {
        tenants.clear()
        auth.logout()
        hooks.onSignedOut()
        _state.value = SessionState.SignedOut(UiError(message))
    }

    /** The API rejected the session (401): sign out locally and explain why. */
    fun endSession(reference: String? = null) {
        auth.logout()
        tenants.clear()
        hooks.onSignedOut()
        _state.value = SessionState.SignedOut(UiError("Your session ended. Please sign in again.", reference))
    }

    private companion object {
        const val SIGN_OUT_HOOK_TIMEOUT_MS = 5_000L
        const val BEFORE_HOME_TIMEOUT_MS = 10_000L
    }

    private fun Throwable.unwrapAuth(): Throwable =
        if (this is AuthFailure) Exception(reason, cause) else this
}
