package com.cameramonitoring.app.data.repository

import com.cameramonitoring.app.data.model.Camera
import com.cameramonitoring.app.data.model.CameraCreateRequest
import com.cameramonitoring.app.data.remote.ApiService

class CameraRepository(
    private val apiService: ApiService
) {
    suspend fun getCameras(): Result<List<Camera>> {
        return try {
            val response = apiService.getCameras()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!.cameras)
            } else {
                Result.failure(Exception("Error al obtener las cámaras (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun addCamera(name: String, rtspUrl: String): Result<Camera> {
        return try {
            val response = apiService.createCamera(CameraCreateRequest(name, rtspUrl))
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al registrar la cámara. Verifique la URL RTSP."))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getCameraDetails(id: String): Result<Camera> {
        return try {
            val response = apiService.getCamera(id)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Cámara no encontrada."))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteCamera(id: String): Result<Unit> {
        return try {
            val response = apiService.deleteCamera(id)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error al eliminar la cámara"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
