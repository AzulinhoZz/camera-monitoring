package com.cameramonitoring.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.data.remote.ApiClient
import com.cameramonitoring.app.data.repository.AuthRepository
import com.cameramonitoring.app.ui.navigation.AppNavigation
import com.cameramonitoring.app.ui.theme.CameraMonitoringTheme
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            Log.i("MainActivity", "Notification permission granted")
        } else {
            Log.w("MainActivity", "Notification permission denied")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        requestNotificationPermission()
        initFCMToken()

        setContent {
            CameraMonitoringTheme {
                AppNavigation()
            }
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun initFCMToken() {
        try {
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                if (task.isSuccessful && task.result != null) {
                    val token = task.result
                    Log.i("MainActivity", "FCM token registered locally")
                    val sessionManager = SessionManager(applicationContext)
                    sessionManager.saveFCMToken(token)

                    if (sessionManager.isLoggedIn()) {
                        val apiService = ApiClient.getApiService(sessionManager)
                        val authRepository = AuthRepository(apiService, sessionManager)
                        CoroutineScope(Dispatchers.IO).launch {
                            authRepository.registerFCMToken(token)
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.w("MainActivity", "FirebaseMessaging is not available")
        }
    }
}
