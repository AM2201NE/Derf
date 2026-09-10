package com.derf.pq

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Apple HIG / Frosted Obsidian Material Tokens
val ObsidianBackground = Color(0xFF101014)
val CardSurface        = Color(0xFF1C1C22)
val InputSurface       = Color(0xFF262630)
val ElectricCyan       = Color(0xFF00E5FF)
val ActiveGreen        = Color(0xFF30D158)
val CrispWhite         = Color(0xFFF2F2F7)
val MutedText          = Color(0xFF8E8E93)
val BorderColor        = Color(0xFF2C2C36)
val ErrorRed           = Color(0xFFFF453A)

private val AppleDesignColorScheme = darkColorScheme(
    primary = ElectricCyan,
    onPrimary = Color(0xFF000000),
    secondary = ActiveGreen,
    onSecondary = Color(0xFF000000),
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
        colorScheme = AppleDesignColorScheme,
        content = content
    )
}
