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
    data class Success(val cameras: List<Camera>, val actionError: String? = null) : DashboardUiState
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

    fun checkCameraConnection(id: String) {
        viewModelScope.launch {
            val result = cameraRepository.checkCameraConnection(id)
            result.fold(
                onSuccess = {
                    loadCameras()
                },
                onFailure = { ex ->
                    val currentState = _uiState.value as? DashboardUiState.Success
                    if (currentState != null) {
                        _uiState.value = currentState.copy(actionError = ex.message ?: "Error al verificar la conexión")
                    }
                }
            )
        }
    }

    fun updateCamera(id: String, name: String, rtspUrl: String) {
        viewModelScope.launch {
            val res = cameraRepository.updateCamera(id, name, rtspUrl)
            res.fold(
                onSuccess = {
                    loadCameras()
                },
                onFailure = { ex ->
                    val currentState = _uiState.value as? DashboardUiState.Success
                    if (currentState != null) {
                        _uiState.value = currentState.copy(actionError = ex.message ?: "Error al actualizar la cámara")
                    } else {
                        _uiState.value = DashboardUiState.Error(ex.message ?: "Error al actualizar la cámara")
                    }
                }
            )
        }
    }

    fun deleteCamera(cameraId: String) {
        viewModelScope.launch {
            val res = cameraRepository.deleteCamera(cameraId)
            res.fold(
                onSuccess = {
                    loadCameras()
                },
                onFailure = { ex ->
                    val currentState = _uiState.value as? DashboardUiState.Success
                    if (currentState != null) {
                        _uiState.value = currentState.copy(actionError = ex.message ?: "Error al eliminar la cámara")
                    } else {
                        _uiState.value = DashboardUiState.Error(ex.message ?: "Error al eliminar la cámara")
                    }
                }
            )
        }
    }

    fun dismissActionError() {
        val currentState = _uiState.value as? DashboardUiState.Success ?: return
        _uiState.value = currentState.copy(actionError = null)
    }
}
