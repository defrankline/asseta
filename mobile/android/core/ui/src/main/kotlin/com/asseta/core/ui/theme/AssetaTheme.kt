package com.asseta.core.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

object AssetaColors {
    val Slate = Color(0xFF0F2A3D)
    val SlateLight = Color(0xFF2B4A60)
    val Amber = Color(0xFFF5A300)
    val AmberDark = Color(0xFFB87A00)
    val OnAmber = Color(0xFF1B1300)
    val Surface = Color(0xFFF7F8FA)
    val Error = Color(0xFFB3261E)
}

private val Light = lightColorScheme(
    primary = AssetaColors.Slate,
    onPrimary = Color.White,
    primaryContainer = AssetaColors.SlateLight,
    onPrimaryContainer = Color.White,
    secondary = AssetaColors.Amber,
    onSecondary = AssetaColors.OnAmber,
    background = AssetaColors.Surface,
    surface = Color.White,
    error = AssetaColors.Error,
)

private val Dark = darkColorScheme(
    primary = AssetaColors.Amber,
    onPrimary = AssetaColors.OnAmber,
    primaryContainer = AssetaColors.AmberDark,
    secondary = AssetaColors.Amber,
    onSecondary = AssetaColors.OnAmber,
    background = AssetaColors.Slate,
    surface = AssetaColors.SlateLight,
)

/** Brand theme shared by the Supervisor and Owner apps. Dynamic color is intentionally off to keep branding. */
@Composable
fun AssetaTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (darkTheme) Dark else Light, content = content)
}
