package com.asseta.core.ui.session

import android.content.Context
import androidx.core.content.edit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * A forced sign-out explanation (e.g. device revoked and wiped). Persisted (not sensitive) so it is still shown when
 * the wipe happened in background sync while the app was not visible.
 */
class SessionNotice(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("asseta_session_notice", Context.MODE_PRIVATE)
    private val _pending = MutableStateFlow(prefs.getString(KEY, null))
    val pending: StateFlow<String?> = _pending.asStateFlow()

    fun post(message: String) {
        prefs.edit(commit = true) { putString(KEY, message) }
        _pending.value = message
    }

    fun consume(): String? {
        val message = _pending.value ?: return null
        prefs.edit { remove(KEY) }
        _pending.value = null
        return message
    }

    private companion object {
        const val KEY = "message"
    }
}
