package com.asseta.owner

import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.PushDeviceDto
import com.asseta.owner.ui.alerts.AlertsViewModel
import com.asseta.owner.ui.approvals.ApprovalsViewModel
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.home.HomeViewModel
import com.asseta.owner.ui.notifications.NotificationsViewModel
import com.asseta.owner.ui.settings.PushControl
import com.asseta.owner.ui.settings.SettingsViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ViewModelTest {
    private val h = OwnerHarness()

    @Before
    fun setUp() = Dispatchers.setMain(Dispatchers.Unconfined)

    @After
    fun tearDown() {
        Dispatchers.resetMain()
        h.close()
    }

    private fun <T> StateFlow<ScreenState<T>>.settled(): ScreenState<T> = runBlocking { withTimeout(5_000) { first { !it.loading } } }

    private fun <T> StateFlow<T>.await(predicate: (T) -> Boolean): T = runBlocking { withTimeout(5_000) { first(predicate) } }

    @Test
    fun `home shows the stale cached overview after a refresh while offline`() {
        h.ok(Samples.OVERVIEW)
        val vm = HomeViewModel(h.data, emptyFlow())
        assertEquals(false, vm.state.settled().stale)
        h.goOffline()
        vm.refresh()
        val s = vm.state.await { !it.loading && it.stale }
        assertEquals(1, s.data!!.work!!.pendingApprovals)
        assertNull(s.error)
    }

    @Test
    fun `refresh trigger reloads the screen`() {
        val trigger = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
        h.ok(Samples.page(Samples.alert()))
        h.ok(Samples.page(Samples.alert(), Samples.alert(ID2)))
        val vm = AlertsViewModel(h.data, null, trigger)
        assertEquals(1, vm.state.settled().data!!.items.size)
        trigger.tryEmit(Unit)
        assertEquals(2, vm.state.await { it.data?.items?.size == 2 }.data!!.items.size)
    }

    @Test
    fun `acknowledging an alert updates the row in place`() {
        h.ok(Samples.page(Samples.alert()))
        val vm = AlertsViewModel(h.data, null, emptyFlow())
        vm.state.settled()
        h.ok(Samples.alert(status = "ACKNOWLEDGED"))
        vm.acknowledge(ID1)
        val s = vm.state.await { it.data?.items?.first()?.status == "ACKNOWLEDGED" }
        assertEquals("ACKNOWLEDGED", s.data!!.items.first().status)
        assertEquals("Alert acknowledged.", vm.message.await { it != null })
    }

    @Test
    fun `resolve without note is refused locally`() {
        h.ok(Samples.page(Samples.alert()))
        val vm = AlertsViewModel(h.data, null, emptyFlow())
        vm.state.settled()
        vm.resolve(ID1, "  ")
        assertEquals("Add a note explaining how the alert was resolved.", vm.message.value)
        assertEquals(1, h.server.requestCount) // only the list load
    }

    @Test
    fun `alert closed elsewhere reloads the list`() {
        h.ok(Samples.page(Samples.alert()))
        val vm = AlertsViewModel(h.data, null, emptyFlow())
        vm.state.settled()
        h.error(409, "ALERT_CLOSED")
        h.ok(Samples.page(Samples.alert(status = "RESOLVED")))
        vm.acknowledge(ID1)
        vm.state.await { it.data?.items?.first()?.status == "RESOLVED" }
        assertTrue(vm.message.value!!.contains("already closed"))
    }

    @Test
    fun `segregation of duties error is attached to the request`() {
        h.ok(Samples.page(Samples.approval()))
        val vm = ApprovalsViewModel(h.data, null, emptyFlow())
        vm.state.settled()
        h.error(422, "SEGREGATION_OF_DUTIES")
        vm.decide(ID1, approve = true, note = null)
        val e = vm.error.await { it != null }!!
        assertEquals(ID1, e.approvalId)
        assertTrue(e.segregationOfDuties)
        assertEquals("PENDING", vm.state.value.data!!.items.first().status)
    }

    @Test
    fun `approval decision replaces the request`() {
        h.ok(Samples.page(Samples.approval()))
        val vm = ApprovalsViewModel(h.data, null, emptyFlow())
        vm.state.settled()
        h.ok(Samples.approval(status = "REJECTED"))
        vm.decide(ID1, approve = false, note = "No receipt")
        vm.state.await { it.data?.items?.first()?.status == "REJECTED" }
        assertEquals("Rejected.", vm.message.await { it != null })
    }

    @Test
    fun `live notification is prepended once and routes to its target`() {
        h.ok(Samples.page(Samples.notification(ID1, read = true)))
        val vm = NotificationsViewModel(h.data, null, emptyFlow())
        vm.state.settled()
        val n = com.asseta.core.network.NetworkFactory.json.decodeFromString(com.asseta.core.model.owner.NotificationDto.serializer(), Samples.notification(ID2))
        vm.prepend(n)
        vm.prepend(n)
        assertEquals(listOf(ID2, ID1), vm.state.value.data!!.items.map { it.id.toString() })
        h.ok("""{"updated":1,"unread":0}""")
        assertEquals(OwnerDestination.Approvals(ID2), vm.open(n))
    }

    @Test
    fun `settings sends only changed push cells and keeps email`() {
        h.ok("[${Samples.routing("ACTION", "CRITICAL", true, mandatoryPush = true)},${Samples.routing("INFO", "INFO", false)}]")
        h.ok("""{"items":[],"total":0,"page":1,"page_size":25}""")
        val push = object : PushControl {
            override val available = false
            override val providerName = "none"
            override suspend fun register(): PushDeviceDto? = null
        }
        val vm = SettingsViewModel(h.data, push)
        vm.ui.await { !it.loading }
        vm.toggle("ACTION", "CRITICAL", false) // mandatory: ignored
        vm.toggle("INFO", "INFO", true)
        assertTrue(vm.ui.value.dirty)
        h.ok("[${Samples.routing("ACTION", "CRITICAL", true, true)},${Samples.routing("INFO", "INFO", true)}]")
        vm.save()
        vm.ui.await { it.message != null }
        h.server.takeRequest(); h.server.takeRequest()
        val put = h.server.takeRequest()
        assertEquals("PUT", put.method)
        assertEquals("""{"changes":[{"category":"INFO","severity":"INFO","push":true,"email":true}],"tenant_default":false}""", put.body!!.utf8())
        assertEquals(false, vm.ui.value.dirty)
    }
}
