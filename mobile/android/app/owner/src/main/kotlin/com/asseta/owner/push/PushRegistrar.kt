package com.asseta.owner.push

import android.content.Context
import android.os.Build
import androidx.core.content.edit
import com.asseta.core.model.owner.PushDeviceDto
import com.asseta.core.model.owner.PushDeviceIn
import com.asseta.core.network.TenantApi

/**
 * Registers this installation's push token with `/me/push-devices` (platform ANDROID, app OWNER) for the selected
 * tenant, and deactivates it on sign-out. The server de-duplicates by token, so re-registering is safe.
 */
class PushRegistrar(
    context: Context,
    private val provider: PushTokenProvider,
    private val api: () -> TenantApi,
    private val appVersion: String,
) {
    private val prefs = context.applicationContext.getSharedPreferences("asseta_owner_push", Context.MODE_PRIVATE)

    val available: Boolean get() = provider.available
    val providerName: String get() = provider.name

    /** Server id of this device's registration, when registered. */
    val registeredDeviceId: String? get() = prefs.getString(KEY_DEVICE, null)

    /** Returns the registration, or null when push is unavailable. Exceptions (network/server) propagate. */
    suspend fun register(): PushDeviceDto? {
        if (!provider.available) return null
        val token = provider.token() ?: return null
        val device = api().registerPushDevice(
            PushDeviceIn(token = token, platform = PLATFORM, app = APP, appVersion = appVersion, deviceLabel = "${Build.MANUFACTURER} ${Build.MODEL}".take(100)),
        )
        prefs.edit { putString(KEY_DEVICE, device.id.toString()) }
        return device
    }

    /** Best effort on sign-out: deactivate the server registration and drop the local token. */
    suspend fun unregister() {
        registeredDeviceId?.let { id -> runCatching { api().deactivatePushDevice(id) } }
        prefs.edit { remove(KEY_DEVICE) }
        runCatching { provider.deleteToken() }
    }

    fun forget() = prefs.edit { remove(KEY_DEVICE) }

    companion object {
        const val PLATFORM = "ANDROID"
        const val APP = "OWNER"
        private const val KEY_DEVICE = "device_id"
    }
}
