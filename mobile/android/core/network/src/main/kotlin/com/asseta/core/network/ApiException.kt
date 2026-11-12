package com.asseta.core.network

import com.asseta.core.model.ErrorDetail
import java.io.IOException

/**
 * Typed failure for any non-2xx API response. Extends IOException so it propagates correctly through
 * OkHttp interceptors and Retrofit suspend calls.
 */
class ApiException(
    val httpStatus: Int,
    val code: String,
    override val message: String,
    val correlationId: String?,
    val details: List<ErrorDetail> = emptyList(),
) : IOException("$httpStatus $code: $message") {
    val isUnauthenticated: Boolean get() = httpStatus == 401
    val isForbidden: Boolean get() = httpStatus == 403
    val isConflict: Boolean get() = httpStatus == 409

    /** The account was deleted or disabled: every token of it is refused. */
    val isUserInactive: Boolean get() = httpStatus == 403 && code == USER_INACTIVE

    /** 5xx, 408 and 429 may be retried with backoff; 4xx business/validation errors may not. */
    val isRetryable: Boolean get() = httpStatus >= 500 || httpStatus == 408 || httpStatus == 429

    companion object {
        const val USER_INACTIVE = "USER_INACTIVE"
    }
}
