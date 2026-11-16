package com.asseta.core.ui.shell

import androidx.annotation.DrawableRes
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
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
import androidx.compose.material3.LinearProgressIndicator
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
import com.asseta.core.ui.R
import com.asseta.core.ui.theme.AssetaColors
import com.asseta.core.ui.theme.palette
import java.time.LocalTime

/*
 * ADR-008 app shell shared by the Supervisor and Owner apps (approved designs Main / SideNav / OwnerHome /
 * OwnerSideNav): a sliding side menu, the home's summary strip, big action tiles, status pills and card lists. The
 * same building blocks and sizes as the iOS apps.
 */

/** One side-menu entry; [badge] in amber ([alert] false) or red ([alert] true). */
data class DrawerEntry(
    val key: String,
    val label: String,
    @DrawableRes val icon: Int,
    val badge: String? = null,
    val alert: Boolean = false,
)

/** Tone of a status pill (design: amber "Awaiting approval", green "Paid", red "Overdue"). */
enum class PillTone { WAITING, GOOD, BAD, ACCENT, NEUTRAL }

object ShellText {
    /** "Good morning, Daudi": the first word of the display name, by the local time of day. */
    fun greeting(displayName: String?, now: LocalTime = LocalTime.now()): String {
        val part = when (now.hour) {
            in 0..11 -> "Good morning"
            in 12..16 -> "Good afternoon"
            else -> "Good evening"
        }
        val first = displayName?.trim()?.split(Regex("\\s+"))?.firstOrNull()?.takeIf { it.isNotEmpty() && '@' !in it }
        return if (first == null) part else "$part, $first"
    }

    /** "DM" from "Daudi Mollel"; "?" when there is no name. */
    fun initials(displayName: String?): String {
        val words = displayName?.trim()?.split(Regex("\\s+"))?.filter { it.isNotEmpty() && '@' !in it }.orEmpty()
        return when {
            words.isEmpty() -> displayName?.trim()?.firstOrNull()?.uppercase() ?: "?"
            words.size == 1 -> words[0].take(2).uppercase()
            else -> (words.first().take(1) + words.last().take(1)).uppercase()
        }
    }

    /** Badge text: null for 0, "99+" above 99. */
    fun badge(count: Int?): String? = count?.takeIf { it > 0 }?.let { if (it > 99) "99+" else it.toString() }
}

/** The side menu (design SideNav): who is signed in, the entries, then the footer entries and a caption. */
@Composable
fun ShellDrawer(
    name: String,
    subtitle: String,
    entries: List<DrawerEntry>,
    footer: List<DrawerEntry>,
    selected: String?,
    caption: String?,
    onSelect: (String) -> Unit,
    footerTint: Map<String, Color> = emptyMap(),
) {
    val p = palette
    ModalDrawerSheet(
        drawerContainerColor = p.drawer,
        drawerShape = RoundedCornerShape(topEnd = 28.dp, bottomEnd = 28.dp),
        modifier = Modifier.width(304.dp),
    ) {
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
            Column(
                Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(top = 14.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                entries.forEach { e -> DrawerRow(e, e.key == selected, large = true, tint = null) { onSelect(e.key) } }
            }
            HorizontalDivider(color = p.separator)
            Column(Modifier.padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                footer.forEach { e -> DrawerRow(e, false, large = false, tint = footerTint[e.key]) { onSelect(e.key) } }
                caption?.let { Text(it, color = p.neutral, fontSize = 12.sp, modifier = Modifier.padding(start = 12.dp, end = 12.dp, top = 6.dp)) }
            }
        }
    }
}

@Composable
private fun DrawerRow(e: DrawerEntry, selected: Boolean, large: Boolean, tint: Color?, onClick: () -> Unit) {
    val p = palette
    val color = when {
        selected -> p.accent
        large -> Color.Unspecified
        else -> p.secondaryText
    }
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
            e.label, color = color, fontSize = if (large) 15.sp else 14.sp, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
            modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
        )
        e.badge?.let { CountBadge(it, alert = e.alert) }
    }
}

/** Amber (or red) count badge. */
@Composable
fun CountBadge(text: String, alert: Boolean = false) {
    val bg = if (alert) palette.offline else palette.accent
    val fg = if (alert) Color.White else AssetaColors.OnAmber
    Text(
        text, color = fg, fontSize = 12.sp, fontWeight = FontWeight.Bold,
        modifier = Modifier.clip(RoundedCornerShape(999.dp)).background(bg).padding(horizontal = 8.dp, vertical = 2.dp),
    )
}

/** Home's first row: the menu button, then [trailing] (the sync chip, the bell). */
@Composable
fun HomeTopRow(onMenu: () -> Unit, menuBadge: String? = null, trailing: @Composable RowScope.() -> Unit = {}) {
    Row(Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        MenuButton(onMenu, menuBadge)
        Spacer(Modifier.weight(1f))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp), content = trailing)
    }
}

