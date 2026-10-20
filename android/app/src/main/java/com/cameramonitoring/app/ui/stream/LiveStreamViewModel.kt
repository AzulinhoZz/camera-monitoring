package com.cameramonitoring.app.ui.stream

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.Camera
import com.cameramonitoring.app.data.model.CameraEvent
import com.cameramonitoring.app.data.repository.CameraRepository
import com.cameramonitoring.app.data.repository.EventRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

sealed interface StreamUiState {
    object Loading : StreamUiState
    data class Success(
        val camera: Camera,
        val isDetectingMotion: Boolean = false,
        val motionEnabled: Boolean = true,
        val minArea: Int = 1500,
        val threshold: Int = 25,
        val cooldownSeconds: Float = 5.0f,
        val recentEvents: List<CameraEvent> = emptyList(),
        val statusMessage: String? = null
    ) : StreamUiState
    data class Error(val message: String) : StreamUiState
}

class LiveStreamViewModel(
    private val cameraRepository: CameraRepository,
    private val eventRepository: EventRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<StreamUiState>(StreamUiState.Loading)
    val uiState: StateFlow<StreamUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null

    fun loadCamera(cameraId: String) {
        viewModelScope.launch {
            _uiState.value = StreamUiState.Loading
            val cameraRes = cameraRepository.getCameraDetails(cameraId)
            cameraRes.fold(
                onSuccess = { camera ->
                    val statusRes = eventRepository.getDetectionStatus(cameraId)
                    val status = statusRes.getOrNull()
                    val isActive = status?.isActive ?: false
                    val motionEnabled = camera.motionEnabled
                    val minArea = status?.minArea ?: 1500
                    val threshold = status?.threshold ?: 25
                    val cooldown = status?.cooldownSeconds ?: 5.0f

                    val eventsRes = eventRepository.getEvents(cameraId)
                    val initialEvents = eventsRes.getOrNull() ?: emptyList()

                    _uiState.value = StreamUiState.Success(
                        camera = camera,
                        isDetectingMotion = isActive,
                        motionEnabled = motionEnabled,
                        minArea = minArea,
                        threshold = threshold,
                        cooldownSeconds = cooldown,
                        recentEvents = initialEvents
                    )

                    startEventPolling(cameraId)
                },
                onFailure = { ex ->
                    _uiState.value = StreamUiState.Error(ex.message ?: "Error al cargar la cámara")
                }
            )
        }
    }

    fun toggleMotionDetection(cameraId: String, minArea: Int = 1500, threshold: Int = 25) {
        val currentState = _uiState.value as? StreamUiState.Success ?: return
        val newDetectState = !currentState.motionEnabled

        viewModelScope.launch {
            val action = if (newDetectState) "start" else "stop"
            val result = eventRepository.triggerMotionDetection(
                cameraId = cameraId,
                action = action,
                minArea = minArea,
                threshold = threshold
            )
            result.fold(
                onSuccess = { status ->
                    _uiState.value = currentState.copy(
                        isDetectingMotion = status.isActive,
                        motionEnabled = newDetectState,
                        minArea = status.minArea,
                        threshold = status.threshold,
                        cooldownSeconds = status.cooldownSeconds,
                        statusMessage = if (newDetectState) "Monitoreo habilitado" else "Monitoreo pausado"
                    )
                },
                onFailure = {
                    _uiState.value = currentState.copy(
                        statusMessage = "Error al actualizar configuración"
                    )
                }
            )
        }
    }

    private fun startEventPolling(cameraId: String) {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                delay(4000)
                val eventsRes = eventRepository.getEvents(cameraId)
                eventsRes.getOrNull()?.let { events ->
                    val state = _uiState.value as? StreamUiState.Success
                    if (state != null) {
                        _uiState.value = state.copy(recentEvents = events)
                    }
                }
            }
        }
    }

    fun dismissStatusMessage() {
        val currentState = _uiState.value as? StreamUiState.Success ?: return
        _uiState.value = currentState.copy(statusMessage = null)
    }

    override fun onCleared() {
        super.onCleared()
        pollingJob?.cancel()
    }
}
