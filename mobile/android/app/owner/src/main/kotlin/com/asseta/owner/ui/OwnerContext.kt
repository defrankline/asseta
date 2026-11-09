package com.asseta.owner.ui

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.TenantAccess
import com.asseta.core.network.RealtimeEvent
import com.asseta.owner.OwnerGraph
import com.asseta.owner.ui.accountability.DecisionKind
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.merge

/** The selected tenant as the Owner UI needs it. Permissions only hide/disable UI; the server decides. */
data class OwnerSession(
    val tenantId: String,
    val tenantName: String,
    val permissions: Set<String>,
    val readOnly: Boolean,
    val userEmail: String = "",
    /** More than one enterable company, so "Switch company" is offered. */
    val canSwitchTenant: Boolean = false,
    /** The signed-in user's id (`/me`): a request they proposed is never theirs to decide. */
    val userId: String? = null,
    /** Tenant capabilities switched off by policy (`/me` `disabled_capabilities`, e.g. CUSTOMER_HOURS). */
    val disabledCapabilities: Set<String> = emptySet(),
    /** Go-live banner figures from `/me` (null without tenant.setup.read). */
    val setup: com.asseta.owner.ui.setup.SetupProgress? = null,
) {
    val features: OwnerFeatures get() = OwnerFeatures(permissions, disabledCapabilities)

    fun can(action: OwnerAction, online: Boolean, source: DataSource?): MutationCheck =
        MutationGate.check(action, online, source ?: DataSource.CACHE, permissions, readOnly)
}

/**
 * What the Owner app shows for a membership, from the `/me` permission hints (same rules as the iOS `OwnerFeatures`).
 * Only hides UI; the server re-authorizes every call.
 */
data class OwnerFeatures(val permissions: Set<String>, val disabled: Set<String> = emptySet()) {
    val fleet get() = "tenant.fleet.read" in permissions
    val manageAlerts get() = "tenant.fleet.alert_manage" in permissions
    val jobs get() = "tenant.job.read" in permissions
    val finance get() = "tenant.finance.read" in permissions
    val expenses get() = "tenant.expense.read" in permissions
    val overview get() = fleet || jobs || finance
    val approvals get() = "tenant.approval.read" in permissions
    val decideApprovals get() = "tenant.approval.expense" in permissions
    val approveJobs get() = "tenant.job.approve" in permissions
    val createJobs get() = "tenant.job.write" in permissions
    val jobSites get() = "tenant.geofence.read" in permissions
    val cases get() = "tenant.case.read" in permissions && TenantAccess.INVESTIGATIONS !in disabled

    /** Live tracking is in use (TRACKING not switched off): trackers, alerts, geofences and connectivity figures. */
    val tracking get() = TenantAccess.TRACKING !in disabled
    val investigations get() = TenantAccess.INVESTIGATIONS !in disabled

    /** Alerts tab and lists (tenant.fleet.read with TRACKING on). */
    val alerts get() = fleet && tracking
    val meterEvidence get() = "tenant.meter.read" in permissions
    val meterApprove get() = "tenant.meter.approve" in permissions
    val verifyHandovers get() = "tenant.finance.verify" in permissions

    /** The "Payments to confirm" queue: the role can read customer payments and decide them. */
    val confirmPayments get() = finance && verifyHandovers
    val issueFloats get() = "tenant.finance.cash" in permissions
    val reviewExceptions get() = "tenant.meter.review" in permissions
    val notifications get() = "tenant.notification.read" in permissions

    // Accountability (each list needs its read permission; deciding needs the approve permission).
    val hoursRead get() = "tenant.hours.read" in permissions

    /** Customer hours are in use (not switched off by the tenant's policy) and the role may read them. */
    val customerHours get() = hoursRead && TenantAccess.CUSTOMER_HOURS !in disabled

    /** Engine-hour controls are in use (ENGINE_HOURS not switched off by the tenant's policy). */
    val engineHours get() = TenantAccess.ENGINE_HOURS !in disabled

    /** The DEC-030 cash custody additions are in use (CASH_CUSTODY not switched off); the cash basics always stay. */
    val cashCustody get() = TenantAccess.CASH_CUSTODY !in disabled

    /** Revenue reconciliation is in use (DEC-031; platform default off, so `/me` lists it while it is off). */
    val revenueOn get() = TenantAccess.REVENUE_RECONCILIATION !in disabled

    /** Daily machine sheet, revenue differences and non-revenue hours (tenant.revenue.read). */
    val revenueRead get() = revenueOn && "tenant.revenue.read" in permissions

    /** Explain a revenue difference (needs read too, for the reason list). */
    val revenueExplain get() = revenueRead && "tenant.revenue.explain" in permissions

    /** Decide revenue differences and non-revenue hours. */
    val revenueDecide get() = revenueRead && "tenant.revenue.decide" in permissions

    /** The machine-day ledger (DEC-032): tenant.meter.read with ENGINE_HOURS on, whether or not revenue checks are on. */
    val machineDayLedger get() = meterEvidence && engineHours

    /** Machine days are open to this role: with money (revenue checks) or the allocations alone. */
    val machineDays get() = revenueRead || machineDayLedger

