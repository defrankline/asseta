package com.asseta.core.auth

import android.content.Context
import androidx.core.content.edit
import com.asseta.core.network.TenantIdProvider
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Remembers which tenant the user is working in (an id, not a secret). Choosing a tenant here only sets
 * the `X-Tenant-ID` header; the server still verifies membership on every request.
 */
class SelectedTenantStore(context: Context) : TenantIdProvider {
    private val prefs = context.applicationContext.getSharedPreferences("asseta_session", Context.MODE_PRIVATE)
    private val _selected = MutableStateFlow(prefs.getString(KEY, null))
    val selected: StateFlow<String?> = _selected.asStateFlow()

    override fun tenantId(): String? = _selected.value

    fun select(tenantId: String) {
        prefs.edit { putString(KEY, tenantId) }
        _selected.value = tenantId
    }

    fun clear() {
        prefs.edit { remove(KEY) }
        _selected.value = null
    }

    private companion object {
        const val KEY = "selected_tenant_id"
    }
}
