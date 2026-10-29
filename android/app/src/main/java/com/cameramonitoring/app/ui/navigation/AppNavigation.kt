package com.cameramonitoring.app.ui.navigation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
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
import com.cameramonitoring.app.data.repository.StorageRepository
import com.cameramonitoring.app.ui.account.AccountScreen
import com.cameramonitoring.app.ui.auth.AuthViewModel
import com.cameramonitoring.app.ui.auth.LoginScreen
import com.cameramonitoring.app.ui.auth.RegisterScreen
import com.cameramonitoring.app.ui.auth.WelcomeScreen
import com.cameramonitoring.app.ui.cameras.AddCameraScreen
import com.cameramonitoring.app.ui.cameras.AddCameraViewModel
import com.cameramonitoring.app.ui.dashboard.DashboardScreen
import com.cameramonitoring.app.ui.dashboard.DashboardViewModel
import com.cameramonitoring.app.ui.events.EventHistoryScreen
import com.cameramonitoring.app.ui.events.EventHistoryViewModel
import com.cameramonitoring.app.ui.storage.StorageManagementScreen
import com.cameramonitoring.app.ui.storage.StorageViewModel
import com.cameramonitoring.app.ui.stream.LiveStreamScreen
import com.cameramonitoring.app.ui.stream.LiveStreamViewModel
import com.cameramonitoring.app.ui.vision.VisionRulesScreen

object Destinations {
    const val WELCOME = "welcome"
    const val LOGIN = "login"
    const val REGISTER = "register"
    const val DASHBOARD = "dashboard"
    const val ADD_CAMERA = "add_camera"
    const val VISION = "vision/{cameraId}"
    const val STREAM = "stream/{cameraId}"
    const val EVENTS = "events"
    const val STORAGE = "storage"
    const val ACCOUNT = "account"

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
                navController.navigate(Destinations.WELCOME) {
                    popUpTo(0) { inclusive = true }
                }
            }
        )
    }

    val authRepository = remember { AuthRepository(apiService, sessionManager) }
    val cameraRepository = remember { CameraRepository(apiService) }
    val eventRepository = remember { EventRepository(apiService) }
    val storageRepository = remember { StorageRepository(apiService) }

    val authViewModel = remember { AuthViewModel(authRepository) }
    val dashboardViewModel = remember { DashboardViewModel(cameraRepository, eventRepository) }
    val addCameraViewModel = remember { AddCameraViewModel(cameraRepository) }
    val storageViewModel = remember { StorageViewModel(storageRepository) }

    val startDestination = if (authRepository.isLoggedIn()) Destinations.DASHBOARD else Destinations.WELCOME

    NavHost(
        navController = navController,
        startDestination = startDestination
    ) {
        composable(Destinations.WELCOME) {
            WelcomeScreen(
                onLoginClick = { navController.navigate(Destinations.LOGIN) },
                onRegisterClick = { navController.navigate(Destinations.REGISTER) }
            )
        }

        composable(Destinations.LOGIN) {
            LoginScreen(
                viewModel = authViewModel,
                onLoginSuccess = {
                    navController.navigate(Destinations.DASHBOARD) {
                        popUpTo(Destinations.WELCOME) { inclusive = true }
                    }
                },
                onRegisterClick = { navController.navigate(Destinations.REGISTER) }
            )
        }

        composable(Destinations.REGISTER) {
            RegisterScreen(
                viewModel = authViewModel,
                onBackClick = { navController.popBackStack() },
                onRegisterSuccess = {
                    navController.navigate(Destinations.DASHBOARD) {
                        popUpTo(Destinations.WELCOME) { inclusive = true }
                    }
                }
            )
        }

        composable(Destinations.DASHBOARD) {
            DashboardScreen(
                viewModel = dashboardViewModel,
                userFullName = authViewModel.getUserFullName(),
                userEmail = authViewModel.getUserEmail(),
                onAddCameraClick = { navController.navigate(Destinations.ADD_CAMERA) },
                onCameraSelect = { cameraId -> navController.navigate(Destinations.streamRoute(cameraId)) },
                onEventsClick = { navController.navigate(Destinations.EVENTS) },
                onPendingEventsClick = { cameraId -> navController.navigate("events/camera/${android.net.Uri.encode(cameraId)}") },
                onStorageClick = { navController.navigate(Destinations.STORAGE) },
                onAccountClick = { navController.navigate(Destinations.ACCOUNT) }
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
            val liveStreamViewModel: LiveStreamViewModel = viewModel(viewModelStoreOwner = backStackEntry, factory = remember(backStackEntry) { ScreenModelFactory { LiveStreamViewModel(cameraRepository, eventRepository) } })
            LiveStreamScreen(
                cameraId = cameraId,
                viewModel = liveStreamViewModel,
                onVisionRules = { navController.navigate("vision/$cameraId") },
                onBackClick = { navController.popBackStack() }
            )
        }

        composable(Destinations.VISION, arguments = listOf(navArgument("cameraId") { type = NavType.StringType })) { entry ->
            VisionRulesScreen(entry.arguments?.getString("cameraId") ?: "", apiService) { navController.popBackStack() }
        }

        composable("events/camera/{cameraId}", arguments = listOf(navArgument("cameraId") { type = NavType.StringType })) { entry ->
            val eventHistoryViewModel: EventHistoryViewModel = viewModel(viewModelStoreOwner = entry, factory = remember(entry) { ScreenModelFactory { EventHistoryViewModel(eventRepository, storageRepository, cameraRepository) } })
            EventHistoryScreen(viewModel = eventHistoryViewModel, initialCameraId = entry.arguments?.getString("cameraId"),
                initialPending = true, onBackClick = { navController.popBackStack() },
                onStorageClick = { navController.navigate(Destinations.STORAGE) })
        }

        composable(Destinations.EVENTS) { entry ->
            val eventHistoryViewModel: EventHistoryViewModel = viewModel(viewModelStoreOwner = entry, factory = remember(entry) { ScreenModelFactory { EventHistoryViewModel(eventRepository, storageRepository, cameraRepository) } })
            EventHistoryScreen(
                viewModel = eventHistoryViewModel,
                onBackClick = { navController.popBackStack() },
                onStorageClick = { navController.navigate(Destinations.STORAGE) }
            )
        }

        composable(Destinations.STORAGE) {
            StorageManagementScreen(
                viewModel = storageViewModel,
                onBackClick = { navController.popBackStack() }
            )
        }

        composable(Destinations.ACCOUNT) {
            AccountScreen(
                userEmail = authViewModel.getUserEmail(),
                userFullName = authViewModel.getUserFullName(),
                onLogoutClick = {
                    authViewModel.logout()
                    navController.navigate(Destinations.WELCOME) {
                        popUpTo(Destinations.DASHBOARD) { inclusive = true }
                    }
                }
            )
        }
    }
}


private class ScreenModelFactory(private val build: () -> ViewModel) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        val model = build()
        require(modelClass.isInstance(model))
        @Suppress("UNCHECKED_CAST")
        return model as T
    }
}
