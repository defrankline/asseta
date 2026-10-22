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
        "SUBSCRIPTION_READ_ONLY" -> "This company's subscription is read-only, so changes are not accepted right now."
        "PERMISSION_DENIED" -> "You do not have permission to do this."
        "TENANT_ACCESS_DENIED", "TENANT_ACCESS_BLOCKED", "MANDATE_ENDED", "MANDATE_REQUIRED" ->
            "Your access to this company has ended. Its saved data was removed from this device."
        else -> serverMessage
    }

    /** Codes after which the shown list is out of date and must be reloaded. */
    fun needsReload(code: String): Boolean = code == "ALERT_CLOSED" || code == "APPROVAL_ALREADY_DECIDED"
}
