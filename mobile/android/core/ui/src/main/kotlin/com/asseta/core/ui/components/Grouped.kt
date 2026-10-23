package com.asseta.core.ui.components

import androidx.annotation.DrawableRes
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.layout.ParentDataModifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.asseta.core.ui.R
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette

/*
 * Building blocks that give the Android apps the same layout as the iOS apps' inset-grouped `List`/`Form`:
 * uppercase grey section headers, rounded white (dark: #1C1C1E) groups with hairline separators between rows,
 * grey footers, chevrons on rows that open a screen, capsule pills and bordered filter chips.
 */

private val CellMargin = 16.dp
private val CellInset = 16.dp
private val RowMinHeight = 44.dp
private val RowVertical = 11.dp
private val GroupShape = RoundedCornerShape(10.dp)

/** Marks a row of a [GroupedSection] that spans the whole group without insets (e.g. a map; iOS `listRowInsets(EdgeInsets())`). */
fun Modifier.fullBleed(): Modifier = this.then(FullBleed)

private object FullBleed : ParentDataModifier {
    override fun Density.modifyParentData(parentData: Any?): Any = true
}

/** Uppercase grey section header (iOS grouped list section header). */
@Composable
fun SectionHeader(text: String, modifier: Modifier = Modifier, margin: Dp = CellMargin) {
    Text(
        text.uppercase(), style = AssetaType.sectionHeader, color = palette.secondaryText,
        modifier = modifier.fillMaxWidth().padding(start = margin + CellInset, end = margin + CellInset, bottom = 7.dp)
            .semantics { heading() },
    )
}

/** Grey explanatory text under a group (iOS section footer). */
@Composable
fun SectionFooter(text: String, modifier: Modifier = Modifier, margin: Dp = CellMargin) {
    Text(
        text, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText,
        modifier = modifier.fillMaxWidth().padding(start = margin + CellInset, end = margin + CellInset, top = 7.dp),
    )
}

/**
 * One inset-grouped section: optional [header], a rounded group whose direct children become rows separated by
 * hairlines (each at least 44 dp tall, inset 16 dp), and an optional [footer]. Children that draw nothing take no row.
 */
@Composable
fun GroupedSection(
    modifier: Modifier = Modifier,
    header: String? = null,
    footer: String? = null,
    /** Side margin of the group; 0 when the parent already pads its content by 16 dp. */
    margin: Dp = CellMargin,
    spacingAfter: Dp = 24.dp,
    content: @Composable () -> Unit,
) {
    Column(modifier.fillMaxWidth().padding(bottom = spacingAfter)) {
        header?.let { SectionHeader(it, margin = margin) }
        GroupedRows(Modifier.padding(horizontal = margin), content)
        footer?.let { SectionFooter(it, margin = margin) }
    }
}

/** The rounded group of a [GroupedSection] (rows with separators), without header or footer. */
@Composable
fun GroupedRows(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    val p = palette
    val separators = remember { ArrayList<Int>() }
    Layout(
        content = content,
        modifier = modifier.fillMaxWidth().clip(GroupShape).background(p.cell).drawWithContent {
            drawContent()
            val start = CellInset.toPx()
            separators.forEach { y ->
                drawLine(p.separator, Offset(start, y.toFloat()), Offset(size.width, y.toFloat()), strokeWidth = 1f)
            }
        },
    ) { measurables, constraints ->
        val width = constraints.maxWidth
        val inset = CellInset.roundToPx()
        val vertical = RowVertical.roundToPx()
        val minRow = RowMinHeight.roundToPx()
        val placeables = measurables.map { m ->
            val bleed = m.parentData == true
            val childWidth = if (bleed) width else (width - 2 * inset).coerceAtLeast(0)
            bleed to m.measure(constraints.copy(minWidth = 0, maxWidth = childWidth, minHeight = 0, maxHeight = Int.MAX_VALUE))
        }.filter { it.second.height > 0 }
        val heights = placeables.map { (bleed, pl) -> if (bleed) pl.height else maxOf(pl.height + 2 * vertical, minRow) }
        layout(width, heights.sum()) {
            separators.clear()
            var y = 0
            placeables.forEachIndexed { i, (bleed, pl) ->
                if (i > 0) separators.add(y)
                val rowHeight = heights[i]
                pl.placeRelative(if (bleed) 0 else inset, y + (rowHeight - pl.height) / 2)
                y += rowHeight
            }
        }
    }
}

