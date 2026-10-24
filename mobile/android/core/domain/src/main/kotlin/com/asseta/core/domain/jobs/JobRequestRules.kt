package com.asseta.core.domain.jobs

import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.model.ClientOperationStatus

/**
 * A supervisor's job request from the field (`JOB_REQUEST`): what the form must contain, and how a request shows in the
 * Jobs list until the owner decides it. Same rules and wording as the iOS app.
 */
object JobRequestRules {
    const val NOTE_MAX = 1000

    /** Days an accepted request whose job is not on the phone yet keeps showing (the server's recently-closed window). */
    const val SHOW_ACCEPTED_DAYS = 14L

    /** Problems with the form, in field order (empty when it can be sent). */
    fun validate(contractId: String?, machineId: String?, plannedStartMs: Long, plannedEndMs: Long?, note: String): List<String> = buildList {
        if (contractId.isNullOrBlank()) add("Choose the customer contract.")
        if (machineId.isNullOrBlank()) add("Choose the machine.")
        if (plannedEndMs != null && plannedEndMs < plannedStartMs) add("The planned end is before the planned start.")
        if (note.trim().length > NOTE_MAX) add("What the customer asked for: at most $NOTE_MAX characters.")
    }

    /** Where a request stands, from its outbox operation and (once on the phone) the server's job. */
    fun state(operation: ClientOperationStatus?, serverJobStatus: String?): JobRequestState = when {
        serverJobStatus == JobStatus.CANCELLED -> JobRequestState.DECLINED
        serverJobStatus == PENDING_APPROVAL -> JobRequestState.WAITING
        serverJobStatus != null -> JobRequestState.DECIDED
        operation == null -> JobRequestState.DECIDED
        operation == ClientOperationStatus.ACKED -> JobRequestState.WAITING
        operation == ClientOperationStatus.PENDING || operation == ClientOperationStatus.SENT -> JobRequestState.NOT_SENT
        else -> JobRequestState.PROBLEM
    }

    const val PENDING_APPROVAL = "PENDING_APPROVAL"
}

enum class JobRequestState {
    /** Saved on this phone, not accepted by the server yet. */
    NOT_SENT,

    /** Accepted by the server, waiting for the owner. */
    WAITING,

    /** The owner declined it (the job was cancelled). */
    DECLINED,

    /** The server refused the request (see the sync status screen). */
    PROBLEM,

    /** Approved (or further along): shown like any other job. */
    DECIDED,
}
