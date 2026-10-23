package com.asseta.owner

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.hasScrollAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollToNode
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.ui.session.UiError
import com.asseta.core.ui.theme.AssetaTheme
import com.asseta.owner.data.Snapshot
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.approvals.DecisionError
import com.asseta.owner.ui.approvals.SegregationNotice
import com.asseta.owner.ui.common.STALE_BANNER_TAG
import com.asseta.owner.ui.common.StaleBanner
import com.asseta.owner.ui.settings.PushControl
import com.asseta.owner.ui.settings.SettingsScreen
import com.asseta.owner.ui.settings.SettingsViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.time.ZoneOffset

/** Compose UI on Robolectric: stale marking, SoD notice, and offline-disabled settings. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class OwnerComposeTest {
    @get:Rule val compose = createComposeRule()

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun staleBannerOnlyForCachedData() {
        val ms = java.time.Instant.parse("2026-10-21T14:05:00Z").toEpochMilli()
        compose.setContent {
            AssetaTheme {
                StaleBanner(Snapshot(Unit, ms, DataSource.CACHE), ZoneOffset.UTC)
                StaleBanner(Snapshot(Unit, ms, DataSource.LIVE), ZoneOffset.UTC)
            }
        }
        compose.onNodeWithTag(STALE_BANNER_TAG).assertIsDisplayed()
        compose.onNodeWithText("Offline — data from 21 Oct 2026, 14:05 (stale)").assertIsDisplayed()
    }

    @Test
    fun segregationOfDutiesIsExplained() {
        compose.setContent {
            AssetaTheme { SegregationNotice(DecisionError(ID1, UiError("Another authorised person must approve it.", "cid-9"), "SEGREGATION_OF_DUTIES")) }
        }
        compose.onNodeWithText("Not allowed: segregation of duties").assertIsDisplayed()
        compose.onNodeWithText("Reference: cid-9").assertIsDisplayed()
    }

    @Test
    fun settingsActionsDisabledOffline() {
        Dispatchers.setMain(Dispatchers.Unconfined)
        val h = OwnerHarness()
        h.goOffline()
        val vm = SettingsViewModel(h.data, object : PushControl {
            override val available = true
            override val providerName = "Test"
            override suspend fun register() = null
        })
        val session = OwnerSession(TENANT, "Acme", setOf("tenant.notification.read"), readOnly = false)
        compose.setContent { AssetaTheme { SettingsScreen(vm, session, online = false) } }
        compose.onNodeWithText("You're offline. Changes need a connection.").assertIsDisplayed()
        compose.onNodeWithText("Enable push notifications").assertIsNotEnabled()
        compose.onNodeWithText("Save").assertIsNotEnabled()
        compose.onNode(hasScrollAction()).performScrollToNode(hasText("Change password"))
        compose.onNodeWithText("Change password").assertIsNotEnabled()
        compose.onNodeWithText("Connect to the internet to change your password.").assertExists()
    }
}
