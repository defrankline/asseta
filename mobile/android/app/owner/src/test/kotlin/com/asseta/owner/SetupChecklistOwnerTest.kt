package com.asseta.owner

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.MeResponse
import com.asseta.core.model.owner.SetupChecklistDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.Load
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.moreEntries
import com.asseta.owner.ui.setup.SetupLinks
import com.asseta.owner.ui.setup.SetupPresentation
import com.asseta.owner.ui.setup.SetupProgress
import com.asseta.owner.ui.setup.SetupTarget
import com.asseta.owner.ui.setup.SetupTexts
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Go-live checklist in the Owner app: banner figures, link mapping, actions and their gating. */
class SetupChecklistOwnerTest {
    private val json = NetworkFactory.json
    private val h = OwnerHarness()
    private val web = "https://asseta.co.tz/"
    private val owner = OwnerFeatures(
        setOf("tenant.setup.read", "tenant.setup.manage", "tenant.fleet.read", "tenant.job.read", "tenant.approval.read", "tenant.finance.read", "tenant.hours.read"),
    )

    @After fun close() = h.close()

    private fun step(key: String, order: Int, status: String, link: String, canSkip: Boolean = true, notNeeded: String = "null", total: String = "null") =
        """{"key":"$key","order":$order,"title":"T$order","description":"D","status":"$status","done_count":${if (total == "null") "null" else "1"},
        "total_count":$total,"link":"$link","required_permission":"tenant.fleet.manage","can_mark_not_needed":$canSkip,"not_needed":$notNeeded,
        "checks":[{"key":"c","label":"Part","done":false,"optional":true,"done_count":null,"total_count":null,"link":"$link","required_permission":"x"}]}"""

    private fun checklist(done: Int = 1, total: Int = 3, complete: Boolean = false, dismissed: Boolean = false, confirmed: String = "null") = """{
        "steps":[${step("MACHINES", 4, "TODO", "/tenant/machines", total = "5")},${step("COMPANY_SETTINGS", 1, "DONE", "/tenant/subscription", canSkip = false)},
        ${step("CONTROLS_CHOSEN", 8, "TODO", "/tenant/policies")},
        ${step("TRACKERS", 5, "NOT_NEEDED", "/tenant/trackers", notNeeded = """{"reason":"No trackers yet","marked_by":"$ID1","marked_by_name":"Asha","marked_at":"2026-10-28T08:00:00Z"}""")}],
        "steps_done":$done,"steps_total":$total,"percent":33,"complete":$complete,"dismissed":$dismissed,"controls_confirmed_at":$confirmed,
        "as_of":"2026-10-29T08:00:00Z"}"""

    private fun dto(body: String = checklist()) = json.decodeFromString(SetupChecklistDto.serializer(), body)

    @Test
    fun `banner figures come from me and follow the rules`() {
        val me = json.decodeFromString(
            MeResponse.serializer(),
            """{"user_id":"$ID1","email":"o@x.tz","display_name":"O","tenants":[
              {"tenant_id":"$TENANT","name":"Acme","status":"ACTIVE","setup_complete":false,"setup_percent":15,"setup_steps_done":2,"setup_steps_total":13,"setup_dismissed":false},
              {"tenant_id":"$ID2","name":"Other","status":"ACTIVE"}]}""",
        )
        val p = SetupProgress.fromMe(me.tenants[0])!!
        assertEquals(SetupProgress(2, 13, complete = false, dismissed = false), p)
        assertTrue(p.showBanner)
        assertEquals("Get ready to go live — 2 of 13 done", SetupTexts.banner(p.done, p.total))
        assertNull(SetupProgress.fromMe(me.tenants[1]))
        assertFalse(p.copy(complete = true).showBanner)
        assertFalse(p.copy(dismissed = true).showBanner)
    }

