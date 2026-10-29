package com.cameramonitoring.app.data.model

import com.google.gson.annotations.SerializedName

data class User(
    val id: String,
    val email: String? = null,
    @SerializedName("full_name") val fullName: String? = null,
    val role: String? = "conductor",
    @SerializedName("organization_id") val organizationId: String? = null
)

data class LoginRequest(
    val email: String,
    val password: String
)

data class RegisterRequest(
    @SerializedName("full_name") val fullName: String,
    val email: String,
    val password: String
)

data class ForgotPasswordRequest(
    val email: String
)

data class ForgotPasswordResponse(
    val message: String
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
    @SerializedName("user") val user: SupabaseUser?,
    val message: String? = null
)

data class SupabaseUser(
    val id: String,
    val email: String?,
    @SerializedName("full_name") val fullName: String? = null,
    val role: String? = "conductor"
)

data class SessionData(
    val accessToken: String,
    val refreshToken: String?,
    val userId: String,
    val userEmail: String?,
    val fullName: String? = null,
    val role: String = "conductor"
)

data class Camera(
    val id: String,
    @SerializedName("user_id") val userId: String? = null,
    val name: String,
    @SerializedName("rtsp_url") val rtspUrl: String,
    val status: String = "online",
    @SerializedName("last_seen_at") val lastSeenAt: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("stream_path") val streamPath: String? = null,
    @SerializedName("hls_url") val hlsUrl: String? = null,
    @SerializedName("stream_token") val streamToken: String? = null,
    @SerializedName("stream_expires_at") val streamExpiresAt: String? = null,
    @SerializedName("motion_enabled") val motionEnabled: Boolean = true
)

data class CameraCreateRequest(
    val name: String,
    @SerializedName("rtsp_url") val rtspUrl: String
)

data class CameraUpdateRequest(
    val name: String? = null,
    @SerializedName("rtsp_url") val rtspUrl: String? = null
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
    val description: String? = "Movimiento detectado",
    @SerializedName("evidence_path") val evidencePath: String? = null,
    @SerializedName("has_evidence") val hasEvidence: Boolean = false,
    @SerializedName("clip_path") val clipPath: String? = null,
    @SerializedName("has_clip") val hasClip: Boolean = false,
    @SerializedName("is_protected") val isProtected: Boolean = false,
    @SerializedName("review_status") val reviewStatus: String = "pending",
    @SerializedName("vision_summary") val visionSummary: VisionSummary? = null,
    @SerializedName("reviewed_at") val reviewedAt: String? = null
)

data class ReviewAlertRequest(
    @SerializedName("review_status") val reviewStatus: String
)

data class EventEvidenceResponse(
    @SerializedName("event_id") val eventId: String,
    @SerializedName("has_evidence") val hasEvidence: Boolean,
    @SerializedName("evidence_path") val evidencePath: String? = null,
    @SerializedName("signed_url") val signedUrl: String? = null
)

data class EventClipResponse(
    @SerializedName("event_id") val eventId: String,
    @SerializedName("has_clip") val hasClip: Boolean,
    @SerializedName("clip_path") val clipPath: String? = null,
    @SerializedName("signed_url") val signedUrl: String? = null
)

data class EventListResponse(
    val total: Int,
    val events: List<CameraEvent>,
    @SerializedName("has_more") val hasMore: Boolean = false,
    @SerializedName("next_cursor") val nextCursor: String? = null,
    @SerializedName("applied_filters") val appliedFilters: AppliedEventFilters? = null
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
    @SerializedName("cooldown_seconds") val cooldownSeconds: Float = 5.0f,
    @SerializedName("sensitivity_preset") val sensitivityPreset: String = "medium",
    @SerializedName("schedule_type") val scheduleType: String = "24/7",
    @SerializedName("schedule_days") val scheduleDays: List<String> = listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
    @SerializedName("start_time") val startTime: String = "00:00:00",
    @SerializedName("end_time") val endTime: String = "23:59:59",
    val timezone: String = "America/Mexico_City",
    @SerializedName("is_schedule_active") val isScheduleActive: Boolean = true,
    @SerializedName("active_zones_count") val activeZonesCount: Int = 0,
    val zones: List<DetectionZone> = emptyList()
)

