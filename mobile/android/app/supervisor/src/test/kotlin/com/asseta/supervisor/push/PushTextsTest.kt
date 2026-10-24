package com.asseta.supervisor.push

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** "Notifications on this phone" and the one-time permission prompt, identical on iOS (`PushTextsTests`). */
class PushTextsTest {
    @Test
    fun `the permission is asked once on Android 13 and a refusal stays a refusal`() {
        assertEquals(NotificationPermission.GRANTED, PushTexts.permission(notificationsEnabled = true, sdk = 34, asked = false))
        assertEquals(NotificationPermission.NOT_ASKED, PushTexts.permission(notificationsEnabled = false, sdk = 34, asked = false))
        assertEquals(NotificationPermission.DENIED, PushTexts.permission(notificationsEnabled = false, sdk = 34, asked = true))
        // Below Android 13 notifications are on unless the user turned them off in Settings.
        assertEquals(NotificationPermission.DENIED, PushTexts.permission(notificationsEnabled = false, sdk = 30, asked = false))
    }

    @Test
    fun `account menu status`() {
        assertEquals("Notifications on this phone", PushTexts.ROW)
        assertEquals("Turn on", PushTexts.TURN_ON)
        assertEquals(PhonePushStatus.UNAVAILABLE, PushTexts.status(available = false, registered = true, NotificationPermission.GRANTED))
        assertEquals(PhonePushStatus.OFF, PushTexts.status(available = true, registered = true, NotificationPermission.DENIED))
        assertEquals(PhonePushStatus.ON, PushTexts.status(available = true, registered = true, NotificationPermission.GRANTED))
        assertEquals(PhonePushStatus.NOT_REGISTERED, PushTexts.status(available = true, registered = false, NotificationPermission.GRANTED))
        assertEquals(PhonePushStatus.ON, PushTexts.status(available = true, registered = true, NotificationPermission.NOT_ASKED))
        assertEquals(PhonePushStatus.NOT_REGISTERED, PushTexts.status(available = true, registered = false, NotificationPermission.NOT_ASKED))
        assertEquals(
            listOf("On", "Off — allow notifications in Settings", "Not available on this build", "Not registered yet"),
            PhonePushStatus.entries.map { it.label },
        )
    }

    @Test
    fun `the inbox asks only when push works, the role gets notifications and nobody asked yet`() {
        assertTrue(PushTexts.askOnInbox(available = true, canReadNotifications = true, NotificationPermission.NOT_ASKED))
        assertFalse(PushTexts.askOnInbox(available = false, canReadNotifications = true, NotificationPermission.NOT_ASKED))
        assertFalse(PushTexts.askOnInbox(available = true, canReadNotifications = false, NotificationPermission.NOT_ASKED))
        assertFalse(PushTexts.askOnInbox(available = true, canReadNotifications = true, NotificationPermission.DENIED))
        assertFalse(PushTexts.askOnInbox(available = true, canReadNotifications = true, NotificationPermission.GRANTED))
    }
}