    /** People scorecard (DEC-031 M1): SCORECARD on and the role may read it. */
    val scorecard get() = TenantAccess.SCORECARD !in disabled && "tenant.oversight.scorecard.read" in permissions

    /** Oversight lists (unbilled work, idle machines, office check-ins). */
    val oversightRead get() = "tenant.oversight.read" in permissions

    /** Unbilled work list (DEC-031 M2): UNBILLED_WORK on and tenant.oversight.read. */
    val unbilledWork get() = oversightRead && TenantAccess.UNBILLED_WORK !in disabled

    /** Idle machines list (DEC-031 M2): IDLE_MACHINES on and tenant.oversight.read. */
    val idleMachines get() = oversightRead && TenantAccess.IDLE_MACHINES !in disabled

    /** Adjustment requests waiting for a decision (DEC-032). */
    val adjustmentRead get() = "tenant.adjustment.read" in permissions

    /** May withdraw a request of their own while it waits. */
    val adjustmentPropose get() = "tenant.adjustment.propose" in permissions

    /** Approvals opens for expense approvers and for adjustment holders, who may hold no tenant.approval.* at all. */
    val approvalsScreen get() = approvals || DecisionKind.visible(this).isNotEmpty() || revenueRead || confirmPayments

    /** One customer payment can be read (to mark a reversed one). */
    val paymentDetails get() = finance || adjustmentRead

    /** Go-live checklist (banner, More entry, screen). */
    val setupRead get() = "tenant.setup.read" in permissions

    /** Mark steps as not needed / undo, confirm the default controls. */
    val setupManage get() = setupRead && "tenant.setup.manage" in permissions

    /** The same features with more switched-off capabilities (e.g. the dashboard's `disabled_capabilities`). */
    fun without(capabilities: Collection<String>): OwnerFeatures =
        if (capabilities.all { it in disabled }) this else copy(disabled = disabled + capabilities)

    /**
     * [d], or the list / home it falls back to when it belongs to a capability the tenant switched off (a deep link to
     * a hidden kind opens the list instead: Approvals for a decision, Cash with supervisors for a cash record).
     */
    fun route(d: OwnerDestination): OwnerDestination = when (d) {
        is OwnerDestination.Decision -> if (DecisionKind.of(d.kind)?.switchedOff(this) == true) OwnerDestination.Approvals() else d
        is OwnerDestination.CashRecord, is OwnerDestination.RemittanceOverdue -> if (cashCustody) d else OwnerDestination.Cash
        is OwnerDestination.DailySheet -> if (machineDays) d else OwnerDestination.Machine(d.machineId)
        is OwnerDestination.SheetDay -> if (machineDays) d else OwnerDestination.Machine(d.machineId)
        // Customer hours (DEC-031 P4): switched off or not readable -> the dashboard, as before these screens existed.
        OwnerDestination.CustomerHours, is OwnerDestination.HoursPurchase, is OwnerDestination.HoursStatement ->
            if (customerHours) d else OwnerDestination.Accountability
        // Oversight (DEC-031 Phase 5): switched off or not readable -> the dashboard.
        OwnerDestination.Scorecard, is OwnerDestination.ScorecardPerson -> if (scorecard) d else OwnerDestination.Accountability
        OwnerDestination.UnbilledWork -> if (unbilledWork) d else OwnerDestination.Accountability
        OwnerDestination.IdleMachines -> if (idleMachines) d else OwnerDestination.Accountability
        OwnerDestination.SetupChecklist -> if (setupRead) d else OwnerDestination.More
        is OwnerDestination.EmployeeAccountability -> if (employeeAccountability) d else OwnerDestination.Accountability
        OwnerDestination.Lookup -> if (lookup) d else OwnerDestination.More
        // DEC-032 switches: a link to a hidden module opens the overview instead.
        OwnerDestination.Cases, is OwnerDestination.Case -> if (cases) d else OwnerDestination.Home
        is OwnerDestination.Alerts -> if (alerts) d else OwnerDestination.Home
        // A link to a customer payment for a role that cannot read them: the inbox, where the notification already is.
        is OwnerDestination.CustomerPayment -> if (finance) d else OwnerDestination.Notifications()
        else -> d
    }
    val custodyRead get() = finance || "tenant.collection.record" in permissions
    val accountability get() = "tenant.accountability.read" in permissions

    /** One employee's accountability screen (DEC-032 Phase 4). */
    val employeeAccountability get() = "tenant.accountability.employee.read" in permissions

    /** Find a record by its reference (DEC-032 Phase 4). */
    val lookup get() = "tenant.lookup.read" in permissions
}

/**
 * Reload triggers for a screen: WebSocket "entity changed" frames for [entities] and connectivity coming back.
 * Debounced so a burst of position updates causes one reload.
 */
@OptIn(FlowPreview::class)
fun OwnerGraph.refreshTriggers(vararg entities: String, debounceMs: Long = 1_500): Flow<Unit> {
    val set = entities.toSet()
    val changes = liveUpdates.events.filterIsInstance<RealtimeEvent.EntityChanged>().filter { it.entity in set }.map { }
    val reconnected = network.online.drop(1).filter { it }.map { }
    return merge(changes, reconnected).debounce(debounceMs)
}
