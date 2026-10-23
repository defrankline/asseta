package com.asseta.core.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** Brand constants (see `branding/README.md`); the same values as iOS `Brand`. */
object AssetaColors {
    val Slate = Color(0xFF0F2A3D)
    val SlateLight = Color(0xFF2B4A60)
    val Amber = Color(0xFFF5A300)
    val AmberDark = Color(0xFFB87A00)
    val OnAmber = Color(0xFF1B1300)
    val OffWhite = Color(0xFFF7F8FA)
    val Error = Color(0xFFB3261E)
}

/**
 * Colours both apps use besides the Material scheme, with the same values as iOS `Palette` (AssetaAppShell): the
 * grouped-list surfaces of iOS (background, cells, separators, secondary text) and the status colours (live green,
 * stale amber, offline red, recent blue, neutral grey) for pills, markers and tinted figures.
 */
@Immutable
data class AssetaPalette(
    val accent: Color,
    val groupedBackground: Color,
    val cell: Color,
    val separator: Color,
    val secondaryText: Color,
    val chrome: Color,
    val live: Color,
    val recent: Color,
    val stale: Color,
    val offline: Color,
    val neutral: Color,
    val dark: Boolean,
) {
    val critical: Color get() = offline
    val warning: Color get() = stale
    val info: Color get() = recent
}

val LightPalette = AssetaPalette(
    accent = AssetaColors.Amber,
    groupedBackground = Color(0xFFF2F2F7),
    cell = Color(0xFFFFFFFF),
    separator = Color(0xFFC6C6C8),
    secondaryText = Color(0xFF6C6C70),
    chrome = Color(0xFFF9F9F9),
    live = Color(0xFF248A3D),
    recent = Color(0xFF0071A4),
    stale = AssetaColors.AmberDark,
    offline = Color(0xFFD70015),
    neutral = Color(0xFF6C6C70),
    dark = false,
)

val DarkPalette = AssetaPalette(
    accent = AssetaColors.Amber,
    groupedBackground = Color(0xFF000000),
    cell = Color(0xFF1C1C1E),
    separator = Color(0xFF38383A),
    secondaryText = Color(0xFF98989F),
    chrome = Color(0xFF161616),
    live = Color(0xFF30D158),
    recent = Color(0xFF64D2FF),
    stale = AssetaColors.Amber,
    offline = Color(0xFFFF453A),
    neutral = Color(0xFF98989F),
    dark = true,
)

val LocalAssetaPalette = staticCompositionLocalOf { LightPalette }

/** The palette of the current (system) light/dark mode. */
val palette: AssetaPalette
    @Composable @ReadOnlyComposable get() = LocalAssetaPalette.current

private fun scheme(p: AssetaPalette) = if (p.dark) {
    darkColorScheme(
        primary = p.accent, onPrimary = AssetaColors.Slate,
        primaryContainer = AssetaColors.AmberDark, onPrimaryContainer = Color.White,
        secondary = p.accent, onSecondary = AssetaColors.Slate,
        secondaryContainer = Color(0xFF3A2E12), onSecondaryContainer = Color.White,
        background = p.groupedBackground, onBackground = Color.White,
        surface = p.groupedBackground, onSurface = Color.White,
        surfaceVariant = p.cell, onSurfaceVariant = p.secondaryText,
        surfaceContainerLowest = p.groupedBackground, surfaceContainerLow = p.cell, surfaceContainer = p.chrome,
        surfaceContainerHigh = p.cell, surfaceContainerHighest = Color(0xFF2C2C2E),
        outline = Color(0xFF545458), outlineVariant = p.separator,
        error = p.offline, onError = Color.White, errorContainer = Color(0xFF4A1512), onErrorContainer = Color(0xFFFFDAD6),
    )
} else {
    lightColorScheme(
        primary = p.accent, onPrimary = AssetaColors.Slate,
        primaryContainer = Color(0xFFFFE2A8), onPrimaryContainer = AssetaColors.OnAmber,
        secondary = p.accent, onSecondary = AssetaColors.Slate,
        secondaryContainer = Color(0xFFFFF1D6), onSecondaryContainer = AssetaColors.OnAmber,
        background = p.groupedBackground, onBackground = Color.Black,
        surface = p.groupedBackground, onSurface = Color.Black,
        surfaceVariant = Color(0xFFE5E5EA), onSurfaceVariant = p.secondaryText,
        surfaceContainerLowest = p.cell, surfaceContainerLow = p.cell, surfaceContainer = p.chrome,
        surfaceContainerHigh = p.cell, surfaceContainerHighest = Color(0xFFE5E5EA),
        outline = Color(0xFFAEAEB2), outlineVariant = p.separator,
        error = p.offline, onError = Color.White, errorContainer = Color(0xFFFFDAD6), onErrorContainer = Color(0xFF410002),
    )
}

/** Type ramp sized like iOS Dynamic Type defaults (large title 34, title3 20, headline/body 17, footnote 13, caption 12). */
private val IosTypography = Typography().run {
    copy(
        displaySmall = displaySmall.copy(fontSize = 34.sp, lineHeight = 41.sp, fontWeight = FontWeight.Bold),
        headlineSmall = headlineSmall.copy(fontSize = 22.sp, lineHeight = 28.sp, fontWeight = FontWeight.Bold),
        titleLarge = titleLarge.copy(fontSize = 20.sp, lineHeight = 25.sp, fontWeight = FontWeight.Bold),
        titleMedium = titleMedium.copy(fontSize = 17.sp, lineHeight = 22.sp, fontWeight = FontWeight.SemiBold),
        titleSmall = titleSmall.copy(fontSize = 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.SemiBold),
        bodyLarge = bodyLarge.copy(fontSize = 17.sp, lineHeight = 22.sp),
        bodyMedium = bodyMedium.copy(fontSize = 15.sp, lineHeight = 20.sp),
        bodySmall = bodySmall.copy(fontSize = 13.sp, lineHeight = 18.sp),
        labelLarge = labelLarge.copy(fontSize = 15.sp, lineHeight = 20.sp),
        labelMedium = labelMedium.copy(fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.SemiBold),
        labelSmall = labelSmall.copy(fontSize = 11.sp, lineHeight = 13.sp),
    )
}

/** iOS-sized text styles not in the Material ramp. */
object AssetaType {
    val largeTitle = TextStyle(fontSize = 34.sp, lineHeight = 41.sp, fontWeight = FontWeight.Bold)
    val navTitle = TextStyle(fontSize = 17.sp, lineHeight = 22.sp, fontWeight = FontWeight.SemiBold)
    val sectionHeader = TextStyle(fontSize = 13.sp, lineHeight = 18.sp)
    val headline = TextStyle(fontSize = 17.sp, lineHeight = 22.sp, fontWeight = FontWeight.SemiBold)
    val subheadline = TextStyle(fontSize = 15.sp, lineHeight = 20.sp)
    val footnote = TextStyle(fontSize = 13.sp, lineHeight = 18.sp)
    val caption = TextStyle(fontSize = 12.sp, lineHeight = 16.sp)
}

/**
 * Brand theme shared by the Supervisor and Owner apps; follows the system light/dark setting like the iOS apps.
 * Dynamic colour is intentionally off to keep branding.
 */
@Composable
fun AssetaTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val p = if (darkTheme) DarkPalette else LightPalette
    CompositionLocalProvider(LocalAssetaPalette provides p) {
        MaterialTheme(colorScheme = scheme(p), typography = IosTypography, content = content)
    }
}
