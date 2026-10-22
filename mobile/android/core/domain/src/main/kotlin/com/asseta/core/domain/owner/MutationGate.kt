package com.asseta.core.domain.owner

/** The only mutations the Owner app performs. Everything else is read-only by design. */
enum class OwnerAction(val permission: String) {
    ACKNOWLEDGE_ALERT("tenant.fleet.alert_manage"),
    RESOLVE_ALERT("tenant.fleet.alert_manage"),
    DECIDE_APPROVAL("tenant.approval.expense"),
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
    fun check(action: OwnerAction, online: Boolean, source: DataSource, permissions: Collection<String>, tenantReadOnly: Boolean): MutationCheck = when {
        !online || source == DataSource.CACHE -> MutationCheck.Blocked("Offline: actions are disabled while showing saved data.")
        action.permission !in permissions -> MutationCheck.Blocked("You do not have permission to do this.")
        tenantReadOnly -> MutationCheck.Blocked("This company is read-only. Actions are disabled.")
        else -> MutationCheck.Allowed
    }

    /** Resolving an alert needs a note (the server answers `422 NOTE_REQUIRED` otherwise). */
    fun resolveNoteValid(note: String): Boolean = note.isNotBlank()
}
