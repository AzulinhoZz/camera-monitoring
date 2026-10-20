package com.cameramonitoring.app.data.model

import com.google.gson.annotations.SerializedName

data class User(
    val id: String,
    val email: String? = null
)

data class LoginRequest(
    val email: String,
    val password: String
)

data class RefreshRequest(
    @SerializedName("refresh_token") val refreshToken: String
)

data class FCMTokenRequest(
    @SerializedName("fcm_token") val fcmToken: String,
    @SerializedName("device_type") val deviceType: String = "android"
)

data class SupabaseAuthResponse(
    @SerializedName("access_token") val accessToken: String?,
    @SerializedName("refresh_token") val refreshToken: String?,
    @SerializedName("user") val user: SupabaseUser?
)

data class SupabaseUser(
    val id: String,
    val email: String?
)

data class SessionData(
    val accessToken: String,
    val refreshToken: String?,
    val userId: String,
    val userEmail: String?
)

data class Camera(
    val id: String,
    @SerializedName("user_id") val userId: String? = null,
    val name: String,
    @SerializedName("rtsp_url") val rtspUrl: String,
    val status: String = "online",
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("stream_path") val streamPath: String? = null,
    @SerializedName("hls_url") val hlsUrl: String? = null,
    @SerializedName("motion_enabled") val motionEnabled: Boolean = true
)

data class CameraCreateRequest(
    val name: String,
    @SerializedName("rtsp_url") val rtspUrl: String
)

data class CameraListResponse(
    val total: Int,
    val cameras: List<Camera>
)

data class CameraEvent(
    val id: String,
    @SerializedName("camera_id") val cameraId: String,
    @SerializedName("camera_name") val cameraName: String? = "Cámara",
    @SerializedName("event_type") val eventType: String = "motion_detected",
    @SerializedName("detected_at") val detectedAt: String? = null,
    val description: String? = "Movimiento detectado"
)

data class EventListResponse(
    val total: Int,
    val events: List<CameraEvent>
)

data class EventCreateRequest(
    @SerializedName("camera_id") val cameraId: String,
    @SerializedName("event_type") val eventType: String = "motion_detected",
    val description: String? = "Movimiento detectado por OpenCV"
)

data class DetectionStatusResponse(
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("camera_id") val cameraId: String,
    @SerializedName("min_area") val minArea: Int = 1500,
    val threshold: Int = 25,
    @SerializedName("cooldown_seconds") val cooldownSeconds: Float = 5.0f
)

data class UpdateDetectionRequest(
    val action: String = "start",
    @SerializedName("min_area") val minArea: Int? = 1500,
    val threshold: Int? = 25,
    @SerializedName("cooldown_seconds") val cooldownSeconds: Float? = 5.0f
)
