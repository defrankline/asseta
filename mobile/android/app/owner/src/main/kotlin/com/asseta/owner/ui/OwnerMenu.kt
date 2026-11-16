package com.asseta.owner.ui

import androidx.annotation.DrawableRes
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.ui.shell.CountBadge
import com.asseta.core.ui.shell.ShellText
import com.asseta.core.ui.theme.AssetaColors
import com.asseta.core.ui.theme.palette
import com.asseta.owner.R
import com.asseta.owner.ui.accountability.OwnerAccountabilityTexts
import com.asseta.core.ui.R as CoreR

/** One side-menu entry: a destination, or a session action ([destination] null: [key] names the action). */
data class MenuEntry(
    val key: String,
    val label: String,
    @DrawableRes val icon: Int,
    val destination: OwnerDestination? = null,
    val badge: String? = null,
    val alert: Boolean = false,
)

/** A titled group of the side menu ([header] null: the first group, untitled). */
data class MenuGroup(val header: String?, val entries: List<MenuEntry>)

/** Side-menu wording (design OwnerSideNav; same as iOS). */
object MenuTexts {
    const val HOME = "Home"
    const val APPROVALS = "Approvals"
    const val CUSTOMERS = "Customers & hours"
    const val MACHINES = "Machines"
    const val MONEY = "Money"
    const val REPORTS = "Reports"
    const val NOTIFICATIONS = "Notifications"
    const val MORE = "More"
    const val DASHBOARD = "Dashboard"
    const val FLEET = "Fleet map"
    const val ALERTS = "Alerts"
    const val EXCEPTIONS = "Meter exceptions"
    const val FIELD_SPEND = "Field spend"
    const val CASH = "Cash with supervisors"
    const val INVESTIGATIONS = "Investigations"
    const val SWITCH = "Switch company"
    const val SETTINGS = "Settings"
    const val SIGN_OUT = "Sign out"
    const val READ_ONLY = "This company is read-only. Viewing only."

    const val KEY_SWITCH = "switch"
    const val KEY_SETTINGS = "settings"
    const val KEY_SIGN_OUT = "sign_out"
}

/**
 * What the side menu shows for a role (design OwnerSideNav), grouped: the business screens, then "More" with the
 * existing screens the design does not name (each with its own gating), then the footer. Never one flat list.
 */
object OwnerMenu {
    fun groups(f: OwnerFeatures, waiting: Int?, unread: Int?): List<MenuGroup> = listOf(
        MenuGroup(null, main(f, waiting, unread)),
        MenuGroup(MenuTexts.MORE, more(f)),
    ).filter { it.entries.isNotEmpty() }

    fun main(f: OwnerFeatures, waiting: Int?, unread: Int?): List<MenuEntry> = listOfNotNull(
        MenuEntry("home", MenuTexts.HOME, CoreR.drawable.ic_shell_home, OwnerDestination.Home),
        MenuEntry("approvals", MenuTexts.APPROVALS, CoreR.drawable.ic_shell_approvals, OwnerDestination.Approvals(), ShellText.badge(waiting))
            .takeIf { f.approvalsScreen },
        MenuEntry("customers", MenuTexts.CUSTOMERS, CoreR.drawable.ic_shell_customers, OwnerDestination.Customers).takeIf { f.customers },
        MenuEntry("machines", MenuTexts.MACHINES, CoreR.drawable.ic_shell_machines, OwnerDestination.Machines).takeIf { f.machines },
        MenuEntry("money", MenuTexts.MONEY, CoreR.drawable.ic_shell_money, OwnerDestination.Money).takeIf { f.money },
        MenuEntry("reports", MenuTexts.REPORTS, CoreR.drawable.ic_shell_dashboard, OwnerDestination.Reports).takeIf { f.reports },
        MenuEntry("notifications", MenuTexts.NOTIFICATIONS, CoreR.drawable.ic_shell_bell, OwnerDestination.Notifications(), ShellText.badge(unread), alert = true)
            .takeIf { f.notifications },
    )

    /** The screens kept from before ADR-008, with the gating they always had. */
    fun more(f: OwnerFeatures): List<MenuEntry> = listOfNotNull(
        MenuEntry("setup", com.asseta.owner.ui.setup.SetupTexts.MORE, R.drawable.ic_approval, OwnerDestination.SetupChecklist).takeIf { f.setupRead },
        MenuEntry("dashboard", MenuTexts.DASHBOARD, CoreR.drawable.ic_shell_dashboard, OwnerDestination.Dashboard).takeIf { f.overview },
        MenuEntry("accountability", OwnerAccountabilityTexts.MORE_ACCOUNTABILITY, R.drawable.ic_approval, OwnerDestination.Accountability).takeIf { f.accountability },
        MenuEntry("lookup", com.asseta.owner.ui.accountability.ManagementTexts.LOOKUP_MORE, R.drawable.ic_investigation, OwnerDestination.Lookup).takeIf { f.lookup },
        MenuEntry("scorecard", com.asseta.owner.ui.accountability.OversightTexts.SCORE_MORE, R.drawable.ic_investigation, OwnerDestination.Scorecard).takeIf { f.scorecard },
        MenuEntry("fleet", MenuTexts.FLEET, R.drawable.ic_nav_fleet, OwnerDestination.Fleet).takeIf { f.fleet },
        MenuEntry("alerts", MenuTexts.ALERTS, R.drawable.ic_nav_alerts, OwnerDestination.Alerts()).takeIf { f.alerts },
        MenuEntry("exceptions", MenuTexts.EXCEPTIONS, R.drawable.ic_warning, OwnerDestination.Exceptions).takeIf { f.meterEvidence },
        MenuEntry("spend", MenuTexts.FIELD_SPEND, R.drawable.ic_receipt, OwnerDestination.FieldSpend).takeIf { f.expenses },
        MenuEntry("cash", MenuTexts.CASH, R.drawable.ic_cash, OwnerDestination.Cash).takeIf { f.finance },
        MenuEntry("cases", MenuTexts.INVESTIGATIONS, R.drawable.ic_investigation, OwnerDestination.Cases).takeIf { f.cases },
    )

