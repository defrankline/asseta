package com.asseta.core.push

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
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

/**
 * Shows push messages received while the app runs (FCM delivers them to the service, not the tray). The tap intent
 * carries the push data (`notification_id`, `tenant_id`, `link`, ...) to [activity], which routes it. Each app has its
 * own channel ids; [channelHigh] is also the FCM default channel declared in the app manifest.
 */
class PushNotifier(
    val channelHigh: String,
    val channelNormal: String,
    private val activity: Class<out Activity>,
) {
    fun ensureChannels(context: Context) {
        val nm = context.getSystemService(NotificationManager::class.java) ?: return
        nm.createNotificationChannel(NotificationChannel(channelHigh, "Priority alerts", NotificationManager.IMPORTANCE_HIGH))
        nm.createNotificationChannel(NotificationChannel(channelNormal, "Updates", NotificationManager.IMPORTANCE_DEFAULT))
    }

    fun tapIntent(context: Context, data: Map<String, String>): Intent =
        Intent(context, activity).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            DATA_KEYS.forEach { key -> data[key]?.let { putExtra(key, it) } }
        }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked first (each app declares it)
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
        val notification = NotificationCompat.Builder(context, if (high) channelHigh else channelNormal)
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

    companion object {
        val DATA_KEYS = listOf("notification_id", "type", "severity", "tenant_id", "link", "entity", "entity_id", "kind", "record_id")
    }
}
