package com.asseta.core.ui.session

import com.asseta.core.model.TenantAccess
import com.asseta.core.network.ApiException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.IOException

/**
 * "Delete my account" wording (docs/requirements/accountability-mobile-strings.md "Account deletion"; identical on
 * iOS `AccountDeletionText`).
 */
object AccountDeletionText {
    const val ACTION = "Delete my account"
    const val TITLE = "Delete my account"
    const val EXPLAIN = "Your login is deleted for good. Your name and email are removed; your records stay with the " +
        "company under an anonymous name. This cannot be undone."
    const val REASON_LABEL = "Reason (optional)"
    const val TYPE_LABEL = "Type DELETE to confirm"
    const val CONFIRM_WORD = "DELETE"
    const val SUBMIT = "Delete my account"
    const val FINAL_TITLE = "Delete your account for good?"
    const val FINAL_MESSAGE = "You will be signed out and this phone's saved data is erased. This cannot be undone."
    const val FINAL_ACTION = "Delete for good"
    const val DELETING = "Deleting…"
    const val OFFLINE = "Connect to the internet to delete your account."
    const val UNSYNCED_TITLE = "Records not yet sent will be lost"
    const val SYNC_FIRST = "Sync first"
    const val DELETE_ANYWAY = "Delete anyway"
    const val SYNCING = "Syncing…"
    const val DELETED = "Your account was deleted."
    const val INACTIVE = "This account was deleted or disabled."
    const val PLATFORM_ACCOUNT = "Platform accounts are removed by the platform owner."
    const val NETWORK = "Cannot reach Asseta. Check your connection and try again."

    fun unsyncedMessage(count: Int): String =
        "$count item(s) on this phone are not synced yet. If you delete your account now they are lost. Sync first to send them."

    /** LAST_OWNER: the server's message (it names the companies); PLATFORM_ACCOUNT: ours; offline: the connection text. */
    fun error(t: Throwable): String = when {
        t is ApiException && t.code == "LAST_OWNER" -> t.message
        t is ApiException && t.code == "PLATFORM_ACCOUNT" -> PLATFORM_ACCOUNT
        t is ApiException -> t.message
        t is IOException -> NETWORK
        else -> t.message ?: NETWORK
    }
}

/** The company-closure banner: the selected company's `access_state_reason` (e.g. a requested closure), else none. */
object CompanyNotice {
    /** Permission to see (and cancel) the company's closure request. */
    const val CLOSE_PERMISSION = "tenant.company.close"

    fun banner(tenant: TenantAccess?): String? = tenant?.accessStateReason?.trim()?.takeIf { it.isNotEmpty() }

    /** Owner app: the banner opens the closure request for holders of [CLOSE_PERMISSION]. */
    fun opensClosure(tenant: TenantAccess?): Boolean = banner(tenant) != null && CLOSE_PERMISSION in tenant!!.permissions
}

/** Where the "Delete my account" screen is. */
sealed interface DeletionStep {
    data object Form : DeletionStep
    /** This phone has [count] of the user's records not sent yet: sync first, delete anyway or cancel. */
    data class Unsynced(val count: Int) : DeletionStep
    data object Syncing : DeletionStep
    /** The last question before the call. */
    data object Confirm : DeletionStep
    data object Deleting : DeletionStep
    /** Deleted: the session is ending (the login screen shows [AccountDeletionText.DELETED]). */
    data object Done : DeletionStep
}

data class AccountDeletionUi(
    val step: DeletionStep = DeletionStep.Form,
    val reason: String = "",
    val typed: String = "",
    val error: String? = null,
) {
    val confirmed: Boolean get() = typed.trim() == AccountDeletionText.CONFIRM_WORD
}

/**
 * The deletion flow (same steps on iOS): typed DELETE -> unsynced warning when this phone holds the user's unsent work
 * (sync first or delete anyway) -> final confirmation -> `POST /me/account-deletion` -> [onDeleted] (wipe and sign
 * out). Online only: offline nothing is sent. A refusal returns to the form with its message.
 */
class AccountDeletionFlow(
    private val online: () -> Boolean,
    private val unsyncedCount: suspend () -> Int,
    private val syncNow: suspend () -> Unit,
    private val delete: suspend (reason: String?) -> Unit,
    private val onDeleted: suspend () -> Unit,
) {
    private val _ui = MutableStateFlow(AccountDeletionUi())
    val ui: StateFlow<AccountDeletionUi> = _ui.asStateFlow()

    fun setReason(value: String) = _ui.update { it.copy(reason = value.take(MAX_REASON)) }
    fun setTyped(value: String) = _ui.update { it.copy(typed = value, error = null) }

    fun canSubmit(isOnline: Boolean): Boolean = isOnline && _ui.value.confirmed && _ui.value.step == DeletionStep.Form

    /** "Delete my account" on the form. */
    suspend fun submit() {
        val ui = _ui.value
        if (ui.step != DeletionStep.Form || !ui.confirmed) return
        if (!online()) return _ui.update { it.copy(error = AccountDeletionText.OFFLINE) }
        _ui.update { it.copy(error = null) }
        checkUnsynced()
    }

    /** Unsynced warning: send the records first, then ask again if anything is still waiting. */
    suspend fun syncFirst() {
        if (_ui.value.step !is DeletionStep.Unsynced) return
        _ui.update { it.copy(step = DeletionStep.Syncing) }
        runCatching { syncNow() }.onFailure { if (it is CancellationException) throw it }
        checkUnsynced()
    }

    fun deleteAnyway() {
        if (_ui.value.step is DeletionStep.Unsynced) _ui.update { it.copy(step = DeletionStep.Confirm) }
    }

    /** Closes the warning or the final question; back to the form. */
    fun dismiss() {
        if (_ui.value.step is DeletionStep.Unsynced || _ui.value.step == DeletionStep.Confirm) _ui.update { it.copy(step = DeletionStep.Form) }
    }

    /** "Delete for good". */
    suspend fun confirm() {
        if (_ui.value.step != DeletionStep.Confirm) return
        if (!online()) return _ui.update { it.copy(step = DeletionStep.Form, error = AccountDeletionText.OFFLINE) }
        _ui.update { it.copy(step = DeletionStep.Deleting, error = null) }
        try {
            delete(_ui.value.reason.trim().ifEmpty { null })
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            _ui.update { it.copy(step = DeletionStep.Form, error = AccountDeletionText.error(e)) }
            return
        }
        _ui.update { it.copy(step = DeletionStep.Done) }
        onDeleted()
    }

    private suspend fun checkUnsynced() {
        val count = runCatching { unsyncedCount() }.getOrDefault(0)
        _ui.update { it.copy(step = if (count > 0) DeletionStep.Unsynced(count) else DeletionStep.Confirm) }
    }

    private companion object {
        const val MAX_REASON = 1000
    }
}
