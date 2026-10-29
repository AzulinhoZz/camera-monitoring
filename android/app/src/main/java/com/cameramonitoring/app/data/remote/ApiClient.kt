package com.cameramonitoring.app.data.remote

import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.BuildConfig
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {

    private val BASE_URL = BuildConfig.API_BASE_URL

    private var apiService: ApiService? = null

    fun getApiService(
        sessionManager: SessionManager,
        onSessionExpired: (() -> Unit)? = null
    ): ApiService {
        if (apiService == null) {
            val logging = HttpLoggingInterceptor().apply {
                level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
                redactHeader("Authorization")
                redactHeader("Cookie")
                redactHeader("Set-Cookie")
            }

            val authInterceptor = Interceptor { chain ->
                val originalRequest = chain.request()
                val token = sessionManager.getAccessToken()

                val requestBuilder = originalRequest.newBuilder()
                if (!token.isNullOrBlank()) {
                    requestBuilder.header("Authorization", "Bearer $token")
                }

                chain.proceed(requestBuilder.build())
            }

            val tokenAuthenticator = TokenAuthenticator(
                sessionManager = sessionManager,
                baseUrl = BASE_URL,
                onSessionExpired = onSessionExpired
            )

            val okHttpClient = OkHttpClient.Builder()
                .addInterceptor(authInterceptor)
                .authenticator(tokenAuthenticator)
                .addInterceptor(logging)
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(15, TimeUnit.SECONDS)
                .writeTimeout(15, TimeUnit.SECONDS)
                .build()

            val retrofit = Retrofit.Builder()
                .baseUrl(BASE_URL)
                .client(okHttpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build()

            apiService = retrofit.create(ApiService::class.java)
        }
        return apiService!!
    }
}
