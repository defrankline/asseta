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

    /** Resolving an alert needs a note (the server answers `422 NOTE_REQUIRED` otherwise). */
    fun resolveNoteValid(note: String): Boolean = note.isNotBlank()
}
