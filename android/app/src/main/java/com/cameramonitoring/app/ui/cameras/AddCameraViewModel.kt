package com.cameramonitoring.app.ui.cameras

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.repository.CameraRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface AddCameraUiState {
    object Idle : AddCameraUiState
    object Loading : AddCameraUiState
    object Success : AddCameraUiState
    data class Error(val message: String) : AddCameraUiState
}

class AddCameraViewModel(
    private val cameraRepository: CameraRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<AddCameraUiState>(AddCameraUiState.Idle)
    val uiState: StateFlow<AddCameraUiState> = _uiState.asStateFlow()

    fun addCamera(name: String, rtspUrl: String) {
        val trimmedName = name.trim()
        val trimmedUrl = rtspUrl.trim()

        if (trimmedName.isBlank()) {
            _uiState.value = AddCameraUiState.Error("Ingrese un nombre para la cámara")
            return
        }

        if (trimmedUrl.isBlank() || (!trimmedUrl.startsWith("rtsp://") && !trimmedUrl.startsWith("rtsps://"))) {
            _uiState.value = AddCameraUiState.Error("Ingrese una URL RTSP válida (ej. rtsp://10.0.2.2:8554/camara1)")
            return
        }

        viewModelScope.launch {
            _uiState.value = AddCameraUiState.Loading
            val result = cameraRepository.addCamera(trimmedName, trimmedUrl)
            result.fold(
                onSuccess = {
                    _uiState.value = AddCameraUiState.Success
                },
                onFailure = { ex ->
                    _uiState.value = AddCameraUiState.Error(ex.message ?: "Error al registrar la cámara")
                }
            )
        }
    }

    fun resetState() {
        _uiState.value = AddCameraUiState.Idle
    }
}
