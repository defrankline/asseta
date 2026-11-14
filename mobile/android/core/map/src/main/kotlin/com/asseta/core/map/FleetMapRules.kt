package com.asseta.core.map

import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.Freshness
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.MachineMapDto
import kotlinx.coroutines.CancellationException
import retrofit2.HttpException

/**
 * Rules of the machine map (`getFleetMap`) shared by the apps; same rules as iOS `FleetMapRules`.
 *
 * The server decides which machines a person sees (a supervisor gets their own machines unless the company setting
 * `TRACKING.field_fleet_scope` is `ALL`), so the app never filters the list itself. The map is online only.
 */
object FleetMapRules {
    /** Permission behind the fleet map endpoints. Without it the Map / List switch is not shown at all. */
    const val PERMISSION = "tenant.fleet.read"

    fun canShowMap(permissions: Collection<String>): Boolean = PERMISSION in permissions

    /** Machines drawn on the map (with a known position) and those without one (counted in [unplacedNote]). */
    data class Split(val placed: List<MachineMapDto>, val unplaced: List<MachineMapDto>)

    fun split(machines: List<MachineMapDto>): Split = machines.partition { it.hasPosition }.let { (a, b) -> Split(a, b) }

    /** Shown over the map when machines have no known position. */
    fun unplacedNote(count: Int): String? = when {
        count <= 0 -> null
        count == 1 -> "1 machine has no known position (see List)."
        else -> "$count machines have no known position (see List)."
    }

    /** What the map pane shows. */
    sealed interface State {
        /** No connection: the map is not loaded (the List keeps working from the phone's data). */
        data object Offline : State
        data object Loading : State
        data class Failed(val message: String) : State
        data class Loaded(val machines: List<MachineMapDto>, val fetchedAtMs: Long) : State
    }

    /** Loads the map when [online]; offline it never calls the server. Errors become a plain message, never a crash. */
    suspend fun load(online: Boolean, nowMs: () -> Long, fetch: suspend () -> List<MachineMapDto>): State {
        if (!online) return State.Offline
        return try {
            State.Loaded(fetch(), nowMs())
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            State.Failed(errorMessage(e))
        }
    }

    fun errorMessage(error: Throwable): String = when ((error as? HttpException)?.code()) {
        403 -> FORBIDDEN
        404 -> NOT_FOUND
        null -> if (error is java.io.IOException) NO_CONNECTION else FAILED
        else -> FAILED
    }

    /** The card shown when a marker is tapped. */
    data class Status(val title: String, val connectivity: Connectivity, val lastSeen: String, val reported: String)

    /**
     * Asset code and name, connectivity (never "Live" unless the server says so in a fresh response), when it was last
     * seen and the reported work status.
     */
    fun status(m: MachineMapDto, fetchedAtMs: Long, nowMs: Long): Status {
        val connectivity = Freshness.displayConnectivity(m.connectivity, m.isLive, DataSource.LIVE, fetchedAtMs, nowMs)
        val seenAt = OwnerFormat.parseInstant(m.lastMessageAt ?: m.positionTime)?.toEpochMilli()
        val age = Freshness.ageSeconds(seenAt, nowMs)
            ?: m.lastSeenAgeSeconds?.let { it + ((nowMs - fetchedAtMs) / 1000).coerceAtLeast(0) }
        val lastSeen = age?.let { "Last seen ${Freshness.ageLabel(it)}" } ?: NEVER_SEEN
        return Status("${m.assetCode} · ${m.name}", connectivity, lastSeen, "Reported: ${OwnerFormat.humanize(m.reportedWorkStatus)}")
    }

    fun mapDescription(placed: Int): String =
        "Map of your machines with ${if (placed == 1) "1 machine" else "$placed machines"}. Use the List view for details."

    const val MAP = "Map"
    const val LIST = "List"
    const val NEVER_SEEN = "Never seen"
    const val OFFLINE = "The map needs a connection. Your machines are still listed under List."
    const val LOADING = "Loading the map…"
    const val EMPTY = "No machines to show on the map."
    const val FORBIDDEN = "You do not have access to the machine map in this company."
    const val NOT_FOUND = "The machine map is not available in this company."
    const val NO_CONNECTION = "Could not reach the server. Check your connection and try again."
    const val FAILED = "Could not load the map. Try again."
    const val TRY_AGAIN = "Try again"
}
