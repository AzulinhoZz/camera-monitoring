package com.cameramonitoring.app.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.Camera
import com.cameramonitoring.app.data.repository.CameraRepository
import com.cameramonitoring.app.data.repository.EventRepository
import com.cameramonitoring.app.data.model.CameraAttention
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface DashboardUiState {
    object Loading : DashboardUiState
    data class Success(val cameras: List<Camera>, val actionError: String? = null, val attention: CameraAttention? = null) : DashboardUiState
    data class Error(val message: String) : DashboardUiState
}

class DashboardViewModel(
    private val cameraRepository: CameraRepository,
    private val eventRepository: EventRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<DashboardUiState>(DashboardUiState.Loading)
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private var request: Job? = null
    fun loadCameras() {
        request?.cancel()
        request = viewModelScope.launch {
            _uiState.value = DashboardUiState.Loading
            val result = cameraRepository.getCameras()
            if (!currentCoroutineContext().isActive) return@launch
            result.fold(
                onSuccess = { cameras ->
                    _uiState.value = DashboardUiState.Success(cameras)
                    val attention = withTimeoutOrNull(5000) { eventRepository.getCameraAttention() }
                    if (currentCoroutineContext().isActive) {
                        val current = _uiState.value as? DashboardUiState.Success
                        if (current != null) _uiState.value = current.copy(attention = attention)
                    }
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

    fun clear() { viewModelScope.coroutineContext.cancelChildren(); _uiState.value = DashboardUiState.Loading }

    fun dismissActionError() {
        val currentState = _uiState.value as? DashboardUiState.Success ?: return
        _uiState.value = currentState.copy(actionError = null)
    }
}
