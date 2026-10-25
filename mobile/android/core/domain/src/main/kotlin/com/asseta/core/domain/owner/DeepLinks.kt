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

    /** One cash transfer or float ([kind] [RecordKinds.CASH_TRANSFER] / [RecordKinds.CASH_FLOAT]), read-only. */
    data class CashRecord(val kind: String, val id: String) : OwnerDestination

    /** Overdue remittances flagged today ([id] null) or one flag (REMITTANCE_OVERDUE). */
    data class RemittanceOverdue(val id: String? = null) : OwnerDestination
}

/**
 * Accountability record kinds carried by notifications (`data.kind` + `data.record_id`; push `kind` / `record_id`),
 * one per record with its own detail screen (backend notification rules RECORDS).
 */
object RecordKinds {
    const val CASH_TRANSFER = "CASH_TRANSFER"
    const val CASH_FLOAT = "CASH_FLOAT"
    const val CASH_VARIANCE = "CASH_VARIANCE"
    const val CASH_RETENTION = "CASH_RETENTION"
    const val CUSTODY_ADJUSTMENT = "CUSTODY_ADJUSTMENT"
    const val CASH_REMITTANCE = "CASH_REMITTANCE"
    const val REMITTANCE_OVERDUE = "REMITTANCE_OVERDUE"
    const val HOURS_DISCOUNT = "HOURS_DISCOUNT"
    const val HOURS_CREDIT = "HOURS_CREDIT"
    const val HOURS_TRANSFER = "HOURS_TRANSFER"
    const val HOURS_CANCELLATION = "HOURS_CANCELLATION"
    const val METER_BASELINE = "METER_BASELINE"
    const val METER_CORRECTION = "METER_CORRECTION"
    const val ENGINE_HOURS_CLASSIFICATION = "ENGINE_HOURS_CLASSIFICATION"

    /** Record kind -> the decision kind whose screen shows it (and decides it while it waits). */
    val DECISIONS = mapOf(
        CASH_VARIANCE to DecisionKinds.WRITE_OFF,
        CASH_RETENTION to DecisionKinds.RETENTION,
        CUSTODY_ADJUSTMENT to DecisionKinds.ADJUSTMENT,
        HOURS_DISCOUNT to DecisionKinds.DISCOUNT,
        HOURS_CREDIT to DecisionKinds.CREDIT,
        HOURS_TRANSFER to DecisionKinds.HOURS_TRANSFER,
        HOURS_CANCELLATION to DecisionKinds.CANCELLATION,
        METER_BASELINE to DecisionKinds.BASELINE,
        METER_CORRECTION to DecisionKinds.CORRECTION,
        ENGINE_HOURS_CLASSIFICATION to DecisionKinds.CLASSIFICATION,
    )

    /** Web detail route segment(s) -> record kind (`/tenant/finance/cash/<segment>/<id>`, `/tenant/hours/<segment>/<id>`). */
    val CASH_SEGMENTS = mapOf(
        "transfers" to CASH_TRANSFER, "floats" to CASH_FLOAT, "variances" to CASH_VARIANCE, "retentions" to CASH_RETENTION,
        "adjustments" to CUSTODY_ADJUSTMENT, "remittances" to CASH_REMITTANCE, "remittance-overdue" to REMITTANCE_OVERDUE,
    )
    val HOURS_SEGMENTS = mapOf(
        "discounts" to HOURS_DISCOUNT, "credit" to HOURS_CREDIT, "transfers" to HOURS_TRANSFER, "cancellations" to HOURS_CANCELLATION,
    )

    /** The Owner screen of record [kind] [id], or null for a kind the app does not know (the caller falls back). */
    fun destination(kind: String?, id: String?): OwnerDestination? {
        if (kind == null || id == null) return null
        DECISIONS[kind]?.let { return OwnerDestination.Decision(it, id) }
        return when (kind) {
            CASH_TRANSFER, CASH_FLOAT -> OwnerDestination.CashRecord(kind, id)
            CASH_REMITTANCE -> OwnerDestination.Handover(id)
            REMITTANCE_OVERDUE -> OwnerDestination.RemittanceOverdue(id)
            else -> null
        }
    }
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