data class UpdateDetectionRequest(
    val action: String = "start",
    @SerializedName("sensitivity_preset") val sensitivityPreset: String? = "medium",
    @SerializedName("min_area") val minArea: Int? = 1500,
    val threshold: Int? = 25,
    @SerializedName("cooldown_seconds") val cooldownSeconds: Float? = 5.0f,
    @SerializedName("schedule_type") val scheduleType: String? = "24/7",
    @SerializedName("schedule_days") val scheduleDays: List<String>? = listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
    @SerializedName("start_time") val startTime: String? = "00:00:00",
    @SerializedName("end_time") val endTime: String? = "23:59:59",
    val timezone: String? = "America/Mexico_City"
)

data class NormalizedPoint(
    val x: Float,
    val y: Float
)

data class DetectionZone(
    val id: String? = null,
    @SerializedName("camera_id") val cameraId: String? = null,
    val name: String = "Zona de Detección",
    val polygon: List<NormalizedPoint>,
    @SerializedName("is_active") val isActive: Boolean = true
)

data class ZoneListResponse(
    val total: Int,
    val zones: List<DetectionZone>
)

data class ZoneCreateRequest(
    val name: String = "Zona de Detección",
    val polygon: List<NormalizedPoint>
)

data class StorageStatsResponse(
    @SerializedName("photos_count") val photosCount: Int = 0,
    @SerializedName("clips_count") val clipsCount: Int = 0,
    @SerializedName("protected_events_count") val protectedEventsCount: Int = 0,
    @SerializedName("total_storage_mb") val totalStorageMb: Float = 0.0f,
    @SerializedName("retention_days") val retentionDays: Int = 30,
    @SerializedName("auto_cleanup_enabled") val autoCleanupEnabled: Boolean = false
)

data class RetentionUpdateRequest(
    @SerializedName("retention_days") val retentionDays: Int = 30,
    @SerializedName("auto_cleanup_enabled") val autoCleanupEnabled: Boolean = false
)

data class EventProtectRequest(
    @SerializedName("is_protected") val isProtected: Boolean = true
)

data class CleanupResultResponse(
    @SerializedName("user_id") val userId: String,
    @SerializedName("dry_run") val dryRun: Boolean,
    @SerializedName("retention_days") val retentionDays: Int = 30,
    @SerializedName("deleted_photos") val deletedPhotos: Int = 0,
    @SerializedName("deleted_clips") val deletedClips: Int = 0,
    @SerializedName("freed_mb") val freedMb: Float = 0.0f
)

data class FleetOverviewResponse(
    @SerializedName("organization_id") val organizationId: String?,
    @SerializedName("drivers_count") val driversCount: Int = 0,
    @SerializedName("units_count") val unitsCount: Int = 0,
    @SerializedName("cameras_count") val camerasCount: Int = 0
)

data class TransportUnit(
    val id: String,
    @SerializedName("unit_number") val unitNumber: String,
    @SerializedName("plate_number") val plateNumber: String? = null,
    @SerializedName("created_at") val createdAt: String? = null
)

data class TransportUnitCreateRequest(
    @SerializedName("unit_number") val unitNumber: String,
    @SerializedName("plate_number") val plateNumber: String? = null
)

// Server derives tenant scope; never submit owner/organization IDs in this DTO.
data class VisionRule(
    @SerializedName("rule_id") val ruleId: String,
    val kind: String = "intrusion",
    val enabled: Boolean = false,
    val classes: List<String> = listOf("person"),
    val polygon: List<NormalizedPoint> = emptyList(),
    val line: List<NormalizedPoint>? = null,
    val direction: String = "both",
    @SerializedName("min_confidence") val minConfidence: Double = 0.5,
    @SerializedName("min_observations") val minObservations: Int = 2,
    @SerializedName("line_margin") val lineMargin: Double = 0.005,
    val threshold: Int = 1,
    @SerializedName("duration_seconds") val durationSeconds: Double = 10.0,
    @SerializedName("cooldown_seconds") val cooldownSeconds: Double = 30.0,
    @SerializedName("stationary_radius") val stationaryRadius: Double = 0.02,
    @SerializedName("timezone_name") val timezoneName: String = "America/Mexico_City",
    val weekdays: List<Int> = (0..6).toList(),
    val start: String = "00:00:00",
    val end: String = "23:59:59"
)