    /** Switch company (only with another company to enter), Settings (account deletion, closure, push) and Sign out. */
    fun footer(canSwitchTenant: Boolean): List<MenuEntry> = listOfNotNull(
        MenuEntry(MenuTexts.KEY_SWITCH, MenuTexts.SWITCH, CoreR.drawable.ic_shell_switch).takeIf { canSwitchTenant },
        MenuEntry(MenuTexts.KEY_SETTINGS, MenuTexts.SETTINGS, CoreR.drawable.ic_shell_settings, OwnerDestination.Settings),
        MenuEntry(MenuTexts.KEY_SIGN_OUT, MenuTexts.SIGN_OUT, CoreR.drawable.ic_shell_sign_out),
    )

    /** Every screen the side menu opens for a role, as (label, destination), in menu order (groups, then Settings). */
    fun entries(f: OwnerFeatures, waiting: Int? = null, unread: Int? = null): List<Pair<String, OwnerDestination>> =
        (groups(f, waiting, unread).flatMap { it.entries } + footer(false)).mapNotNull { e -> e.destination?.let { e.label to it } }

    /** The entry highlighted for the side-menu destination the stack sits under. */
    fun selectedKey(root: OwnerDestination, groups: List<MenuGroup>): String? =
        groups.flatMap { it.entries }.firstOrNull { it.destination == root }?.key
}

/**
 * The side menu sheet: who is signed in, the grouped entries (titled groups after the first), then the footer. Same
 * look as the shared ShellDrawer, with group headers.
 */
@Composable
fun OwnerDrawerSheet(
    name: String,
    subtitle: String,
    groups: List<MenuGroup>,
    footer: List<MenuEntry>,
    selected: String?,
    caption: String?,
    onSelect: (MenuEntry) -> Unit,
) {
    val p = palette
    ModalDrawerSheet(drawerContainerColor = p.drawer, drawerShape = RoundedCornerShape(topEnd = 28.dp, bottomEnd = 28.dp), modifier = Modifier.width(304.dp)) {
        Column(Modifier.fillMaxHeight().statusBarsPadding().padding(start = 16.dp, end = 16.dp, top = 24.dp, bottom = 24.dp)) {
            Row(Modifier.padding(start = 8.dp, end = 8.dp, bottom = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(48.dp).clip(CircleShape).background(p.accent), contentAlignment = Alignment.Center) {
                    Text(ShellText.initials(name), color = AssetaColors.OnAmber, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                }
                Column(Modifier.padding(start = 12.dp)) {
                    Text(name, fontWeight = FontWeight.Bold, fontSize = 16.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(subtitle, color = p.secondaryText, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
            HorizontalDivider(color = p.separator)
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(top = 14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                groups.forEach { g ->
                    g.header?.let {
                        Text(
                            it.uppercase(), fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = p.secondaryText, letterSpacing = 0.6.sp,
                            modifier = Modifier.padding(start = 12.dp, top = 16.dp, bottom = 4.dp).semantics { heading() },
                        )
                    }
                    g.entries.forEach { e -> MenuRow(e, e.key == selected, large = g.header == null) { onSelect(e) } }
                }
            }
            HorizontalDivider(color = p.separator)
            Column(Modifier.padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                footer.forEach { e -> MenuRow(e, false, large = false, tint = if (e.key == MenuTexts.KEY_SIGN_OUT) p.offline else null) { onSelect(e) } }
                caption?.let { Text(it, color = p.neutral, fontSize = 12.sp, modifier = Modifier.padding(start = 12.dp, end = 12.dp, top = 6.dp)) }
            }
        }
    }
}

@Composable
private fun MenuRow(e: MenuEntry, selected: Boolean, large: Boolean, tint: Color? = null, onClick: () -> Unit) {
    val p = palette
    Row(
        Modifier.fillMaxWidth().height(if (large) 48.dp else 44.dp).clip(RoundedCornerShape(14.dp))
            .background(if (selected) p.raised else Color.Transparent)
            .clickable(role = Role.Button, onClick = onClick).padding(horizontal = 12.dp)
            .semantics(mergeDescendants = true) { contentDescription = listOfNotNull(e.label, e.badge).joinToString(", ") },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Icon(painterResource(e.icon), null, tint = tint ?: if (selected) p.accent else p.secondaryText, modifier = Modifier.size(if (large) 22.dp else 20.dp))
        Text(
            e.label, color = tint ?: if (selected) p.accent else if (large) Color.Unspecified else p.secondaryText,
            fontSize = if (large) 15.sp else 14.sp, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
            modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
        )
        e.badge?.let { CountBadge(it, alert = e.alert) }
    }
}
