package com.derf.pq

import androidx.compose.material3.DarkColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val ObsidianBackground = Color(0xFF0E0E0E)
val CardSurface        = Color(0xFF18181C)
val InputSurface       = Color(0xFF222228)
val ElectricCyan       = Color(0xFF00F0FF)
val ActiveGreen        = Color(0xFF00FF9D)
val CrispWhite         = Color(0xFFFFFFFF)
val MutedText          = Color(0xFFA0A0A8)
val BorderColor        = Color(0xFF2A2A32)
val ErrorRed           = Color(0xFFFF5252)

private val StitchDarkColorScheme = DarkColorScheme(
    primary = ElectricCyan,
    onPrimary = ObsidianBackground,
    secondary = ActiveGreen,
    onSecondary = ObsidianBackground,
    background = ObsidianBackground,
    onBackground = CrispWhite,
    surface = CardSurface,
    onSurface = CrispWhite,
    surfaceVariant = InputSurface,
    onSurfaceVariant = CrispWhite,
    error = ErrorRed,
    onError = CrispWhite,
    outline = BorderColor
)

@Composable
fun DerfStitchTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = StitchDarkColorScheme,
        content = content
    )
}
