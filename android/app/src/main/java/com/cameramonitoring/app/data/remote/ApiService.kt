package com.cameramonitoring.app.data.remote

import com.cameramonitoring.app.data.model.*
import retrofit2.Call
import retrofit2.Response
import retrofit2.http.*

interface ApiService {
    @GET("cameras/{id}/vision-rules")
    suspend fun getVisionRules(@Path("id") id: String): Response<VisionConfig>

    @PUT("cameras/{id}/vision-rules")
    suspend fun saveVisionRules(@Path("id") id: String, @Body body: VisionConfigUpdate): Response<VisionConfig>


    @POST("auth/register")
    suspend fun register(
        @Body body: RegisterRequest
    ): Response<SupabaseAuthResponse>

    @POST("auth/login")
    suspend fun login(
        @Body body: LoginRequest
    ): Response<SupabaseAuthResponse>

    @POST("auth/forgot-password")
    suspend fun forgotPassword(
        @Body body: ForgotPasswordRequest
    ): Response<ForgotPasswordResponse>

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

    @PUT("cameras/{id}")
    suspend fun updateCamera(
        @Path("id") id: String,
        @Body body: CameraUpdateRequest
    ): Response<Camera>

    @GET("cameras/{id}")
    suspend fun getCamera(
        @Path("id") id: String
    ): Response<Camera>

    @POST("cameras/{id}/check-connection")
    suspend fun checkCameraConnection(
        @Path("id") id: String
    ): Response<Camera>

    @DELETE("cameras/{id}")
    suspend fun deleteCamera(
        @Path("id") id: String
    ): Response<Unit>

    @GET("cameras/{id}/vision-status")
    suspend fun getVisionStatus(@Path("id") id: String,
        @Query("preview") preview: Boolean = false,
        @Query("overlay") overlay: Boolean = false): Response<VisionStatus>

    @GET("events/attention")
    suspend fun getCameraAttention(): Response<CameraAttention>

    @GET("events/statistics")
    suspend fun getEventStatistics(@Query("camera_id") cameraId: String? = null,
        @Query("event_type") eventType: String? = null,
        @Query("review_status") reviewStatus: String? = null,
        @Query("since") since: String? = null,
        @Query("rule_id") ruleId: String? = null,
        @Query("until") until: String? = null): Response<EventStatistics>

    @GET("events")
    suspend fun getEvents(
        @Query("camera_id") cameraId: String? = null,
        @Query("event_type") eventType: String? = null,
        @Query("review_status") reviewStatus: String? = null,
        @Query("since") since: String? = null,
        @Query("cursor") cursor: String? = null,
        @Query("limit") limit: Int = 100,
        @Query("rule_id") ruleId: String? = null,
        @Query("until") until: String? = null
    ): Response<EventListResponse>

    @POST("events/{id}/review")
    suspend fun reviewAlert(
        @Path("id") id: String,
        @Body body: ReviewAlertRequest
    ): Response<Map<String, Any>>

    @GET("events/{id}/evidence")
    suspend fun getEventEvidence(
        @Path("id") id: String
    ): Response<EventEvidenceResponse>

    @GET("events/{id}/clip")
    suspend fun getEventClip(
        @Path("id") id: String
    ): Response<EventClipResponse>

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

    @GET("cameras/{id}/zones")
    suspend fun getZones(
        @Path("id") id: String
    ): Response<ZoneListResponse>

    @POST("cameras/{id}/zones")
    suspend fun createZone(
        @Path("id") id: String,
        @Body body: ZoneCreateRequest
    ): Response<DetectionZone>

    @DELETE("cameras/{id}/zones/{zoneId}")
    suspend fun deleteZone(
        @Path("id") id: String,
        @Path("zoneId") zoneId: String
    ): Response<Map<String, Any>>

    @DELETE("cameras/{id}/zones")
    suspend fun clearAllZones(
        @Path("id") id: String
    ): Response<Map<String, Any>>

    @GET("storage/stats")
    suspend fun getStorageStats(): Response<StorageStatsResponse>

    @PUT("storage/retention")
    suspend fun updateRetentionPolicy(
        @Body body: RetentionUpdateRequest
    ): Response<Map<String, Any>>

    @POST("storage/cleanup")
    suspend fun triggerStorageCleanup(
        @Query("dry_run") dryRun: Boolean = true
    ): Response<CleanupResultResponse>

    @POST("storage/events/{id}/protect")
    suspend fun setEventProtectionStatus(
        @Path("id") id: String,
        @Body body: EventProtectRequest
    ): Response<Map<String, Any>>

    @GET("admin/overview")
    suspend fun getFleetOverview(): Response<FleetOverviewResponse>

    @GET("admin/drivers")
    suspend fun listDrivers(): Response<Map<String, Any>>

    @GET("admin/units")
    suspend fun listTransportUnits(): Response<Map<String, Any>>

    @POST("admin/units")
    suspend fun createTransportUnit(
        @Body body: TransportUnitCreateRequest
    ): Response<TransportUnit>
}
