package com.cameramonitoring.app.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.Camera
import com.cameramonitoring.app.data.repository.CameraRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface DashboardUiState {
    object Loading : DashboardUiState
    data class Success(val cameras: List<Camera>) : DashboardUiState
    data class Error(val message: String) : DashboardUiState
}

class DashboardViewModel(
    private val cameraRepository: CameraRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<DashboardUiState>(DashboardUiState.Loading)
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    fun loadCameras() {
        viewModelScope.launch {
            _uiState.value = DashboardUiState.Loading
            val result = cameraRepository.getCameras()
            result.fold(
                onSuccess = { cameras ->
                    _uiState.value = DashboardUiState.Success(cameras)
                },
                onFailure = { ex ->
                    _uiState.value = DashboardUiState.Error(ex.message ?: "Error al cargar las cámaras")
                }
            )
        }
    }

    fun deleteCamera(cameraId: String) {
        viewModelScope.launch {
            cameraRepository.deleteCamera(cameraId)
            loadCameras()
        }
    }
}
