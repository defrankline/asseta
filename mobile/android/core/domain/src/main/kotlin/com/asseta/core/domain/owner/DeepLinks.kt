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
    /** A meter reset request (listed under Approvals), with approve / reject. */
    data class MeterReset(val resetId: String) : OwnerDestination
    /** Meter exceptions, optionally only those of [jobId]. */
    data class Exceptions(val jobId: String? = null) : OwnerDestination
    /** One meter exception with its review (REVIEW_EXCEPTION). */
    data class MeterException(val exceptionId: String) : OwnerDestination
    /** One cash handover a supervisor claimed, with confirm received / dispute. */
    data class Handover(val handoverId: String) : OwnerDestination
    /** Expenses and fuel recorded in the field. */
    data object FieldSpend : OwnerDestination
    /** Cash held by each supervisor over a period. */
    data object Cash : OwnerDestination
    data object Cases : OwnerDestination
    data class Case(val caseId: String) : OwnerDestination
    data class Notifications(val notificationId: String? = null) : OwnerDestination
    data object Settings : OwnerDestination
    /** Menu of the secondary screens (approvals, exceptions, field spend, cash, investigations, notifications, settings). */
    data object More : OwnerDestination

    /** An accountability request to approve or reject ([kind] a [DecisionKinds] code), listed under Approvals. */
    data class Decision(val kind: String, val id: String) : OwnerDestination

    /** Accountability dashboard summary (tenant.accountability.read). */
    data object Accountability : OwnerDestination
}

/** Codes of the accountability decisions the Owner app lists under Approvals (and their notification entities). */
object DecisionKinds {
    const val DISCOUNT = "DISCOUNT"
    const val CREDIT = "CREDIT"
    const val HOURS_TRANSFER = "HOURS_TRANSFER"
    const val CANCELLATION = "CANCELLATION"
    const val BASELINE = "BASELINE"
    const val CLASSIFICATION = "CLASSIFICATION"
    const val CORRECTION = "CORRECTION"
    const val WRITE_OFF = "WRITE_OFF"
    const val RETENTION = "RETENTION"
    const val ADJUSTMENT = "ADJUSTMENT"

    /** Notification target entity -> decision kind (backend notification rules). */
    val BY_ENTITY = mapOf(
        "customer_discount" to DISCOUNT,
        "credit_arrangement" to CREDIT,
        "hours_transfer" to HOURS_TRANSFER,
        "hours_cancellation" to CANCELLATION,
        "baseline" to BASELINE,
        "meter_baseline" to BASELINE,
        "classification" to CLASSIFICATION,
        "correction" to CORRECTION,
        "meter_correction" to CORRECTION,
        "cash_variance" to WRITE_OFF,
        "cash_retention" to RETENTION,
        "custody_adjustment" to ADJUSTMENT,
    )
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

    fun fromTarget(entity: String?, id: String?, path: String?, notificationId: String? = null, type: String? = null): OwnerDestination {
        val target = id(id)
        // A cash difference just opened is not a decision yet: it is reviewed from Approvals (cash write-offs).
        if (type == "CASH_VARIANCE_OPENED") return OwnerDestination.Approvals()
        DecisionKinds.BY_ENTITY[entity]?.let { kind -> return target?.let { OwnerDestination.Decision(kind, it) } ?: OwnerDestination.Approvals() }
        return when (entity) {
            "alert" -> OwnerDestination.Alerts(target)
            "approval" -> OwnerDestination.Approvals(target)
            "meter_reset" -> target?.let { OwnerDestination.MeterReset(it) } ?: OwnerDestination.Approvals()
            "exception" -> OwnerDestination.Exceptions()
            "job" -> target?.let { OwnerDestination.Job(it) } ?: OwnerDestination.Jobs
            "machine", "fleet.position" -> target?.let { OwnerDestination.Machine(it) } ?: OwnerDestination.Fleet
            "case" -> target?.let { OwnerDestination.Case(it) } ?: OwnerDestination.Cases
            // HOURS_OVERRUN: the meter exception to review.
            "job_exception" -> target?.let { OwnerDestination.MeterException(it) } ?: OwnerDestination.Exceptions()
            // PARTIAL_REMITTANCE: the remittance (cash handover).
            "cash_handover" -> target?.let { OwnerDestination.Handover(it) } ?: OwnerDestination.Approvals()
            "cash_transfer", "supervisor_cash_custody" -> OwnerDestination.Cash
            "hours_purchase" -> OwnerDestination.Accountability
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
            "meter-resets" -> second?.let { OwnerDestination.MeterReset(it) } ?: OwnerDestination.Approvals()
            "exceptions" -> OwnerDestination.Exceptions()
            "jobs" -> second?.let { OwnerDestination.Job(it) } ?: OwnerDestination.Jobs
            "cases" -> second?.let { OwnerDestination.Case(it) } ?: OwnerDestination.Cases
            "machines" -> second?.let { OwnerDestination.Machine(it) } ?: OwnerDestination.Fleet
            "fleet" -> id(rest.getOrNull(2))?.let { OwnerDestination.Machine(it) } ?: OwnerDestination.Fleet
            "notifications" -> OwnerDestination.Notifications(second)
            // Accountability (customer hours, engine hours, cash custody chain).
            "hours" -> if (rest.getOrNull(1) == "purchases") OwnerDestination.Accountability else OwnerDestination.Approvals()
            "meter-baselines", "meter-corrections" -> OwnerDestination.Approvals()
            "engine-hours" -> if (rest.getOrNull(1) == "machines") id(rest.getOrNull(2))?.let { OwnerDestination.Machine(it) } ?: OwnerDestination.Fleet
            else OwnerDestination.Approvals()
            "cash" -> when (rest.getOrNull(1)) {
                "transfers", "floats" -> OwnerDestination.Cash
                "handovers" -> id(rest.getOrNull(2))?.let { OwnerDestination.Handover(it) } ?: OwnerDestination.Approvals()
                else -> OwnerDestination.Approvals()
            }
            "accountability" -> OwnerDestination.Accountability
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
