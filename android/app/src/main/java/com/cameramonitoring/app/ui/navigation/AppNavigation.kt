package com.cameramonitoring.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.data.remote.ApiClient
import com.cameramonitoring.app.data.repository.AuthRepository
import com.cameramonitoring.app.data.repository.CameraRepository
import com.cameramonitoring.app.data.repository.EventRepository
import com.cameramonitoring.app.ui.auth.AuthViewModel
import com.cameramonitoring.app.ui.auth.LoginScreen
import com.cameramonitoring.app.ui.cameras.AddCameraScreen
import com.cameramonitoring.app.ui.cameras.AddCameraViewModel
import com.cameramonitoring.app.ui.dashboard.DashboardScreen
import com.cameramonitoring.app.ui.dashboard.DashboardViewModel
import com.cameramonitoring.app.ui.events.EventHistoryScreen
import com.cameramonitoring.app.ui.events.EventHistoryViewModel
import com.cameramonitoring.app.ui.stream.LiveStreamScreen
import com.cameramonitoring.app.ui.stream.LiveStreamViewModel

object Destinations {
    const val LOGIN = "login"
    const val DASHBOARD = "dashboard"
    const val ADD_CAMERA = "add_camera"
    const val STREAM = "stream/{cameraId}"
    const val EVENTS = "events"

    fun streamRoute(cameraId: String) = "stream/$cameraId"
}

@Composable
fun AppNavigation() {
    val context = LocalContext.current
    val navController = rememberNavController()

    val sessionManager = remember { SessionManager(context) }
    val apiService = remember {
        ApiClient.getApiService(
            sessionManager = sessionManager,
            onSessionExpired = {
                navController.navigate(Destinations.LOGIN) {
                    popUpTo(0) { inclusive = true }
                }
            }
        )
    }

    val authRepository = remember { AuthRepository(apiService, sessionManager) }
    val cameraRepository = remember { CameraRepository(apiService) }
    val eventRepository = remember { EventRepository(apiService) }

    val authViewModel = remember { AuthViewModel(authRepository) }
    val dashboardViewModel = remember { DashboardViewModel(cameraRepository) }
    val addCameraViewModel = remember { AddCameraViewModel(cameraRepository) }
    val liveStreamViewModel = remember { LiveStreamViewModel(cameraRepository, eventRepository) }
    val eventHistoryViewModel = remember { EventHistoryViewModel(eventRepository) }

    val startDestination = if (authRepository.isLoggedIn()) Destinations.DASHBOARD else Destinations.LOGIN

    NavHost(
        navController = navController,
        startDestination = startDestination
    ) {
        composable(Destinations.LOGIN) {
            LoginScreen(
                viewModel = authViewModel,
                onLoginSuccess = {
                    navController.navigate(Destinations.DASHBOARD) {
                        popUpTo(Destinations.LOGIN) { inclusive = true }
                    }
                }
            )
        }

        composable(Destinations.DASHBOARD) {
            DashboardScreen(
                viewModel = dashboardViewModel,
                userEmail = authViewModel.getUserEmail(),
                onAddCameraClick = { navController.navigate(Destinations.ADD_CAMERA) },
                onCameraSelect = { cameraId -> navController.navigate(Destinations.streamRoute(cameraId)) },
                onEventsClick = { navController.navigate(Destinations.EVENTS) },
                onLogoutClick = {
                    authViewModel.logout()
                    navController.navigate(Destinations.LOGIN) {
                        popUpTo(Destinations.DASHBOARD) { inclusive = true }
                    }
                }
            )
        }

        composable(Destinations.ADD_CAMERA) {
            AddCameraScreen(
                viewModel = addCameraViewModel,
                onBackClick = { navController.popBackStack() },
                onCameraAdded = {
                    navController.popBackStack()
                }
            )
        }

        composable(
            route = Destinations.STREAM,
            arguments = listOf(navArgument("cameraId") { type = NavType.StringType })
        ) { backStackEntry ->
            val cameraId = backStackEntry.arguments?.getString("cameraId") ?: ""
            LiveStreamScreen(
                cameraId = cameraId,
                viewModel = liveStreamViewModel,
                onBackClick = { navController.popBackStack() }
            )
        }

        composable(Destinations.EVENTS) {
            EventHistoryScreen(
                viewModel = eventHistoryViewModel,
                onBackClick = { navController.popBackStack() }
            )
        }
    }
}
