package com.asseta.supervisor.capture

import android.content.Context
import android.location.Address
import android.location.Geocoder
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import com.asseta.core.domain.reports.Visits
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.util.Locale
import kotlin.coroutines.resume

/**
 * The area label of a GPS fix by the platform geocoder ("Mbezi Beach, Kinondoni, Dar es Salaam"): neighbourhood,
 * district, city -- never a street address. Only when the phone is online; at most ~3 s; null on any failure. Callers
 * never wait for it before saving a reading.
 */
class PlaceNamer(context: Context) {
    private val appContext = context.applicationContext

    fun online(): Boolean = runCatching {
        val manager = appContext.getSystemService(ConnectivityManager::class.java) ?: return false
        val caps = manager.getNetworkCapabilities(manager.activeNetwork) ?: return false
        caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }.getOrDefault(false)

    suspend fun placeName(lat: Double, lng: Double, timeoutMs: Long = TIMEOUT_MS): String? {
        if (!online() || !Geocoder.isPresent()) return null
        val address = withTimeoutOrNull(timeoutMs) { lookUp(lat, lng) } ?: return null
        return Visits.placeLabel(address.subLocality, address.subAdminArea, address.locality)
    }

    private suspend fun lookUp(lat: Double, lng: Double): Address? = runCatching {
        val geocoder = Geocoder(appContext, Locale.ENGLISH)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            suspendCancellableCoroutine { cont ->
                geocoder.getFromLocation(lat, lng, 1, object : Geocoder.GeocodeListener {
                    override fun onGeocode(addresses: MutableList<Address>) { if (cont.isActive) cont.resume(addresses.firstOrNull()) }
                    override fun onError(errorMessage: String?) { if (cont.isActive) cont.resume(null) }
                })
            }
        } else {
            // The blocking lookup runs on its own thread so the timeout returns at once (a late answer is dropped).
            suspendCancellableCoroutine { cont ->
                Thread {
                    @Suppress("DEPRECATION")
                    val found = runCatching { geocoder.getFromLocation(lat, lng, 1)?.firstOrNull() }.getOrNull()
                    if (cont.isActive) cont.resume(found)
                }.apply { isDaemon = true }.start()
            }
        }
    }.getOrNull()

    companion object {
        const val TIMEOUT_MS = 3_000L
    }
}