/** A row of a lazy grouped list (see [groupedSection]). */
class GroupedItem(
    val key: Any,
    val onClick: (() -> Unit)? = null,
    /** Show the trailing chevron of a row that opens another screen (iOS `NavigationLink`). */
    val chevron: Boolean = onClick != null,
    val content: @Composable () -> Unit,
)

/**
 * A lazy inset-grouped section: [header], one item per row with separators and rounded first/last rows, [footer].
 * [keyPrefix] keeps keys unique when a list has several sections.
 */
fun LazyListScope.groupedSection(keyPrefix: String, items: List<GroupedItem>, header: String? = null, footer: String? = null) {
    header?.let { item(key = "$keyPrefix-header") { SectionHeader(it) } }
    items.forEachIndexed { i, row ->
        item(key = "$keyPrefix-${row.key}") { GroupedCell(first = i == 0, last = i == items.lastIndex, onClick = row.onClick, chevron = row.chevron, content = row.content) }
    }
    if (items.isNotEmpty() || header != null || footer != null) {
        item(key = "$keyPrefix-footer") {
            Column(Modifier.padding(bottom = 24.dp)) { footer?.let { SectionFooter(it) } }
        }
    }
}

/** One row of a grouped list, rounded at the top when [first] and at the bottom when [last]. */
@Composable
fun GroupedCell(first: Boolean, last: Boolean, onClick: (() -> Unit)? = null, chevron: Boolean = onClick != null, content: @Composable () -> Unit) {
    val p = palette
    val radius = 10.dp
    val shape = RoundedCornerShape(
        topStart = if (first) radius else 0.dp, topEnd = if (first) radius else 0.dp,
        bottomStart = if (last) radius else 0.dp, bottomEnd = if (last) radius else 0.dp,
    )
    Box(Modifier.padding(horizontal = CellMargin).fillMaxWidth().clip(shape).background(p.cell)) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = RowMinHeight)
                .then(if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier)
                .padding(start = CellInset, end = if (chevron) 8.dp else CellInset, top = RowVertical, bottom = RowVertical),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.weight(1f)) { content() }
            if (chevron) Chevron()
        }
        if (!first) {
            Box(Modifier.align(Alignment.TopStart).padding(start = CellInset).fillMaxWidth().height(0.5.dp).background(p.separator))
        }
    }
}

/** Trailing grey chevron of a row that opens another screen. */
@Composable
fun Chevron() {
    Icon(painterResource(R.drawable.ic_chevron_right), contentDescription = null, tint = palette.secondaryText.copy(alpha = 0.6f),
        modifier = Modifier.padding(start = 8.dp).size(20.dp))
}

/** Label on the left, grey value on the right (iOS `LabeledContent`); [trailing] replaces the value (e.g. a pill). */
@Composable
fun LabeledValue(label: String, value: String = "", valueColor: Color = Color.Unspecified, trailing: (@Composable () -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f).padding(end = 12.dp))
        if (trailing != null) {
            trailing()
        } else {
            Text(
                value, style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.End,
                color = if (valueColor == Color.Unspecified) palette.secondaryText else valueColor,
                modifier = Modifier.weight(1f, fill = false),
            )
        }
    }
}

/** A row that opens a screen: primary text, optional [badge], trailing chevron (iOS `NavigationLink` in a list). */
@Composable
fun NavigationRow(title: String, @DrawableRes icon: Int? = null, badge: String? = null, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = 22.dp).clickable(role = Role.Button, onClick = onClick),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        icon?.let { Icon(painterResource(it), contentDescription = null, tint = palette.accent, modifier = Modifier.padding(end = 14.dp).size(22.dp)) }
        Text(title, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
        badge?.let { Text(it, style = MaterialTheme.typography.bodyLarge, color = palette.secondaryText) }
        Chevron()
    }
}

/** Arbitrary row content that opens a screen, with a trailing chevron (iOS `NavigationLink { RowView() }`). */
@Composable
fun LinkRow(onClick: () -> Unit, content: @Composable () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(role = Role.Button, onClick = onClick), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.weight(1f)) { content() }
        Chevron()
    }
}

