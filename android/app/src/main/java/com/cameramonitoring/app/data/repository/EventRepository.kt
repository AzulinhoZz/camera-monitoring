package com.cameramonitoring.app.data.repository

import com.cameramonitoring.app.data.model.*
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

    suspend fun reviewAlert(eventId: String, reviewStatus: String): Result<Unit> {
        return try {
            val response = apiService.reviewAlert(eventId, ReviewAlertRequest(reviewStatus))
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error al registrar revisión de alerta (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getEventEvidence(eventId: String): Result<EventEvidenceResponse> {
        return try {
            val response = apiService.getEventEvidence(eventId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al consultar evidencia (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getEventClip(eventId: String): Result<EventClipResponse> {
        return try {
            val response = apiService.getEventClip(eventId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al consultar clip de video (${response.code()})"))
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
        sensitivityPreset: String? = "medium",
        minArea: Int? = 1500,
        threshold: Int? = 25,
        cooldownSeconds: Float? = 5.0f,
        scheduleType: String? = "24/7",
        scheduleDays: List<String>? = listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
        startTime: String? = "00:00:00",
        endTime: String? = "23:59:59",
        timezone: String? = "America/Mexico_City"
    ): Result<DetectionStatusResponse> {
        return try {
            val req = UpdateDetectionRequest(
                action = action,
                sensitivityPreset = sensitivityPreset,
                minArea = minArea,
                threshold = threshold,
                cooldownSeconds = cooldownSeconds,
                scheduleType = scheduleType,
                scheduleDays = scheduleDays,
                startTime = startTime,
                endTime = endTime,
                timezone = timezone
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

    suspend fun getZones(cameraId: String): Result<List<DetectionZone>> {
        return try {
            val response = apiService.getZones(cameraId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!.zones)
            } else {
                Result.failure(Exception("Error al obtener zonas (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createZone(cameraId: String, name: String, polygon: List<NormalizedPoint>): Result<DetectionZone> {
        return try {
            val response = apiService.createZone(cameraId, ZoneCreateRequest(name, polygon))
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al crear zona. Asegúrese de ingresar un polígono válido con al menos 3 puntos."))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteZone(cameraId: String, zoneId: String): Result<Unit> {
        return try {
            val response = apiService.deleteZone(cameraId, zoneId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error al eliminar zona (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun clearAllZones(cameraId: String): Result<Unit> {
        return try {
            val response = apiService.clearAllZones(cameraId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error al restaurar detección a toda la imagen"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
