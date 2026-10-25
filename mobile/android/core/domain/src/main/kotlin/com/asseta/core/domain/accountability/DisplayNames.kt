package com.asseta.core.domain.accountability

/**
 * Names, not ids (DEC-030 G2): rows and details show the server's display name; only when it is null the first
 * [SHORT] characters of the id stand in (same rule on iOS and the web).
 */
object DisplayNames {
    const val SHORT = 8

    fun shortId(id: String?): String? = id?.takeIf { it.isNotBlank() }?.take(SHORT)

    /** [name] when known, else the short id (null when both are missing). */
    fun of(name: String?, id: String?): String? = name?.takeIf { it.isNotBlank() } ?: shortId(id)

    /** "CODE · Name" for a machine (either part may be missing), else the short id. */
    fun machine(code: String?, name: String?, id: String?): String? =
        listOfNotNull(code?.takeIf { it.isNotBlank() }, name?.takeIf { it.isNotBlank() }).joinToString(" · ").ifEmpty { null } ?: shortId(id)
}
