package com.cameramonitoring.app.data.model

/** Conservative display budget; network delay consumes remaining frame lifetime. */
fun previewLifetimeMillis(cameraId: String, status: VisionStatus?, roundTripSeconds: Double): Long {
    if (status == null || status.cameraId != cameraId || !status.healthy || status.imageBase64 == null ||
        !roundTripSeconds.isFinite() || roundTripSeconds < 0 || !status.imageAgeSeconds.isFinite() || status.imageAgeSeconds < 0) return 0
    val ttl = status.previewTtlSeconds.coerceIn(0, 3)
    return ((ttl - status.imageAgeSeconds - roundTripSeconds) * 1000).toLong().coerceIn(0, 3000)
}