    /**
     * [kind] / [recordId] (notification `data`, DEC-030 G5) name the exact record and win; otherwise the target
     * entity, then the link path, then the notification itself.
     */
    fun fromTarget(
        entity: String?,
        id: String?,
        path: String?,
        notificationId: String? = null,
        type: String? = null,
        kind: String? = null,
        recordId: String? = null,
    ): OwnerDestination {
        RecordKinds.destination(kind, id(recordId))?.let { return it }
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
            "cash_transfer" -> target?.let { OwnerDestination.CashRecord(RecordKinds.CASH_TRANSFER, it) } ?: OwnerDestination.Cash
            "supervisor_cash_custody" -> target?.let { OwnerDestination.CashRecord(RecordKinds.CASH_FLOAT, it) } ?: OwnerDestination.Cash
            "cash_remittance_overdue" -> OwnerDestination.RemittanceOverdue(target)
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
            "hours" -> when (val segment = rest.getOrNull(1)) {
                "purchases" -> OwnerDestination.Accountability
                else -> RecordKinds.destination(RecordKinds.HOURS_SEGMENTS[segment], id(rest.getOrNull(2))) ?: OwnerDestination.Approvals()
            }
            "meter-baselines" -> RecordKinds.destination(RecordKinds.METER_BASELINE, second) ?: OwnerDestination.Approvals()
            "meter-corrections" -> RecordKinds.destination(RecordKinds.METER_CORRECTION, second) ?: OwnerDestination.Approvals()
            "engine-hours" -> when (rest.getOrNull(1)) {
                "machines" -> id(rest.getOrNull(2))?.let { OwnerDestination.Machine(it) } ?: OwnerDestination.Fleet
                "classifications" -> RecordKinds.destination(RecordKinds.ENGINE_HOURS_CLASSIFICATION, id(rest.getOrNull(2))) ?: OwnerDestination.Approvals()
                else -> OwnerDestination.Approvals()
            }
            // Web console detail routes of the cash custody chain: /tenant/finance/cash/<segment>/<id>.
            "finance" -> if (rest.getOrNull(1) == "cash") cashPath(rest.getOrNull(2), id(rest.getOrNull(3))) else null
            "cash" -> when (rest.getOrNull(1)) {
                "handovers" -> id(rest.getOrNull(2))?.let { OwnerDestination.Handover(it) } ?: OwnerDestination.Approvals()
                else -> cashPath(rest.getOrNull(1), id(rest.getOrNull(2)))
            }
            "accountability" -> OwnerDestination.Accountability
            else -> null
        }
    }

    /** A cash custody segment (`transfers`, `floats`, `variances`, ...) and record id; the list when unknown. */
    private fun cashPath(segment: String?, recordId: String?): OwnerDestination {
        val kind = RecordKinds.CASH_SEGMENTS[segment]
        RecordKinds.destination(kind, recordId)?.let { return it }
        return when (kind) {
            RecordKinds.CASH_TRANSFER, RecordKinds.CASH_FLOAT -> OwnerDestination.Cash
            RecordKinds.REMITTANCE_OVERDUE -> OwnerDestination.RemittanceOverdue()
            else -> OwnerDestination.Approvals()
        }
    }

    /**
     * Push data map from FCM (`notification_id`, `type`, `severity`, `tenant_id`, `link`, and for a record `entity`,
     * `entity_id`, `kind`, `record_id`). The exact record wins over the link. Null when not ours.
     */
    fun fromPush(data: Map<String, String?>): DeepLink? {
        val notificationId = id(data["notification_id"])
        val link = data["link"]
        val record = RecordKinds.destination(data["kind"], id(data["record_id"]))
        if (notificationId == null && link.isNullOrBlank() && record == null) return null
        val destination = record ?: fromPath(link) ?: OwnerDestination.Notifications(notificationId)
        return DeepLink(destination, id(data["tenant_id"]), notificationId)
    }
}
