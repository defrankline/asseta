package com.asseta.core.domain.accountability

/**
 * Names, not ids (DEC-030 G2): rows and details show the server's display name; only when it is null the first
 * [SHORT] characters of the id stand in (same rule on iOS and the web).
 */
object DisplayNames {
    const val SHORT = 8

    /** Shown when neither a name nor an id is known. */
    const val NONE = "—"

    private fun clean(text: String?): String? = text?.trim()?.takeIf { it.isNotEmpty() }

    /** The first [SHORT] characters of the id, lower case. */
    fun shortId(id: String?): String? = clean(id)?.take(SHORT)?.lowercase()

    /** [name] when known, else the short id (null when both are missing: a missing person or record is left out). */
    fun of(name: String?, id: String?): String? = clean(name) ?: shortId(id)

    /** [name] when known, else the short id, never empty (iOS `DisplayName.or`). */
    fun or(name: String?, id: String?): String = of(name, id) ?: NONE

    /** "CODE · Name" for a machine (either part may be missing), else the short id. */
    fun machine(code: String?, name: String?, id: String?): String? =
        listOfNotNull(clean(code), clean(name)).joinToString(" · ").ifEmpty { null } ?: shortId(id)
}
