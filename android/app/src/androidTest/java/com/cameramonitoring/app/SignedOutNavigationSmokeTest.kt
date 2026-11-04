package com.cameramonitoring.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.ui.navigation.AppNavigation
import com.cameramonitoring.app.ui.theme.CameraMonitoringTheme
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Signed-out QA installation only. Never clears a session or submits network credentials. */
@RunWith(AndroidJUnit4::class)
class SignedOutNavigationSmokeTest {
    @get:Rule
    val compose = createComposeRule()

    @Before
    fun requireSignedOutInstallation() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        check(!SessionManager(context).isLoggedIn()) {
            "Use a dedicated signed-out QA installation; this test never erases app data."
        }
        compose.setContent { CameraMonitoringTheme { AppNavigation() } }
    }

    @Test
    fun welcomeOpensLoginAndRejectsEmptyCredentialsLocally() {
        compose.onNodeWithText("Iniciar sesión").assertIsDisplayed().performClick()
        compose.onNodeWithText("Correo electrónico").assertIsDisplayed()
        compose.onNodeWithText("Contraseña").assertIsDisplayed()
        compose.onNodeWithText("Entrar").performClick()
        compose.onNodeWithText("Por favor, ingrese correo y contraseña").assertIsDisplayed()
    }

    @Test
    fun welcomeOpensRegistration() {
        compose.onNodeWithText("Crear cuenta").assertIsDisplayed().performClick()
        compose.onNodeWithText("Únete a CameraMonitoring").assertIsDisplayed()
    }
}
