package com.cameramonitoring.app.data.repository

import com.cameramonitoring.app.data.model.*
import com.cameramonitoring.app.data.remote.ApiService

class StorageRepository(
    private val apiService: ApiService
) {
    suspend fun getStorageStats(): Result<StorageStatsResponse> {
        return try {
            val response = apiService.getStorageStats()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al consultar estadísticas de almacenamiento (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun updateRetentionPolicy(retentionDays: Int, autoCleanupEnabled: Boolean): Result<Unit> {
        return try {
            val req = RetentionUpdateRequest(retentionDays = retentionDays, autoCleanupEnabled = autoCleanupEnabled)
            val response = apiService.updateRetentionPolicy(req)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error al actualizar política de retención (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun triggerStorageCleanup(dryRun: Boolean = true): Result<CleanupResultResponse> {
        return try {
            val response = apiService.triggerStorageCleanup(dryRun = dryRun)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al ejecutar limpieza de almacenamiento (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun setEventProtectionStatus(eventId: String, isProtected: Boolean): Result<Unit> {
        return try {
            val response = apiService.setEventProtectionStatus(eventId, EventProtectRequest(isProtected = isProtected))
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error al actualizar protección del evento (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
