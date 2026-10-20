package com.cameramonitoring.app.data.remote

import com.cameramonitoring.app.data.model.*
import retrofit2.Call
import retrofit2.Response
import retrofit2.http.*

interface ApiService {

    @POST("auth/login")
    suspend fun login(
        @Body body: LoginRequest
    ): Response<SupabaseAuthResponse>

    @POST("auth/refresh")
    suspend fun refreshToken(
        @Body body: RefreshRequest
    ): Response<SupabaseAuthResponse>

    @POST("auth/refresh")
    fun refreshTokenSync(
        @Body body: RefreshRequest
    ): Call<SupabaseAuthResponse>

    @POST("auth/fcm-token")
    suspend fun registerFCMToken(
        @Body body: FCMTokenRequest
    ): Response<Map<String, Any>>

    @HTTP(method = "DELETE", path = "auth/fcm-token", hasBody = true)
    suspend fun unregisterFCMToken(
        @Body body: FCMTokenRequest
    ): Response<Map<String, Any>>

    @GET("auth/me")
    suspend fun getCurrentUser(): Response<User>

    @GET("cameras")
    suspend fun getCameras(): Response<CameraListResponse>

    @POST("cameras")
    suspend fun createCamera(
        @Body body: CameraCreateRequest
    ): Response<Camera>

    @GET("cameras/{id}")
    suspend fun getCamera(
        @Path("id") id: String
    ): Response<Camera>

    @DELETE("cameras/{id}")
    suspend fun deleteCamera(
        @Path("id") id: String
    ): Response<Unit>

    @GET("events")
    suspend fun getEvents(
        @Query("camera_id") cameraId: String? = null
    ): Response<EventListResponse>

    @POST("events")
    suspend fun createEvent(
        @Body body: EventCreateRequest
    ): Response<CameraEvent>

    @GET("cameras/{id}/detect-motion")
    suspend fun getDetectionStatus(
        @Path("id") id: String
    ): Response<DetectionStatusResponse>

    @POST("cameras/{id}/detect-motion")
    suspend fun triggerMotionDetection(
        @Path("id") id: String,
        @Body body: UpdateDetectionRequest
    ): Response<DetectionStatusResponse>
}