/** A row that performs an action: accent-coloured text (iOS `Button` in a list); [destructive] makes it red. */
@Composable
fun ButtonRow(
    title: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    destructive: Boolean = false,
    @DrawableRes icon: Int? = null,
    onClick: () -> Unit,
) {
    val p = palette
    val color = when {
        !enabled -> p.secondaryText.copy(alpha = 0.6f)
        destructive -> p.offline
        else -> p.accent
    }
    Row(
        modifier.fillMaxWidth().heightIn(min = 22.dp).clickable(enabled = enabled, role = Role.Button, onClick = onClick),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        icon?.let { Icon(painterResource(it), contentDescription = null, tint = color, modifier = Modifier.padding(end = 14.dp).size(22.dp)) }
        Text(title, style = MaterialTheme.typography.bodyLarge, color = color)
    }
}

/** Capsule label tinted with [color] (iOS `Pill` / `StatusBadge`): text in the colour on a 15 % wash. */
@Composable
fun Pill(text: String, color: Color, modifier: Modifier = Modifier) {
    Text(
        text, style = MaterialTheme.typography.labelMedium, color = color, maxLines = 1,
        modifier = modifier.background(color.copy(alpha = 0.15f), RoundedCornerShape(50)).padding(horizontal = 8.dp, vertical = 3.dp),
    )
}

/** Bordered filter button (iOS `.bordered` button tinted amber when selected, grey otherwise). */
@Composable
fun FilterChipButton(label: String, selected: Boolean, onClick: () -> Unit) {
    val p = palette
    val tint = if (selected) p.accent else p.secondaryText
    Text(
        label, style = MaterialTheme.typography.bodySmall, color = if (selected) p.accent else MaterialTheme.colorScheme.onSurface,
        modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(tint.copy(alpha = if (selected) 0.2f else 0.14f))
            .clickable(role = Role.Tab, onClick = onClick).semantics { this.selected = selected }
            .padding(horizontal = 12.dp, vertical = 7.dp),
    )
}

/** Horizontally scrolling row of [FilterChipButton]s; [options] are (value, label) pairs. */
@Composable
fun <T> FilterChipRow(options: List<Pair<T, String>>, selection: T, onSelect: (T) -> Unit, modifier: Modifier = Modifier) {
    Row(
        modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        options.forEach { (value, label) -> FilterChipButton(label, selection == value) { onSelect(value) } }
    }
}

/** Rounded grey search field with a magnifier (iOS `.searchable` field under the navigation title). */
@Composable
fun SearchField(query: String, onQuery: (String) -> Unit, placeholder: String, modifier: Modifier = Modifier) {
    val p = palette
    Row(
        modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).clip(RoundedCornerShape(10.dp))
            .background(p.secondaryText.copy(alpha = 0.14f)).padding(horizontal = 8.dp).heightIn(min = 36.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(painterResource(R.drawable.ic_search), contentDescription = null, tint = p.secondaryText, modifier = Modifier.size(20.dp))
        Box(Modifier.weight(1f).padding(start = 6.dp)) {
            if (query.isEmpty()) Text(placeholder, style = MaterialTheme.typography.bodyLarge, color = p.secondaryText, maxLines = 1)
            BasicTextField(
                query, onQuery, singleLine = true, modifier = Modifier.fillMaxWidth().semantics { contentDescription = placeholder },
                textStyle = MaterialTheme.typography.bodyLarge.copy(color = MaterialTheme.colorScheme.onSurface),
                cursorBrush = SolidColor(p.accent),
            )
        }
    }
}

/** Empty or unavailable content: grey symbol, bold title, grey explanation and optional actions (iOS `ContentUnavailableView`). */
// `message` stays the second (positional) parameter, as in the iOS `EmptyState(title:message:)`.
@Suppress("ModifierParameter")
@Composable
fun EmptyState(
    title: String,
    message: String? = null,
    @DrawableRes icon: Int? = R.drawable.ic_empty_tray,
    modifier: Modifier = Modifier,
    actions: (@Composable () -> Unit)? = null,
) {
    Column(
        modifier.fillMaxWidth().padding(horizontal = 32.dp, vertical = 32.dp).semantics(mergeDescendants = true) {},
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        icon?.let { Icon(painterResource(it), contentDescription = null, tint = palette.secondaryText, modifier = Modifier.padding(bottom = 4.dp).size(48.dp)) }
        Text(title, style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
        message?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = palette.secondaryText, textAlign = TextAlign.Center) }
        actions?.let { Box(Modifier.padding(top = 8.dp)) { it() } }
    }
}

/** Leading content of a top bar row (e.g. an account menu); see [AssetaTopBar]. */
typealias TopBarSlot = @Composable RowScope.() -> Unit
