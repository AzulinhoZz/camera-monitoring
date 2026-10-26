package com.cameramonitoring.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = BrightBlue,
    onPrimary = Color.White,
    secondary = EmeraldGreen,
    onSecondary = Color.White,
    tertiary = DarkNavy,
    onTertiary = Color.White,
    background = BackgroundLight,
    onBackground = TextPrimaryLight,
    surface = SurfaceLight,
    onSurface = TextPrimaryLight,
    surfaceVariant = SurfaceVariantLight,
    onSurfaceVariant = TextSecondaryLight,
    error = CrimsonRed,
    onError = Color.White,
    outline = Color(0xFFCBD5E1)
)

private val DarkColorScheme = darkColorScheme(
    primary = BrightBlue,
    onPrimary = Color.White,
    secondary = EmeraldGreen,
    onSecondary = Color.White,
    tertiary = DarkNavy,
    onTertiary = Color.White,
    background = DarkBackground,
    onBackground = TextPrimaryDark,
    surface = DarkSurface,
    onSurface = TextPrimaryDark,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = TextSecondaryDark,
    error = CrimsonRed,
    onError = Color.White,
    outline = BorderDark
)

@Composable
fun CameraMonitoringTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
