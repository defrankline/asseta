package com.asseta.supervisor.push

/** The phone's notification permission: granted, never asked (Android 13+), or refused / turned off in Settings. */
enum class NotificationPermission { GRANTED, NOT_ASKED, DENIED }

/** "Notifications on this phone" in the account menu, word for word the iOS wording. */
enum class PhonePushStatus(val label: String) {
    ON("On"),
    OFF("Off — allow notifications in Settings"),
    UNAVAILABLE("Not available on this build"),
    NOT_REGISTERED("Not registered yet"),
}

/** Pure push rules of the Supervisor app (permission state, account-menu status, when to ask), unit-tested. */
object PushTexts {
    const val ROW = "Notifications on this phone"
    const val TURN_ON = "Turn on"

    /** Below Android 13 there is no runtime prompt: notifications off means the user turned them off in Settings. */
    fun permission(notificationsEnabled: Boolean, sdk: Int, asked: Boolean): NotificationPermission = when {
        notificationsEnabled -> NotificationPermission.GRANTED
        sdk < 33 || asked -> NotificationPermission.DENIED
        else -> NotificationPermission.NOT_ASKED
    }

    /** Unavailable wins, then a refused permission, then a registration; anything else is not registered yet. */
    fun status(available: Boolean, registered: Boolean, permission: NotificationPermission): PhonePushStatus = when {
        !available -> PhonePushStatus.UNAVAILABLE
        permission == NotificationPermission.DENIED -> PhonePushStatus.OFF
        registered -> PhonePushStatus.ON
        else -> PhonePushStatus.NOT_REGISTERED
    }

    /** The Inbox asks once (Android 13+), when push works on this build and the role receives notifications. */
    fun askOnInbox(available: Boolean, canReadNotifications: Boolean, permission: NotificationPermission): Boolean =
        available && canReadNotifications && permission == NotificationPermission.NOT_ASKED
}
