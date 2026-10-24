package com.asseta.core.domain.owner

/**
 * User-facing wording for the server's stable error codes on owner actions. The server message is kept as the
 * fallback; segregation of duties gets an explicit explanation because it is a control, not a malfunction.
 */
object OwnerErrors {
    fun message(code: String, serverMessage: String): String = when (code) {
        "SEGREGATION_OF_DUTIES" ->
            "Segregation of duties: you cannot decide on a request you submitted or recorded yourself. " +
                "Another authorised person must approve or reject it."
        "NOTE_REQUIRED" -> "Add a note explaining how the alert was resolved."
        "ALERT_CLOSED" -> "This alert was already closed by someone else. The list has been refreshed."
        "APPROVAL_ALREADY_DECIDED" -> "This request was already decided by someone else. The list has been refreshed."
        "RESET_DECIDED" -> RESET_DECIDED
        "PRICE_REQUIRED" -> PRICE_REQUIRED
        "HANDOVER_ALREADY_DECIDED" -> HANDOVER_DECIDED
        "ALREADY_REVIEWED" -> EXCEPTION_REVIEWED
        "NOT_CUSTODIAN" -> "Only office cash staff may record custody for someone else."
        "STAFF_INACTIVE" -> "The staff member is inactive."
        "STAFF_NOT_LINKED" -> "Your login is not linked to a staff record; pick the staff member explicitly."
        "CURRENCY_NOT_CONFIGURED" -> "Choose a configured currency."
        "SUBSCRIPTION_READ_ONLY" -> "This company's subscription is read-only, so changes are not accepted right now."
        "PERMISSION_DENIED" -> "You do not have permission to do this."
        "TENANT_ACCESS_DENIED", "TENANT_ACCESS_BLOCKED", "MANDATE_ENDED", "MANDATE_REQUIRED" ->
            "Your access to this company has ended. Its saved data was removed from this device."
        else -> serverMessage
    }

    /** Wording for a refused meter reset decision: segregation of duties is about the reset's requester. */
    fun meterResetMessage(code: String?, serverMessage: String): String = when (code) {
        "SEGREGATION_OF_DUTIES" -> RESET_SEGREGATION
        "RESET_DECIDED" -> RESET_DECIDED
        null -> serverMessage
        else -> message(code, serverMessage)
    }

    const val RESET_DECIDED = "This reset was already decided."
    const val PRICE_REQUIRED = "Set an hourly rate before approving this job."
    const val HANDOVER_DECIDED = "Someone already decided this handover. Reload to see it."
    const val EXCEPTION_REVIEWED = "Someone else has already reviewed this exception; reload the list."
    const val RESET_SEGREGATION = "You requested this reset, so someone else must decide it."

    /** Codes after which the shown list is out of date and must be reloaded. */
    fun needsReload(code: String): Boolean = code == "ALERT_CLOSED" || code == "APPROVAL_ALREADY_DECIDED" || code == "RESET_DECIDED" ||
        code == "HANDOVER_ALREADY_DECIDED" || code == "ALREADY_REVIEWED"
}
