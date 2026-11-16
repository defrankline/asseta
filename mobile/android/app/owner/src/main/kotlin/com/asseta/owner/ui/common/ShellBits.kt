package com.asseta.owner.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.asseta.core.ui.shell.ChoiceChip
import com.asseta.core.ui.theme.AssetaColors
import com.asseta.core.ui.theme.palette

/*
 * Owner-app pieces of the ADR-008 shell look that the shared core/ui shell does not have: a tappable item card, a row
 * of filter chips that scrolls, small labels and the amber / red buttons of a card.
 */

/** A rounded card that opens something when tapped ([onClick] null: not tappable). */
@Composable
fun ItemCard(onClick: (() -> Unit)? = null, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val base = modifier.padding(horizontal = 20.dp).fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(palette.cell)
    Column(
        (if (onClick != null) base.clickable(role = Role.Button, onClick = onClick) else base).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
        content = content,
    )
}

/** "MACHINE REPORT" on the left, "today 07:40" on the right. */
@Composable
fun KindLine(kind: String, time: String?) {
    Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, verticalAlignment = Alignment.CenterVertically) {
        Text(kind, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp, color = palette.secondaryText, modifier = Modifier.weight(1f))
        time?.let { Text(it, fontSize = 12.sp, color = palette.secondaryText) }
    }
}

/** Bold card title. */
@Composable
fun CardTitle(text: String) = Text(text, fontSize = 16.sp, fontWeight = FontWeight.Bold)

/** Card detail line; [accent] = amber (the design's figures line). */
@Composable
fun CardDetail(text: String, accent: Boolean = false, color: Color? = null) =
    Text(text, fontSize = 14.sp, color = color ?: if (accent) palette.accent else palette.secondaryText)

/** Filter chips in one scrolling row. */
@Composable
fun <T> ChipRow(options: List<Pair<T, String>>, selected: T, onSelect: (T) -> Unit) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        options.forEach { (value, label) -> ChoiceChip(label, value == selected) { onSelect(value) } }
    }
}

/** A card's pair of buttons ("Reject" / "Approve credit"); the right one amber. */
@Composable
fun CardButtons(left: String?, right: String?, enabled: Boolean, onLeft: () -> Unit, onRight: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        left?.let { ShellButton(it, primary = false, enabled = enabled, modifier = Modifier.weight(1f), onClick = onLeft) }
        right?.let { ShellButton(it, primary = true, enabled = enabled, modifier = Modifier.weight(1f), onClick = onRight) }
    }
}

/** A 48 dp button: amber when [primary], else on the raised colour. */
@Composable
fun ShellButton(label: String, primary: Boolean, enabled: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val p = palette
    Box(
        modifier.height(48.dp).clip(RoundedCornerShape(12.dp))
            .background(if (primary && enabled) p.accent else p.raised)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            label, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
            color = when {
                !enabled -> p.secondaryText
                primary -> AssetaColors.OnAmber
                else -> Color.Unspecified
            },
        )
    }
}

/** Space between cards of a list. */
@Composable
fun CardGap() = Box(Modifier.height(10.dp))