    @Test
    fun `links open the matching app screen, otherwise the web`() {
        assertEquals(OwnerDestination.Fleet, SetupLinks.appScreen("/tenant/machines", owner))
        assertNull(SetupLinks.appScreen("/tenant/machines?missing=tracker", owner))
        assertEquals(OwnerDestination.Jobs, SetupLinks.appScreen("/tenant/jobs", owner))
        assertEquals(OwnerDestination.Approvals(), SetupLinks.appScreen("/tenant/meter-baselines?missing=true", owner))
        assertEquals(OwnerDestination.Cash, SetupLinks.appScreen("/tenant/finance/cash", owner))
        assertNull(SetupLinks.appScreen("/tenant/finance/cash?tab=reasons", owner))
        assertNull(SetupLinks.appScreen("/tenant/hours/reasons", owner))
        assertNull(SetupLinks.appScreen("/tenant/policies", owner))
        // Without the read permission the app screen is not offered.
        assertNull(SetupLinks.appScreen("/tenant/jobs", OwnerFeatures(setOf("tenant.setup.read"))))
        assertEquals(SetupTarget.App(OwnerDestination.Jobs, "Open Jobs"), SetupLinks.target("/tenant/jobs", owner, web))
        val webTarget = SetupLinks.target("/tenant/geofences?tab=sites", owner, web)
        assertEquals(SetupTarget.Web("https://asseta.co.tz/tenant/geofences?tab=sites"), webTarget)
        assertEquals("Open on the web", webTarget!!.label)
        assertEquals("http://h:8/tenant/access", SetupLinks.webUrl("http://h:8/", "/tenant/access"))
    }

    @Test
    fun `only relative tenant links open on the web`() {
        listOf("https://evil.example/tenant/x", "//evil.example/tenant/x", "tenant/access", "/admin/x", "javascript:alert(1)", "/tenant/\\evil.example")
            .forEach { link ->
                assertNull(link, SetupLinks.webUrl(web, link))
                assertNull(link, SetupLinks.target(link, owner, web))
            }
        assertEquals(SetupTarget.Web("https://asseta.co.tz/tenant/policies"), SetupLinks.target("/tenant/policies", owner, web))
    }

    @Test
    fun `steps in order with their actions`() {
        val c = dto()
        val steps = SetupPresentation.steps(c)
        assertEquals(listOf(1, 4, 5, 8), steps.map { it.order })
        val (company, machines, trackers, controls) = steps
        assertFalse(SetupPresentation.hasAction(company))
        assertFalse(SetupPresentation.canMarkNotNeeded(company))
        assertTrue(SetupPresentation.hasAction(machines))
        assertTrue(SetupPresentation.canMarkNotNeeded(machines))
        assertEquals("1 of 5", SetupPresentation.countLine(machines.doneCount, machines.totalCount))
        assertNull(SetupPresentation.countLine(null, null))
        assertTrue(SetupPresentation.canUndo(trackers))
        assertFalse(SetupPresentation.hasAction(trackers))
        assertEquals("Marked not needed by Asha on 28 Oct 2026: No trackers yet", SetupTexts.notNeededBy("Asha", "28 Oct 2026", trackers.notNeeded!!.reason))
        assertEquals("Marked not needed by someone on 28 Oct 2026", SetupTexts.notNeededBy(null, "28 Oct 2026", null))
        assertTrue(SetupPresentation.canConfirmControls(controls, c))
        assertFalse(SetupPresentation.canConfirmControls(controls, dto(checklist(confirmed = "\"2026-10-29T07:00:00Z\""))))
        assertFalse(SetupPresentation.canConfirmControls(machines, c))
        assertTrue(SetupPresentation.needsAccess(machines, setOf("tenant.setup.read")))
        assertFalse(SetupPresentation.needsAccess(machines, setOf("tenant.fleet.manage")))
        assertEquals("Does not apply", SetupTexts.status("NOT_APPLICABLE"))
        assertEquals("Not needed", SetupTexts.status("NOT_NEEDED"))
    }

