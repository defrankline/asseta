package com.asseta.core.model

/**
 * Lifecycle of a locally captured operation in the offline outbox.
 * An operation is only ACKED after a durable server acknowledgement; nothing is "synced" before that.
 *
 * PENDING: waiting to be sent (also after DEFERRED and network/5xx failures). SENT: in flight. ACKED: durable server
 * ACK (or DUPLICATE of an applied op). FAILED: REJECTED by the server (error code kept, not resent automatically).
 * CONFLICT: server state conflict (server_state kept, never auto-overwritten). QUARANTINED: stored but held while the
 * subscription is read-only; resent later until applied.
 */
enum class ClientOperationStatus {
    PENDING,
    SENT,
    ACKED,
    FAILED,
    QUARANTINED,
    CONFLICT,
}