/** The 44 dp menu button that opens the side menu. */
@Composable
fun MenuButton(onClick: () -> Unit, badge: String? = null) {
    Box {
        Box(
            Modifier.size(44.dp).clip(RoundedCornerShape(12.dp)).background(palette.cell)
                .clickable(role = Role.Button, onClickLabel = "Open menu", onClick = onClick)
                .semantics { contentDescription = "Open menu" },
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(R.drawable.ic_shell_menu), null, modifier = Modifier.size(22.dp))
        }
        badge?.let { Box(Modifier.align(Alignment.TopEnd).padding(start = 30.dp)) { CountBadge(it, alert = true) } }
    }
}

/** Round chip: an icon and a short status ("All synced"). */
@Composable
fun StatusChip(label: String, @DrawableRes icon: Int, tint: Color, onClick: (() -> Unit)? = null) {
    val base = Modifier.clip(RoundedCornerShape(999.dp)).background(palette.cell)
    Row(
        (if (onClick != null) base.clickable(role = Role.Button, onClick = onClick) else base).padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(painterResource(icon), null, tint = tint, modifier = Modifier.size(16.dp))
        Text(label, fontSize = 13.sp, color = palette.secondaryText)
    }
}

/** "Good morning, Daudi" over the company name. */
@Composable
fun Greeting(greeting: String, company: String) {
    Column(Modifier.padding(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 18.dp).semantics(mergeDescendants = true) { heading() }) {
        Text(greeting, fontSize = 14.sp, color = palette.secondaryText)
        Text(company, fontSize = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 2.dp))
    }
}

/** One figure of the summary strip; [accent] tints the value amber. */
data class SummaryFigure(val label: String, val value: String, val accent: Boolean = false)

/** The home's card of three figures. */
@Composable
fun SummaryStrip(figures: List<SummaryFigure>, modifier: Modifier = Modifier) {
    Row(
        modifier.padding(horizontal = 20.dp).fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(palette.cell).padding(16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        figures.forEach { f ->
            Column(Modifier.weight(1f).semantics(mergeDescendants = true) {}) {
                Text(f.label, fontSize = 12.sp, color = palette.secondaryText, maxLines = 2)
                Text(f.value, fontSize = 17.sp, fontWeight = FontWeight.Bold, color = if (f.accent) palette.accent else Color.Unspecified,
                    modifier = Modifier.padding(top = 4.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

/** Upper-case muted section label ("WHAT DO YOU WANT TO DO?", "RECENT"). */
@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text.uppercase(), fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = palette.secondaryText, letterSpacing = 0.6.sp,
        modifier = modifier.padding(start = 20.dp, end = 20.dp, top = 22.dp, bottom = 10.dp).semantics { heading() },
    )
}

/** One big home tile; [primary] = the amber tile. */
@Composable
fun ActionTile(
    title: String,
    subtitle: String,
    @DrawableRes icon: Int,
    modifier: Modifier = Modifier,
    primary: Boolean = false,
    badge: String? = null,
    onClick: () -> Unit,
) {
    val p = palette
    val bg = if (primary) p.accent else p.cell
    val fg = if (primary) AssetaColors.OnAmber else Color.Unspecified
    Box(
        modifier.height(150.dp).clip(RoundedCornerShape(20.dp)).background(bg)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = listOfNotNull(title, subtitle, badge).joinToString(", ") }
            .padding(16.dp),
    ) {
        Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.SpaceBetween) {
            Box(
                Modifier.size(44.dp).clip(RoundedCornerShape(12.dp)).background(if (primary) AssetaColors.OnAmber.copy(alpha = 0.12f) else p.raised),
                contentAlignment = Alignment.Center,
            ) {
                Icon(painterResource(icon), null, tint = if (primary) AssetaColors.OnAmber else p.accent, modifier = Modifier.size(24.dp))
            }
            Column {
                Text(title, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = fg)
                Text(subtitle, fontSize = 13.sp, color = if (primary) AssetaColors.OnAmber.copy(alpha = 0.85f) else p.secondaryText,
                    modifier = Modifier.padding(top = 2.dp), maxLines = 2)
            }
        }
        badge?.let { Box(Modifier.align(Alignment.TopEnd)) { CountBadge(it) } }
    }
}

/** Tiles two per row (design: 12 dp gaps, 20 dp side margins). */
@Composable
fun TileGrid(tiles: List<@Composable (Modifier) -> Unit>) {
    Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        tiles.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { it(Modifier.weight(1f)) }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/** A rounded card on the screen background. */
@Composable
fun ShellCard(modifier: Modifier = Modifier, padding: Boolean = true, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier.padding(horizontal = 20.dp).fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(palette.cell)
            .then(if (padding) Modifier.padding(16.dp) else Modifier),
        content = content,
    )
}

/** One row of a card list: title, subtitle, optional trailing (a pill or a figure); dividers between rows. */
@Composable
fun CardRow(
    title: String,
    subtitle: String? = null,
    last: Boolean = true,
    onClick: (() -> Unit)? = null,
    detail: String? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    val p = palette
    val base = Modifier.fillMaxWidth()
    Column((if (onClick != null) base.clickable(role = Role.Button, onClick = onClick) else base)) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 16.dp, vertical = 14.dp).semantics(mergeDescendants = true) {},
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                subtitle?.let { Text(it, fontSize = 13.sp, color = p.secondaryText, modifier = Modifier.padding(top = 2.dp)) }
                detail?.let { Text(it, fontSize = 13.sp, color = p.secondaryText, modifier = Modifier.padding(top = 2.dp)) }
            }
            trailing?.let { Box(Modifier.padding(start = 12.dp)) { it() } }
        }
        if (!last) HorizontalDivider(color = p.separator)
    }
}

