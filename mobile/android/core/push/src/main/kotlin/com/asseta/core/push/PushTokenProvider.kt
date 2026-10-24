package com.asseta.core.push

import android.content.Context
import com.google.android.gms.tasks.Task
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Source of this installation's push token. FCM when configured; otherwise a no-op (push simply off). */
interface PushTokenProvider {
    /** Human-readable name shown in Settings ("Firebase Cloud Messaging", "Not configured"). */
    val name: String
    val available: Boolean
    suspend fun token(): String?
    suspend fun deleteToken()
}

/** Used when no Firebase project is configured (no google-services.json): push is unavailable, nothing is sent. */
object NoOpPushTokenProvider : PushTokenProvider {
    override val name = "Not configured on this build"
    override val available = false
    override suspend fun token(): String? = null
    override suspend fun deleteToken() = Unit
}

/** FCM token provider; only active when the build had a google-services.json and Firebase initialised. */
class FcmPushTokenProvider : PushTokenProvider {
    override val name = "Firebase Cloud Messaging"
    override val available = true
    override suspend fun token(): String? = FirebaseMessaging.getInstance().token.await()
    override suspend fun deleteToken() {
        FirebaseMessaging.getInstance().deleteToken().await()
    }

    companion object {
        /** FCM is used only when compiled in with a Firebase config (BuildConfig flag) and Firebase is initialised. */
        fun isConfigured(context: Context, buildFlag: Boolean): Boolean =
            buildFlag && runCatching { FirebaseApp.getApps(context).isNotEmpty() }.getOrDefault(false)
    }
}

private suspend fun <T> Task<T>.await(): T = suspendCancellableCoroutine { cont ->
    addOnCompleteListener { task ->
        val error = task.exception
        if (error != null) cont.resumeWithException(error) else cont.resume(task.result)
    }
}
