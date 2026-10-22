package com.asseta.core.domain.owner

/** One cell of the push matrix (category x severity). [locked] when PUSH is a mandatory channel for that cell. */
data class PushCell(val category: String, val severity: String, val push: Boolean, val email: Boolean, val locked: Boolean)

/**
 * Configurable priority notifications: the user's push routing per category x severity. Edits produce the minimal
 * change list for `PUT /tenant/notification-routing` (email is sent back unchanged); mandatory cells cannot change.
 */
object NotificationMatrix {
    val SEVERITIES = listOf("CRITICAL", "WARNING", "INFO")
    val CATEGORY_ORDER = listOf("ACTION", "ANOMALY", "REMINDER", "BILLING", "INFO")

    fun sorted(cells: List<PushCell>): List<PushCell> = cells.sortedWith(
        compareBy<PushCell>({ CATEGORY_ORDER.indexOf(it.category).let { i -> if (i < 0) Int.MAX_VALUE else i } }, { it.category })
            .thenBy { SEVERITIES.indexOf(it.severity).let { i -> if (i < 0) Int.MAX_VALUE else i } },
    )

    fun toggle(cells: List<PushCell>, category: String, severity: String, push: Boolean): List<PushCell> =
        cells.map { if (it.category == category && it.severity == severity && !it.locked) it.copy(push = push) else it }

    /** Cells whose push flag differs from [original]. */
    fun changes(original: List<PushCell>, edited: List<PushCell>): List<PushCell> {
        val before = original.associateBy { it.category to it.severity }
        return edited.filter { e -> before[e.category to e.severity]?.let { it.push != e.push } == true }
    }
}