/** A status pill (design colours). */
@Composable
fun StatusPill(text: String, tone: PillTone) {
    val p = palette
    val (fg, bg) = when (tone) {
        PillTone.WAITING -> (if (p.dark) Color(0xFFF5C04A) else Color(0xFF8A5A00)) to (if (p.dark) Color(0xFF3A2E10) else Color(0xFFFFF1D6))
        PillTone.GOOD -> (if (p.dark) Color(0xFF7BE0A0) else Color(0xFF1F7A43)) to (if (p.dark) Color(0xFF10331F) else Color(0xFFDDF3E5))
        PillTone.BAD -> (if (p.dark) Color(0xFFFF8A80) else Color(0xFFB3261E)) to (if (p.dark) Color(0xFF3A1512) else Color(0xFFFDE2DF))
        PillTone.ACCENT -> AssetaColors.OnAmber to p.accent
        PillTone.NEUTRAL -> p.secondaryText to p.raised
    }
    Text(
        text, color = fg, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1,
        modifier = Modifier.clip(RoundedCornerShape(999.dp)).background(bg).padding(horizontal = 10.dp, vertical = 4.dp),
    )
}

/** Today / Week / Month (or any short choices) as a pill row. */
@Composable
fun <T> PeriodTabs(options: List<Pair<T, String>>, selected: T, onSelect: (T) -> Unit, modifier: Modifier = Modifier) {
    val p = palette
    Row(
        modifier.padding(horizontal = 20.dp).fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(p.cell).padding(4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        options.forEach { (value, label) ->
            val on = value == selected
            Box(
                Modifier.weight(1f).height(36.dp).clip(RoundedCornerShape(10.dp)).background(if (on) p.accent else Color.Transparent)
                    .clickable(role = Role.Tab, onClick = { onSelect(value) }),
                contentAlignment = Alignment.Center,
            ) {
                Text(label, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = if (on) AssetaColors.OnAmber else p.secondaryText)
            }
        }
    }
}

/** A full-width amber button (design "Save sale", "Submit for approval"). */
@Composable
fun PrimaryAction(label: String, enabled: Boolean = true, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val p = palette
    Box(
        modifier.padding(horizontal = 20.dp).fillMaxWidth().height(56.dp).clip(RoundedCornerShape(16.dp))
            .background(if (enabled) p.accent else p.raised)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, fontSize = 17.sp, fontWeight = FontWeight.Bold, color = if (enabled) AssetaColors.OnAmber else p.secondaryText)
    }
}

/** A full-width secondary button on a card background. */
@Composable
fun SecondaryAction(label: String, enabled: Boolean = true, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val p = palette
    Box(
        modifier.height(52.dp).clip(RoundedCornerShape(16.dp)).background(p.cell)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, color = if (enabled) Color.Unspecified else p.secondaryText)
    }
}

/** Chip choice ("Cash", "Bank", "M-money", "Credit"; "Registered customer" / "Walk-in"). */
@Composable
fun ChoiceChip(label: String, selected: Boolean, enabled: Boolean = true, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val p = palette
    Box(
        modifier.height(40.dp).clip(RoundedCornerShape(12.dp)).background(if (selected) p.accent else p.raised)
            .clickable(enabled = enabled, role = Role.RadioButton, onClick = onClick).padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = if (selected) AssetaColors.OnAmber else p.secondaryText, maxLines = 1)
    }
}

/** Amber progress bar (the split's "Accounted for"). */
@Composable
fun ShellProgress(fraction: Float, modifier: Modifier = Modifier) {
    LinearProgressIndicator(
        progress = { fraction.coerceIn(0f, 1f) },
        modifier = modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(999.dp)),
        color = palette.accent, trackColor = palette.raised, drawStopIndicator = {},
    )
}

/** Step header ("Step 1 of 3 · New reading") with three bars, the first [step] amber. */
@Composable
fun StepBars(step: Int, total: Int = 3, label: String? = null) {
    Column(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            repeat(total) { i ->
                Box(Modifier.weight(1f).height(4.dp).clip(RoundedCornerShape(999.dp)).background(if (i < step) palette.accent else palette.raised))
            }
        }
        label?.let { Text(it, fontSize = 13.sp, color = palette.secondaryText, modifier = Modifier.padding(top = 8.dp)) }
    }
}
