package com.cameramonitoring.app.data.repository

import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.data.model.FCMTokenRequest
import com.cameramonitoring.app.data.model.ForgotPasswordRequest
import com.cameramonitoring.app.data.model.LoginRequest
import com.cameramonitoring.app.data.model.RegisterRequest
import com.cameramonitoring.app.data.remote.ApiService

class AuthRepository(
    private val apiService: ApiService,
    private val sessionManager: SessionManager
) {
    suspend fun register(fullName: String, email: String, password: String): Result<String> {
        return try {
            val response = apiService.register(RegisterRequest(fullName, email, password))
            if (response.isSuccessful && response.body() != null) {
                val body = response.body()!!
                val token = body.accessToken
                if (!token.isNullOrBlank()) {
                    sessionManager.saveSession(
                        accessToken = token,
                        refreshToken = body.refreshToken,
                        userId = body.user?.id ?: "",
                        userEmail = body.user?.email ?: email,
                        fullName = body.user?.fullName ?: fullName
                    )
                }
                Result.success(body.message ?: "Registro completado con éxito")
            } else {
                Result.failure(Exception("Error al registrar cuenta. Verifique los datos o si el correo ya existe."))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

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
                        userEmail = body.user?.email ?: email,
                        fullName = body.user?.fullName
                    )

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

    suspend fun forgotPassword(email: String): Result<String> {
        return try {
            val response = apiService.forgotPassword(ForgotPasswordRequest(email))
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!.message)
            } else {
                Result.failure(Exception("Error al solicitar restablecimiento de contraseña"))
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

    fun getUserFullName(): String? = sessionManager.getSession()?.fullName

    suspend fun logout() {
        val fcmToken = sessionManager.getFCMToken()
        if (!fcmToken.isNullOrBlank()) {
            unregisterFCMToken(fcmToken)
        }
        sessionManager.clearSession()
    }
}
