package com.cameramonitoring.app.data.repository

import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.data.model.FCMTokenRequest
import com.cameramonitoring.app.data.model.LoginRequest
import com.cameramonitoring.app.data.remote.ApiService

class AuthRepository(
    private val apiService: ApiService,
    private val sessionManager: SessionManager
) {
    suspend fun login(email: String, password: String): Result<Unit> {
        return try {
            val response = apiService.login(LoginRequest(email, password))
            if (response.isSuccessful && response.body() != null) {
                val body = response.body()!!
                val token = body.accessToken
                if (!token.isNullOrBlank()) {
                    sessionManager.saveSession(
                        accessToken = token,
                        refreshToken = body.refreshToken,
                        userId = body.user?.id ?: "",
                        userEmail = body.user?.email ?: email
                    )
                    
                    // Register saved FCM token if available
                    val fcmToken = sessionManager.getFCMToken()
                    if (!fcmToken.isNullOrBlank()) {
                        registerFCMToken(fcmToken)
                    }

                    Result.success(Unit)
                } else {
                    Result.failure(Exception("No se recibió token de acceso"))
                }
            } else {
                Result.failure(Exception("Credenciales inválidas o error del servidor (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun registerFCMToken(fcmToken: String): Result<Unit> {
        sessionManager.saveFCMToken(fcmToken)
        return try {
            val response = apiService.registerFCMToken(FCMTokenRequest(fcmToken))
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error al registrar FCM Token (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun unregisterFCMToken(fcmToken: String): Result<Unit> {
        return try {
            val response = apiService.unregisterFCMToken(FCMTokenRequest(fcmToken))
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error al desregistrar FCM Token"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun isLoggedIn(): Boolean = sessionManager.isLoggedIn()

    fun getUserEmail(): String? = sessionManager.getSession()?.userEmail

    suspend fun logout() {
        val fcmToken = sessionManager.getFCMToken()
        if (!fcmToken.isNullOrBlank()) {
            unregisterFCMToken(fcmToken)
        }
        sessionManager.clearSession()
    }
}
