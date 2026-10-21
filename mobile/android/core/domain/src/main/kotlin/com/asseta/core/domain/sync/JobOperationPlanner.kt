package com.asseta.core.domain.sync

import com.asseta.core.model.ClientOperationStatus

/** Field operation kinds on one job, in workflow order. */
enum class JobOpKind { OPENING_CAPTURE, START, ACTIVITY, CLOSING_CAPTURE, ACKNOWLEDGEMENT, COMPLETE }

data class LocalJobOp(val id: String, val kind: JobOpKind, val status: ClientOperationStatus, val createdAtMs: Long)

/**
 * Dependency chain for a job: opening capture -> START -> activities / closing capture -> acknowledgement -> COMPLETE.
 * Server-side the same order is enforced (DEFERRED until parents are ACKED). Ops the server rejected or flagged as
 * conflicts are ignored, so a re-captured reading becomes the new parent.
 */
object JobOperationPlanner {
    const val MAX_DEPENDENCIES = 20 // OperationIn.depends_on maxItems

    fun dependenciesFor(kind: JobOpKind, existing: List<LocalJobOp>): List<String> {
        val live = existing.filter { it.status != ClientOperationStatus.FAILED && it.status != ClientOperationStatus.CONFLICT }
        fun latest(k: JobOpKind) = live.filter { it.kind == k }.maxByOrNull { it.createdAtMs }?.id
        val deps = when (kind) {
            JobOpKind.OPENING_CAPTURE -> emptyList()
            JobOpKind.START -> listOfNotNull(latest(JobOpKind.OPENING_CAPTURE))
            JobOpKind.ACTIVITY, JobOpKind.CLOSING_CAPTURE -> listOfNotNull(latest(JobOpKind.START))
            JobOpKind.ACKNOWLEDGEMENT -> listOfNotNull(latest(JobOpKind.CLOSING_CAPTURE))
            JobOpKind.COMPLETE -> {
                val required = listOfNotNull(latest(JobOpKind.CLOSING_CAPTURE), latest(JobOpKind.ACKNOWLEDGEMENT))
                val activities = live.filter { it.kind == JobOpKind.ACTIVITY && it.status != ClientOperationStatus.ACKED }
                    .sortedByDescending { it.createdAtMs }.map { it.id }
                required + activities.take(MAX_DEPENDENCIES - required.size)
            }
        }
        return deps.distinct()
    }

    fun hasLive(kind: JobOpKind, existing: List<LocalJobOp>): Boolean =
        existing.any { it.kind == kind && it.status != ClientOperationStatus.FAILED && it.status != ClientOperationStatus.CONFLICT }
}
