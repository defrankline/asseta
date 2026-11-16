package com.asseta.owner.ui

import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.RecordKinds
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.OwnerAccountabilityTexts

/**
 * ADR-008 navigation (designs OwnerHome / OwnerSideNav): Home is the root; a side-menu destination resets the back stack
 * to Home + it (so back returns Home), any other destination is pushed; system back pops.
 */
object OwnerNavigation {
    /** First screen after entering a company. */
    fun start(@Suppress("UNUSED_PARAMETER") features: OwnerFeatures): OwnerDestination = OwnerDestination.Home

    /** Opened from the side menu (or Home's tiles): they reset the stack. */
    fun isMenuRoot(d: OwnerDestination): Boolean = when (d) {
        OwnerDestination.Home, OwnerDestination.Customers, OwnerDestination.Machines, OwnerDestination.Money, OwnerDestination.Reports,
        OwnerDestination.Dashboard, OwnerDestination.Fleet, OwnerDestination.Accountability, OwnerDestination.Lookup,
        OwnerDestination.Scorecard, OwnerDestination.FieldSpend, OwnerDestination.Cash, OwnerDestination.Cases, OwnerDestination.Settings,
        OwnerDestination.SetupChecklist, OwnerDestination.IdleMachines, OwnerDestination.Exceptions,
        -> true
        is OwnerDestination.Approvals -> d.approvalId == null
        is OwnerDestination.Notifications -> d.notificationId == null
        is OwnerDestination.Alerts -> d.alertId == null
        else -> false
    }

    fun navigate(stack: List<OwnerDestination>, to: OwnerDestination): List<OwnerDestination> = when {
        to == OwnerDestination.Home -> listOf(OwnerDestination.Home)
        isMenuRoot(to) -> listOf(OwnerDestination.Home, to)
        stack.lastOrNull() == to -> stack
        else -> stack + to
    }

    fun back(stack: List<OwnerDestination>): List<OwnerDestination> = if (stack.size > 1) stack.dropLast(1) else stack

    /** The side-menu destination the stack sits under (highlighted in the menu). */
    fun menuRoot(stack: List<OwnerDestination>): OwnerDestination = stack.getOrNull(1)?.takeIf(::isMenuRoot) ?: OwnerDestination.Home

    /** Home draws its own top row (menu, bell); every other screen has the top bar with a back button. */
    fun hasTopBar(stack: List<OwnerDestination>): Boolean = stack.last() != OwnerDestination.Home

    /** Screen titles (designs; the rest as on iOS). */
    fun title(d: OwnerDestination, tenantName: String = "Home"): String = when (d) {
        OwnerDestination.Home -> "Home"
        OwnerDestination.Dashboard -> tenantName
        OwnerDestination.Customers -> "Customers & hours"
        OwnerDestination.Machines -> "Machines"
        OwnerDestination.Money -> "Money"
        OwnerDestination.Reports -> "Reports"
        OwnerDestination.HoursByReason -> com.asseta.owner.ui.reports.OwnerReportsTexts.BY_REASON
        is OwnerDestination.MachineReport -> "Machine report"
        is OwnerDestination.RecordPayment -> com.asseta.owner.ui.money.PaymentTexts.TITLE
        OwnerDestination.Fleet -> "Fleet map"
        is OwnerDestination.Machine -> "Machine"
        OwnerDestination.More -> "Home"
        is OwnerDestination.Alerts -> if (d.alertId == null) "Alerts" else "Alert"
        is OwnerDestination.Approvals -> if (d.approvalId == null) "Approvals" else "Approval"
        is OwnerDestination.MeterReset -> "Meter reset"
        is OwnerDestination.Exceptions -> "Meter exceptions"
        is OwnerDestination.MeterException -> "Meter exception"
        is OwnerDestination.Handover -> "Cash handover"
        is OwnerDestination.CustomerPayment -> com.asseta.owner.ui.approvals.PaymentReviewText.SCREEN_TITLE
        is OwnerDestination.PettyCashMovement -> com.asseta.owner.ui.approvals.PettyCashReviewText.TITLE_MOVEMENT
        is OwnerDestination.PettyCashAdjustment -> com.asseta.owner.ui.approvals.PettyCashReviewText.TITLE_ADJUSTMENT
        OwnerDestination.FieldSpend -> "Field spend"
        OwnerDestination.Cash -> "Cash with supervisors"
        OwnerDestination.Cases -> "Investigations"
        is OwnerDestination.Case -> "Investigation"
        is OwnerDestination.Notifications -> if (d.notificationId == null) "Notifications" else "Notification"
        OwnerDestination.Settings -> "Settings"
        // A variance is titled by its status once loaded (DecisionMapper.varianceTitle).
        is OwnerDestination.Decision -> if (d.kind == DecisionKinds.WRITE_OFF) OwnerAccountabilityTexts.VARIANCE_TITLE else DecisionKind.of(d.kind)?.title ?: "Approval"
        OwnerDestination.Accountability -> OwnerAccountabilityTexts.DASH_TITLE
        is OwnerDestination.CashRecord ->
            if (d.kind == RecordKinds.CASH_FLOAT) OwnerAccountabilityTexts.RECORD_FLOAT_TITLE else OwnerAccountabilityTexts.RECORD_TRANSFER_TITLE
        is OwnerDestination.RemittanceOverdue ->
            if (d.id == null) OwnerAccountabilityTexts.OVERDUE_TITLE else OwnerAccountabilityTexts.OVERDUE_DETAIL_TITLE
        is OwnerDestination.MachineDays -> OwnerAccountabilityTexts.MACHINE_DAYS
        is OwnerDestination.MachineDay -> com.asseta.owner.ui.accountability.RecordFormat.day(d.day)
        OwnerDestination.CustomerHours -> "Customers & hours"
        is OwnerDestination.HoursPurchase -> OwnerAccountabilityTexts.HOURS_PURCHASE_TITLE
        is OwnerDestination.HoursStatement -> OwnerAccountabilityTexts.STMT_TITLE
        OwnerDestination.Scorecard -> com.asseta.owner.ui.accountability.OversightTexts.SCORE_TITLE
        is OwnerDestination.ScorecardPerson -> d.name ?: com.asseta.owner.ui.accountability.OversightTexts.SCORE_TITLE
        OwnerDestination.IdleMachines -> com.asseta.owner.ui.accountability.OversightTexts.IDLE_TITLE
        OwnerDestination.SetupChecklist -> com.asseta.owner.ui.setup.SetupTexts.TITLE
        OwnerDestination.CompanyClosure -> com.asseta.owner.ui.settings.ClosureTexts.TITLE
        is OwnerDestination.EmployeeAccountability -> d.name ?: com.asseta.owner.ui.accountability.ManagementTexts.EMP_TITLE
        OwnerDestination.Lookup -> com.asseta.owner.ui.accountability.ManagementTexts.LOOKUP_TITLE
    }
}
