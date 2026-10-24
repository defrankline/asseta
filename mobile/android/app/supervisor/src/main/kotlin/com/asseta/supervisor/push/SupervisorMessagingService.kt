package com.asseta.supervisor.push

import com.asseta.core.push.PushNotifier
import com.asseta.supervisor.MainActivity
import com.asseta.supervisor.SupervisorApplication
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

/** FCM entry point (only invoked when Firebase is configured). Never logs tokens or message content. */
class SupervisorMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        (application as SupervisorApplication).field.onPushTokenRefreshed()
    }

    /** Shown like the Owner app (also in the foreground); the Inbox list is refreshed right away. */
    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val title = message.notification?.title ?: data["title"] ?: "Asseta"
        val body = message.notification?.body ?: data["body"] ?: ""
        notifier.show(this, title, body, data)
        (application as SupervisorApplication).field.onPushReceived()
    }

    companion object {
        /** Supervisor channels (`supervisor_priority` is the FCM default channel in the manifest); taps open [MainActivity]. */
        val notifier = PushNotifier("supervisor_priority", "supervisor_updates", MainActivity::class.java)
    }
}
