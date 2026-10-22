package com.asseta.owner.push

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.asseta.owner.MainActivity
import com.asseta.owner.R

/**
 * Shows push messages received while the app runs (FCM delivers them to the service, not the tray). The tap intent
 * carries the push data (`notification_id`, `tenant_id`, `link`, ...) that MainActivity routes via DeepLinkRouter.
 */
object PushNotifier {
    const val CHANNEL_HIGH = "owner_priority"
    const val CHANNEL_NORMAL = "owner_updates"
    val DATA_KEYS = listOf("notification_id", "type", "severity", "tenant_id", "link")

    fun ensureChannels(context: Context) {
        val nm = context.getSystemService(NotificationManager::class.java) ?: return
        nm.createNotificationChannel(NotificationChannel(CHANNEL_HIGH, "Priority alerts", NotificationManager.IMPORTANCE_HIGH))
        nm.createNotificationChannel(NotificationChannel(CHANNEL_NORMAL, "Updates", NotificationManager.IMPORTANCE_DEFAULT))
    }

    fun tapIntent(context: Context, data: Map<String, String>): Intent =
        Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            DATA_KEYS.forEach { key -> data[key]?.let { putExtra(key, it) } }
        }

    fun show(context: Context, title: String, body: String, data: Map<String, String>) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        ensureChannels(context)
        val high = data["severity"] in setOf("CRITICAL", "WARNING")
        val pending = PendingIntent.getActivity(
            context, (data["notification_id"] ?: title).hashCode(), tapIntent(context, data),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, if (high) CHANNEL_HIGH else CHANNEL_NORMAL)
            .setSmallIcon(R.drawable.ic_stat_asseta)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(if (high) NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify((data["notification_id"] ?: title).hashCode(), notification) }
    }
}
