package com.asseta.owner.data

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.FailureKind
import com.asseta.core.ui.session.UiError

/** Data shown on a screen with its provenance; [source] CACHE means offline and stale. */
data class Snapshot<out T>(val data: T, val fetchedAtMs: Long, val source: DataSource) {
    val stale: Boolean get() = source == DataSource.CACHE
}

sealed interface Load<out T> {
    data class Ok<T>(val snapshot: Snapshot<T>) : Load<T>
    data class Failed(val error: UiError, val kind: FailureKind) : Load<Nothing>
}

/** Result of an owner mutation (acknowledge/resolve alert, approval decision, settings). */
sealed interface ActionResult<out T> {
    data class Done<T>(val value: T) : ActionResult<T>
    data class Refused(val error: UiError, val code: String?, val reload: Boolean = false) : ActionResult<Nothing>
}
