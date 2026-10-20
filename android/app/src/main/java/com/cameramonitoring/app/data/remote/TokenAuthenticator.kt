package com.cameramonitoring.app.data.remote

import android.util.Log
import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.data.model.RefreshRequest
import okhttp3.Authenticator
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.io.IOException

class TokenAuthenticator(
    private val sessionManager: SessionManager,
    private val baseUrl: String,
    private val onSessionExpired: (() -> Unit)? = null
) : Authenticator {

    private val refreshApiService: ApiService by lazy {
        val client = OkHttpClient.Builder().build()
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }

    override fun authenticate(route: Route?, response: Response): Request? {
        val path = response.request.url.encodedPath

        // Task 6: Never attempt token refresh if 401 comes from login or refresh requests
        if (path.contains("/auth/login") || path.contains("/auth/refresh")) {
            return null
        }

        // Task 5: Avoid infinite loops - retry at most once
        if (responseCount(response) >= 2) {
            Log.w("TokenAuthenticator", "Request failed twice with 401. Aborting retry.")
            return null
        }

        synchronized(this) {
            val currentToken = sessionManager.getAccessToken()
            val requestToken = response.request.header("Authorization")?.replace("Bearer ", "")

            // Task 5: Avoid simultaneous refresh requests. If another thread already refreshed token, use it immediately
            if (!currentToken.isNullOrBlank() && currentToken != requestToken) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $currentToken")
                    .build()
            }

            val refreshToken = sessionManager.getSession()?.refreshToken
            if (refreshToken.isNullOrBlank()) {
                Log.w("TokenAuthenticator", "No refresh token available. Clearing session.")
                handleRefreshFailure()
                return null
            }

            return try {
                val refreshCall = refreshApiService.refreshTokenSync(RefreshRequest(refreshToken))
                val refreshResponse = refreshCall.execute()

                if (refreshResponse.isSuccessful && refreshResponse.body() != null) {
                    val body = refreshResponse.body()!!
                    val newAccessToken = body.accessToken
                    if (!newAccessToken.isNullOrBlank()) {
                        Log.i("TokenAuthenticator", "Token refreshed successfully")
                        sessionManager.saveSession(
                            accessToken = newAccessToken,
                            refreshToken = body.refreshToken ?: refreshToken,
                            userId = body.user?.id ?: sessionManager.getSession()?.userId ?: "",
                            userEmail = body.user?.email ?: sessionManager.getSession()?.userEmail
                        )

                        response.request.newBuilder()
                            .header("Authorization", "Bearer $newAccessToken")
                            .build()
                    } else {
                        handleRefreshFailure()
                        null
                    }
                } else {
                    Log.w("TokenAuthenticator", "Token refresh request rejected with code: ${refreshResponse.code()}")
                    handleRefreshFailure()
                    null
                }
            } catch (e: IOException) {
                Log.e("TokenAuthenticator", "Network exception during token refresh", e)
                null
            }
        }
    }

    private fun handleRefreshFailure() {
        sessionManager.clearSession()
        onSessionExpired?.invoke()
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }
}
