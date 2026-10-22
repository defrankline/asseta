package com.asseta.core.domain.owner

/** Owner app destinations reachable from a notification (push tap, inbox row, WebSocket frame). */
sealed interface OwnerDestination {
    data object Home : OwnerDestination
    data object Fleet : OwnerDestination
    data class Machine(val machineId: String) : OwnerDestination
    data object Jobs : OwnerDestination
    data class Job(val jobId: String) : OwnerDestination
    /** Alerts list, scrolled to / highlighting [alertId] when known. */
    data class Alerts(val alertId: String? = null) : OwnerDestination
    data class Approvals(val approvalId: String? = null) : OwnerDestination
    data object Cases : OwnerDestination
    data class Case(val caseId: String) : OwnerDestination
    data class Notifications(val notificationId: String? = null) : OwnerDestination
    data object Settings : OwnerDestination
    /** Menu of the secondary screens (approvals, investigations, notifications, settings). */
    data object More : OwnerDestination
}

/** A deep link resolved from a push payload: [tenantId] must be entered first when it differs from the current one. */
data class DeepLink(val destination: OwnerDestination, val tenantId: String?, val notificationId: String?)

/**
 * Maps notification targets (`{"entity","id","path"}`) and push data (`notification_id`, `type`, `tenant_id`, `link`)
 * to owner destinations. Anything the Owner app does not show (customer payments, cash handovers, access...) opens
 * the notification inbox instead of a console-only screen. Ids are accepted only in canonical UUID form.
 */
object DeepLinkRouter {
    private val UUID = Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

    private fun id(raw: String?): String? = raw?.takeIf { UUID.matches(it) }

    fun fromTarget(entity: String?, id: String?, path: String?, notificationId: String? = null): OwnerDestination {
        val target = id(id)
        return when (entity) {
            "alert" -> OwnerDestination.Alerts(target)
            "approval" -> OwnerDestination.Approvals(target)
            "job" -> target?.let { OwnerDestination.Job(it) } ?: OwnerDestination.Jobs
            "machine", "fleet.position" -> target?.let { OwnerDestination.Machine(it) } ?: OwnerDestination.Fleet
            "case" -> target?.let { OwnerDestination.Case(it) } ?: OwnerDestination.Cases
            else -> fromPath(path) ?: OwnerDestination.Notifications(id(notificationId))
        }
    }

    /** Console paths (`target.path` / push `link`) the Owner app has an equivalent for. */
    fun fromPath(path: String?): OwnerDestination? {
        val segments = path?.substringBefore('?')?.trim('/')?.split('/')?.filter { it.isNotEmpty() } ?: return null
        if (segments.firstOrNull() != "tenant") return null
        val rest = segments.drop(1)
        val second = id(rest.getOrNull(1))
        return when (rest.firstOrNull()) {
            "alerts" -> OwnerDestination.Alerts(second)
            "approvals" -> OwnerDestination.Approvals(second)
            "jobs" -> second?.let { OwnerDestination.Job(it) } ?: OwnerDestination.Jobs
            "cases" -> second?.let { OwnerDestination.Case(it) } ?: OwnerDestination.Cases
            "machines" -> second?.let { OwnerDestination.Machine(it) } ?: OwnerDestination.Fleet
            "fleet" -> id(rest.getOrNull(2))?.let { OwnerDestination.Machine(it) } ?: OwnerDestination.Fleet
            "notifications" -> OwnerDestination.Notifications(second)
            else -> null
        }
    }

    /** Push data map from FCM (`notification_id`, `type`, `severity`, `tenant_id`, `link`). Null when not ours. */
    fun fromPush(data: Map<String, String?>): DeepLink? {
        val notificationId = id(data["notification_id"])
        val link = data["link"]
        if (notificationId == null && link.isNullOrBlank()) return null
        val destination = fromPath(link) ?: OwnerDestination.Notifications(notificationId)
        return DeepLink(destination, id(data["tenant_id"]), notificationId)
    }
}
