package com.asseta.supervisor.push

import android.content.Context
import android.os.Build
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.edit
import com.asseta.core.push.PushRegistrar
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Push of this phone (app SUPERVISOR): registration with the selected tenant, the notification permission (asked once)
 * and the account-menu status. Registration runs in the background and never blocks sign-in or sync; a failure is
 * retried the next time the home opens.
 */
class SupervisorPush(context: Context, private val registrar: PushRegistrar, private val scope: CoroutineScope) {
    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val _registered = MutableStateFlow(registrar.registeredDeviceId != null)

    val registered: StateFlow<Boolean> = _registered.asStateFlow()
    val available: Boolean get() = registrar.available

    /** Whether the permission prompt was shown once (a refusal is never asked again automatically). */
    var asked: Boolean
        get() = prefs.getBoolean(KEY_ASKED, false)
        set(value) = prefs.edit { putBoolean(KEY_ASKED, value) }

    fun permission(): NotificationPermission =
        PushTexts.permission(NotificationManagerCompat.from(appContext).areNotificationsEnabled(), Build.VERSION.SDK_INT, asked)

    fun status(): PhonePushStatus = PushTexts.status(available, _registered.value, permission())

    /** Registers (or re-binds to the selected tenant); false when unavailable or the server could not be reached. */
    suspend fun register(): Boolean {
        val device = runCatching { registrar.register() }.getOrNull()
        _registered.value = registrar.registeredDeviceId != null
        return device != null
    }

    fun registerInBackground() {
        if (available) scope.launch { register() }
    }

    /** Best effort: deactivates this phone's registration (sign-out, or a company whose role gets no notifications). */
    suspend fun unregister() {
        registrar.unregister()
        _registered.value = false
    }

    fun unregisterInBackground() {
        if (registrar.registeredDeviceId != null) scope.launch { unregister() }
    }

    /** FCM rotated the token: re-register only an existing registration (the home registers new ones). */
    fun onNewToken() {
        if (registrar.registeredDeviceId != null) registerInBackground()
    }

    fun forget() {
        registrar.forget()
        _registered.value = false
    }

    companion object {
        /** Shared with [PushRegistrar] (its `device_id` key); the prompt flag lives next to it. */
        const val PREFS = "asseta_supervisor_push"
        private const val KEY_ASKED = "permission_asked"
    }
}
