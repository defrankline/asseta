package com.asseta.core.ui

import androidx.annotation.StringRes

/** Which product shell is running. Only affects labels; permissions always come from the server. */
enum class AppRole(@param:StringRes val label: Int, @param:StringRes val tagline: Int) {
    SUPERVISOR(R.string.role_supervisor, R.string.tagline_supervisor),
    OWNER(R.string.role_owner, R.string.tagline_owner),
}
