package com.asseta.core.model

/**
 * Lifecycle of a locally captured operation in the offline outbox.
 * An operation is only ACKED after a durable server acknowledgement; nothing is "synced" before that.
 */
enum class ClientOperationStatus {
    PENDING,
    SENT,
    ACKED,
    FAILED,
    QUARANTINED,
}