    @Test
    fun `manage is online only and needs the manage permission`() {
        assertTrue(SetupPresentation.manageGate(owner, online = true, DataSource.LIVE, readOnly = false) is MutationCheck.Allowed)
        assertTrue(SetupPresentation.manageGate(owner, online = false, DataSource.LIVE, readOnly = false) is MutationCheck.Blocked)
        assertTrue(SetupPresentation.manageGate(owner, online = true, DataSource.CACHE, readOnly = false) is MutationCheck.Blocked)
        assertTrue(SetupPresentation.manageGate(owner, online = true, DataSource.LIVE, readOnly = true) is MutationCheck.Blocked)
        val reader = OwnerFeatures(setOf("tenant.setup.read"))
        assertTrue(SetupPresentation.manageGate(reader, online = true, DataSource.LIVE, readOnly = false) is MutationCheck.Blocked)
        assertFalse(SetupPresentation.reasonValid("  ab "))
        assertTrue(SetupPresentation.reasonValid("abc"))
        assertFalse(SetupPresentation.reasonValid("x".repeat(501)))
    }

    @Test
    fun `entry points follow tenant setup read`() {
        assertEquals(OwnerDestination.SetupChecklist, moreEntries(owner).first().second)
        assertEquals("Go-live checklist", moreEntries(owner).first().first)
        val none = OwnerFeatures(setOf("tenant.fleet.read"))
        assertTrue(moreEntries(none).none { it.second == OwnerDestination.SetupChecklist })
        assertEquals(OwnerDestination.SetupChecklist, owner.route(OwnerDestination.SetupChecklist))
        assertEquals(OwnerDestination.More, none.route(OwnerDestination.SetupChecklist))
        assertEquals(OwnerDestination.SetupChecklist, DeepLinkRouter.fromPath("/tenant/setup"))
    }

    @Test
    fun `loads and writes update the banner figures and send the right bodies`() = runBlocking {
        h.data.seedSetupProgress(SetupProgress(2, 13, complete = false, dismissed = false))
        h.data.seedSetupProgress(SetupProgress(9, 9, complete = true, dismissed = false))
        assertEquals(2, h.data.setupProgress.value!!.done)

        h.ok(checklist(done = 1, total = 3))
        assertTrue(h.data.setupChecklist() is Load.Ok)
        assertTrue(h.server.takeRequest().url.toString().endsWith("/api/v1/tenant/setup-checklist"))
        assertEquals(SetupProgress(1, 3, complete = false, dismissed = false), h.data.setupProgress.value)

        h.ok(checklist(done = 2, total = 3))
        assertTrue(h.data.markSetupStepNotNeeded("MACHINES", "  We rent only  ") is ActionResult.Done)
        val mark = h.server.takeRequest()
        assertEquals("POST", mark.method)
        assertTrue(mark.url.toString().endsWith("/setup-checklist/steps/MACHINES/not-needed"))
        assertEquals("""{"reason":"We rent only"}""", mark.body!!.utf8())
        assertEquals(2, h.data.setupProgress.value!!.done)

        h.ok(checklist(done = 1, total = 3))
        assertTrue(h.data.undoSetupStepNotNeeded("MACHINES") is ActionResult.Done)
        assertEquals("DELETE", h.server.takeRequest().method)

        h.ok(checklist(done = 3, total = 3, complete = true))
        assertTrue(h.data.confirmSetupControls("  ") is ActionResult.Done)
        val confirm = h.server.takeRequest()
        assertTrue(confirm.url.toString().endsWith("/setup-checklist/confirm-controls"))
        assertEquals("{}", confirm.body!!.utf8())
        assertFalse(h.data.setupProgress.value!!.showBanner)

        h.error(422, "SETUP_STEP_REQUIRED")
        val refused = h.data.markSetupStepNotNeeded("COMPANY_SETTINGS", "not ours") as ActionResult.Refused
        assertEquals(SetupTexts.ERROR_STEP_REQUIRED, SetupTexts.error(refused.code, refused.error.message))
        assertEquals("other", SetupTexts.error("X", "other"))
    }
}
