package com.asseta.core.model

/**
 * The signed-in user that owns this phone's field data for a tenant: [subject] is the Keycloak `sub` of the ID token
 * (stable per user), [label] a readable name for the sync screen (email or username; never used for decisions).
 * Local sync state, outbox operations and evidence files are recorded with their owner, so another user signing in on
 * the same phone gets a fresh bootstrap and never sees, or sends under their own token, the previous user's work.
 */
data class SyncAccount(val subject: String, val label: String? = null) {
    companion object {
        /** Owner of rows written before owners were recorded when no user was signed in at the upgrade. */
        const val UNKNOWN_SUBJECT = "unknown"
    }
}
