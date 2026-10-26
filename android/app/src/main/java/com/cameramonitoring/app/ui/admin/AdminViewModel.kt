package com.cameramonitoring.app.ui.admin

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.FleetOverviewResponse
import com.cameramonitoring.app.data.model.TransportUnit
import com.cameramonitoring.app.data.repository.AdminRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface AdminUiState {
    object Loading : AdminUiState
    data class Success(
        val overview: FleetOverviewResponse,
        val units: List<TransportUnit> = emptyList(),
        val statusMessage: String? = null
    ) : AdminUiState
    data class Error(val message: String) : AdminUiState
}

class AdminViewModel(
    private val adminRepository: AdminRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<AdminUiState>(AdminUiState.Loading)
    val uiState: StateFlow<AdminUiState> = _uiState.asStateFlow()

    fun loadFleetData() {
        viewModelScope.launch {
            _uiState.value = AdminUiState.Loading
            val overviewRes = adminRepository.getFleetOverview()
            overviewRes.fold(
                onSuccess = { overview ->
                    val unitsRes = adminRepository.listTransportUnits()
                    val units = unitsRes.getOrNull() ?: emptyList()

                    _uiState.value = AdminUiState.Success(
                        overview = overview,
                        units = units
                    )
                },
                onFailure = { ex ->
                    _uiState.value = AdminUiState.Error(ex.message ?: "Error al cargar datos de administración de flota")
                }
            )
        }
    }

    fun addTransportUnit(unitNumber: String, plateNumber: String?) {
        val currentState = _uiState.value as? AdminUiState.Success ?: return

        viewModelScope.launch {
            val res = adminRepository.createTransportUnit(unitNumber, plateNumber)
            res.fold(
                onSuccess = {
                    loadFleetData()
                },
                onFailure = { ex ->
                    _uiState.value = currentState.copy(statusMessage = ex.message ?: "Error al registrar unidad")
                }
            )
        }
    }

    fun dismissStatusMessage() {
        val currentState = _uiState.value as? AdminUiState.Success ?: return
        _uiState.value = currentState.copy(statusMessage = null)
    }
}
