package com.cameramonitoring.app.data.repository

import com.cameramonitoring.app.data.model.*
import com.cameramonitoring.app.data.remote.ApiService

class AdminRepository(
    private val apiService: ApiService
) {
    suspend fun getFleetOverview(): Result<FleetOverviewResponse> {
        return try {
            val response = apiService.getFleetOverview()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al consultar resumen de flota (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun listTransportUnits(): Result<List<TransportUnit>> {
        return try {
            val response = apiService.listTransportUnits()
            if (response.isSuccessful && response.body() != null) {
                val raw = response.body()!!["units"] as? List<*>
                val units = mutableListOf<TransportUnit>()
                raw?.forEach { item ->
                    if (item is Map<*, *>) {
                        units.add(
                            TransportUnit(
                                id = item["id"].toString(),
                                unitNumber = item["unit_number"].toString(),
                                plateNumber = item["plate_number"]?.toString(),
                                createdAt = item["created_at"]?.toString()
                            )
                        )
                    }
                }
                Result.success(units)
            } else {
                Result.failure(Exception("Error al consultar unidades de transporte (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createTransportUnit(unitNumber: String, plateNumber: String?): Result<TransportUnit> {
        return try {
            val req = TransportUnitCreateRequest(unitNumber = unitNumber, plateNumber = plateNumber)
            val response = apiService.createTransportUnit(req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Error al crear unidad de transporte (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
