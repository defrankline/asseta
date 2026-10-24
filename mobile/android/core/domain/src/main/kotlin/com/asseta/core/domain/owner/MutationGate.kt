package com.asseta.core.domain.owner

/** The only mutations the Owner app performs. Everything else is read-only by design. */
enum class OwnerAction(val permission: String) {
    ACKNOWLEDGE_ALERT("tenant.fleet.alert_manage"),
    RESOLVE_ALERT("tenant.fleet.alert_manage"),
    DECIDE_APPROVAL("tenant.approval.expense"),
    DECIDE_METER_RESET("tenant.meter.approve"),

    /** Approve (pricing a field request without a rate card) or decline a job waiting for approval. */
    DECIDE_JOB("tenant.job.approve"),

    /** Confirm (verify) or dispute (reject) a cash handover a supervisor claimed. */
    DECIDE_HANDOVER("tenant.finance.verify"),

    /** Record the review of a meter exception (EXPLAINED / CONFIRMED with a note). */
    REVIEW_EXCEPTION("tenant.meter.review"),

    /** Issue a cash float into a supervisor's custody. */
    ISSUE_FLOAT("tenant.finance.cash"),

    /** Create a job and send it for approval (approving it right away also needs [DECIDE_JOB]'s permission). */
    CREATE_JOB("tenant.job.write"),
}

sealed interface MutationCheck {
    data object Allowed : MutationCheck
    data class Blocked(val reason: String) : MutationCheck
}

/**
 * UI gate for owner mutations (the server re-checks everything): blocked while offline or while the screen shows
 * cached data, without the permission from `/me`, or when the tenant is read-only.
 */
object MutationGate {
    fun check(action: OwnerAction, online: Boolean, source: DataSource, permissions: Collection<String>, tenantReadOnly: Boolean): MutationCheck =
        check(online, source, action.permission in permissions, tenantReadOnly)

    /** Same order and wording as the iOS `MutationGuard`: offline, saved data, read-only company, then permission. */
    fun check(online: Boolean, source: DataSource, permitted: Boolean, tenantReadOnly: Boolean): MutationCheck = when {
        !online -> MutationCheck.Blocked(OFFLINE)
        source == DataSource.CACHE -> MutationCheck.Blocked(SHOWING_SAVED_DATA)
        tenantReadOnly -> MutationCheck.Blocked(READ_ONLY_TENANT)
        !permitted -> MutationCheck.Blocked(NOT_PERMITTED)
        else -> MutationCheck.Allowed
    }

    const val OFFLINE = "You're offline. Changes need a connection."
    const val SHOWING_SAVED_DATA = "Showing saved data. Refresh while online before making changes."
    const val READ_ONLY_TENANT = "This company is read-only. Changes are disabled."
    const val NOT_PERMITTED = "Your role can view this but not change it."

    /** A meter reset decision needs a note of at least 5 characters (server `ReviewIn`). */
    fun resetNoteValid(note: String): Boolean = note.trim().length >= RESET_NOTE_MIN

    const val RESET_NOTE_MIN = 5

    /** Resolving an alert needs a note (the server answers `422 NOTE_REQUIRED` otherwise). */
    fun resolveNoteValid(note: String): Boolean = note.isNotBlank()
}
