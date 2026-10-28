package com.cameramonitoring.app

import com.cameramonitoring.app.data.model.*
import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Test

class VisionDashboardContractTest {
    @Test fun previewExpiresAndNeverCrossesCameraScope() {
        val sample = VisionStatus("camera", healthy = true, imageAgeSeconds = 1.0, imageBase64 = "image")
        assertEquals(1500L, previewLifetimeMillis("camera", sample, .5))
        assertEquals(0L, previewLifetimeMillis("other", sample, 0.0))
        assertEquals(0L, previewLifetimeMillis("camera", sample, 2.1))
        assertEquals(0L, previewLifetimeMillis("camera", sample.copy(healthy = false), 0.0))
        assertEquals(0L, previewLifetimeMillis("camera", sample.copy(imageAgeSeconds = Double.NaN), 0.0))
        assertEquals(0L, previewLifetimeMillis("camera", sample.copy(imageAgeSeconds = -1.0), 0.0))
    }

    @Test fun unavailableStatusHasNoPreviewAndWindowStatisticsAreSeparateFromPage() {
        val gson = Gson()
        val status = gson.fromJson("""{"camera_id":"camera","state":"unavailable","healthy":false,"image_base64":null}""", VisionStatus::class.java)
        assertEquals(0L, previewLifetimeMillis("camera", status, 0.0))
        val stats = gson.fromJson("""{"total":1234,"pending":23,"since":"2026-10-26T12:00:00Z","until":"2026-10-27T12:00:00Z","scope":"authorized_window"}""", EventStatistics::class.java)
        assertEquals(1234L, stats.total)
        assertEquals("authorized_window", stats.scope)
    }
}
