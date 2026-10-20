package com.cameramonitoring.app.data.repository

import com.cameramonitoring.app.data.model.CameraEvent
import com.cameramonitoring.app.data.model.DetectionStatusResponse
import com.cameramonitoring.app.data.model.EventCreateRequest
import com.cameramonitoring.app.data.model.UpdateDetectionRequest
import com.cameramonitoring.app.data.remote.ApiService

class EventRepository(
    private val apiService: ApiService
) {
    suspend fun getEvents(cameraId: String? = null): Result<List<CameraEvent>> {
        return try {
            val response = apiService.getEvents(cameraId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!.events)
            } else {
                Result.failure(Exception("Error al consultar eventos (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createEvent(cameraId: String, description: String = "Movimiento detectado"): Result<CameraEvent> {
        return try {
            val response = apiService.createEvent(EventCreateRequest(cameraId = cameraId, description = description))
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al registrar evento"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getDetectionStatus(cameraId: String): Result<DetectionStatusResponse> {
        return try {
            val response = apiService.getDetectionStatus(cameraId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al consultar estado de detección (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun triggerMotionDetection(
        cameraId: String,
        action: String = "start",
        minArea: Int? = 1500,
        threshold: Int? = 25,
        cooldownSeconds: Float? = 5.0f
    ): Result<DetectionStatusResponse> {
        return try {
            val req = UpdateDetectionRequest(
                action = action,
                minArea = minArea,
                threshold = threshold,
                cooldownSeconds = cooldownSeconds
            )
            val response = apiService.triggerMotionDetection(cameraId, req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al configurar detección de movimiento (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
