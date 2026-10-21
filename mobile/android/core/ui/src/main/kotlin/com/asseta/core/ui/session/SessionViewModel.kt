package com.asseta.core.ui.session

import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.auth.AuthFailure
import com.asseta.core.auth.AuthManager
import com.asseta.core.auth.SelectedTenantStore
import com.asseta.core.network.ApiException
import com.asseta.core.network.AssetaApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SessionViewModel(
    private val auth: AuthManager,
    private val api: AssetaApi,
    private val tenants: SelectedTenantStore,
) : ViewModel() {

    private val _state = MutableStateFlow<SessionState>(SessionState.SignedOut())
    val state: StateFlow<SessionState> = _state.asStateFlow()

    init {
        if (auth.signedIn.value) loadProfile()
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
                    _state.value = SessionState.Ready(me, selected)
                }
                .onFailure { e ->
                    if (e is ApiException && e.isUnauthenticated) {
                        auth.logout()
                        tenants.clear()
                        _state.value = SessionState.SignedOut(UiError("Your session ended. Please sign in again.", e.correlationId))
                    } else {
                        _state.value = SessionState.ProfileError(SessionRules.toUiError(e))
                    }
                }
        }
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
        _state.value = SessionState.SignedOut()
        return intent
    }

    private fun Throwable.unwrapAuth(): Throwable =
        if (this is AuthFailure) Exception(reason, cause) else this
}
