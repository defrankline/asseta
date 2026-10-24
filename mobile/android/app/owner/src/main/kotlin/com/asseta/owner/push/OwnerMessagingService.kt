package com.asseta.owner.push

import com.asseta.core.push.PushNotifier
import com.asseta.owner.MainActivity
import com.asseta.owner.OwnerApplication
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

/** FCM entry point (only invoked when Firebase is configured). Never logs tokens or message content. */
class OwnerMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        (application as OwnerApplication).graph.onPushTokenRefreshed()
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val title = message.notification?.title ?: data["title"] ?: "Asseta"
        val body = message.notification?.body ?: data["body"] ?: ""
        notifier.show(this, title, body, data)
    }

    companion object {
        /** Owner channels (`owner_priority` is the FCM default channel in the manifest); taps open [MainActivity]. */
        val notifier = PushNotifier("owner_priority", "owner_updates", MainActivity::class.java)
    }
}