data class VisionConfig(
    val revision: Long = 0,
    val rules: List<VisionRule> = emptyList(),
    @SerializedName("can_manage") val canManage: Boolean = false
)
data class VisionConfigUpdate(val revision: Long, val rules: List<VisionRule>)

data class VisionSummary(
    @SerializedName("rule_id") val ruleId: String? = null,
    @SerializedName("event_type") val eventType: String? = null,
    val count: Int? = null,
    val direction: String? = null
)


data class VisionStatus(
    @SerializedName("camera_id") val cameraId: String,
    val healthy: Boolean = false,
    val state: String = "unavailable",
    val diagnostics: VisionDiagnostics? = null,
    val session: String? = null,
    @SerializedName("frame_at") val frameAt: String? = null,
    @SerializedName("capture_fps") val captureFps: Double = 0.0,
    @SerializedName("inference_fps") val inferenceFps: Double = 0.0,
    @SerializedName("inference_frames") val inferenceFrames: Long = 0,
    @SerializedName("inference_dropped") val inferenceDropped: Long = 0,
    @SerializedName("rss_bytes") val rssBytes: Long = 0,
    @SerializedName("cpu_seconds") val cpuSeconds: Double = 0.0,
    @SerializedName("image_age_seconds") val imageAgeSeconds: Double = 10.0,
    @SerializedName("preview_ttl_seconds") val previewTtlSeconds: Int = 3,
    @SerializedName("image_base64") val imageBase64: String? = null
)

data class EventStatistics(
    val total: Long, val pending: Long,
    val since: String, val until: String, val scope: String,
    @SerializedName("applied_filters") val appliedFilters: AppliedEventFilters? = null
)


data class CameraAttention(
    @SerializedName("pending_by_camera") val pendingByCamera: Map<String,Long> = emptyMap(),
    val complete: Boolean = false,
    val since: String? = null,
    val until: String? = null
) {
    fun pending(cameraId: String): Long? = pendingByCamera[cameraId] ?: if (complete) 0L else null
}

data class VisionDiagnostics(val ready: Boolean = false, val codes: List<String> = emptyList(), @SerializedName("target_fps") val targetFps: Double = 2.0)

fun CameraEvent.incidentReason(): String = when (eventType) {
    "vision_intrusion" -> "Entrada en una zona configurada"
    "vision_dwell" -> "Permanencia superior al tiempo configurado"
    "vision_line_crossing" -> "Cruce de una línea configurada"
    "vision_count" -> "Se alcanzó el conteo configurado"
    "vision_probable_abandoned_object" -> "Posible objeto abandonado; requiere revisión"
    "motion_detected" -> "Movimiento detectado; revisa la evidencia"
    else -> "Evento registrado; requiere revisión humana"
}


fun eventTimestampLabel(value: String?): String = runCatching {
    val instant = java.time.OffsetDateTime.parse(value).toInstant()
    java.time.format.DateTimeFormatter.ofLocalizedDateTime(java.time.format.FormatStyle.MEDIUM)
        .withLocale(java.util.Locale.getDefault()).withZone(java.time.ZoneId.systemDefault()).format(instant)
}.getOrDefault("Fecha no disponible")

data class AppliedEventFilters(@SerializedName("rule_id") val ruleId: String? = null)


data class EventSearchRange(val since: String, val until: String)

fun eventSearchRange(start: java.time.LocalDateTime, end: java.time.LocalDateTime,
                     zone: java.time.ZoneId = java.time.ZoneId.systemDefault()): EventSearchRange {
    fun instant(value: java.time.LocalDateTime): java.time.Instant {
        val offsets = zone.rules.getValidOffsets(value)
        require(offsets.size == 1) { "Elige otra hora: el cambio de horario hace ambigua o inexistente esta selección." }
        return value.toInstant(offsets.single())
    }
    val from = instant(start.withSecond(0).withNano(0))
    // Picker precision is minutes: include the complete selected final minute.
    val to = instant(end.withSecond(0).withNano(0)).plusSeconds(59).plusNanos(999_999_000)
    require(!to.isBefore(from) && java.time.Duration.between(from, to) <= java.time.Duration.ofDays(31)) {
        "El rango debe estar ordenado y ser de hasta 31 días."
    }
    return EventSearchRange(from.toString(), to.toString())
}
