package com.asseta.supervisor.capture

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.SystemClock
import androidx.core.content.ContextCompat
import androidx.core.location.LocationManagerCompat
import com.asseta.core.domain.capture.GpsOutcome
import com.google.android.gms.location.CurrentLocationRequest
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import kotlinx.coroutines.withTimeoutOrNull
import java.time.Instant

/**
 * One fresh foreground GPS attempt per capture (Fused Location, high accuracy, ~20 s). Records the real outcome:
 * a fix taken after the attempt started, or NO_FIX / TIMEOUT / PERMISSION_DENIED / DISABLED without coordinates.
 * Cached or older locations are never reused. No background location is requested.
 */
class GpsLocator(context: Context) {
    private val appContext = context.applicationContext
    private val client = LocationServices.getFusedLocationProviderClient(appContext)

    fun hasPermission(): Boolean = PERMISSIONS.any {
        ContextCompat.checkSelfPermission(appContext, it) == PackageManager.PERMISSION_GRANTED
    }

    @SuppressLint("MissingPermission") // checked by hasPermission(); a revoked permission surfaces as SecurityException
    suspend fun attempt(timeoutMs: Long = TIMEOUT_MS): GpsOutcome {
        if (!hasPermission()) return GpsOutcome.PermissionDenied
        val manager = appContext.getSystemService(LocationManager::class.java)
        if (manager == null || !LocationManagerCompat.isLocationEnabled(manager)) return GpsOutcome.Disabled
        val startedElapsedMs = SystemClock.elapsedRealtime()
        val cancel = CancellationTokenSource()
        val request = CurrentLocationRequest.Builder()
            .setPriority(Priority.PRIORITY_HIGH_ACCURACY)
            .setMaxUpdateAgeMillis(0) // fresh fix only
            .setDurationMillis(timeoutMs)
            .build()
        return try {
            // Wrapped so a provider answer of "no location" (NO_FIX) is distinguishable from our timeout (TIMEOUT).
            val answer = withTimeoutOrNull(timeoutMs) { listOf(client.getCurrentLocation(request, cancel.token).awaitResult()) }
                ?: run { cancel.cancel(); return GpsOutcome.Timeout }
            val location = answer.single() ?: return GpsOutcome.NoFix
            val fixElapsedMs = location.elapsedRealtimeNanos / 1_000_000
            if (!GpsOutcome.acceptFix(Instant.ofEpochMilli(fixElapsedMs), Instant.ofEpochMilli(startedElapsedMs))) {
                return GpsOutcome.NoFix
            }
            GpsOutcome.Fix(
                latitude = location.latitude,
                longitude = location.longitude,
                accuracyM = if (location.hasAccuracy()) location.accuracy.toDouble() else null,
                capturedAt = Instant.ofEpochMilli(location.time),
                provider = location.provider ?: "fused",
            )
        } catch (_: SecurityException) {
            GpsOutcome.PermissionDenied
        } catch (_: Exception) {
            GpsOutcome.NoFix
        }
    }

    companion object {
        const val TIMEOUT_MS = 20_000L
        val PERMISSIONS = arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
    }
}
