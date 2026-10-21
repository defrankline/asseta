package com.asseta.core.sync.engine

/** Wipes everything local after `DEVICE_REVOKED` + `WIPE_LOCAL_DATA` (lost/stolen phone). */
fun interface LocalDataWiper {
    /** [reason] is the user-facing explanation shown on the login screen afterwards. */
    suspend fun wipe(reason: String)
}

/**
 * Production wipe order: stop using and delete the encrypted database, delete evidence files, destroy the database
 * key / evidence key / tokens, then clear the session and post the explanation. Each step runs even if an earlier one
 * fails, so a partial failure never leaves tokens behind.
 */
class DeviceWipe(private val steps: List<(reason: String) -> Unit>) : LocalDataWiper {
    override suspend fun wipe(reason: String) {
        var first: Throwable? = null
        steps.forEach { step -> runCatching { step(reason) }.onFailure { if (first == null) first = it } }
        first?.let { throw it }
    }
}
