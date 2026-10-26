package com.cameramonitoring.app.ui.stream

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.Camera
import com.cameramonitoring.app.data.model.CameraEvent
import com.cameramonitoring.app.data.model.DetectionZone
import com.cameramonitoring.app.data.model.NormalizedPoint
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
        val sensitivityPreset: String = "medium",
        val scheduleType: String = "24/7",
        val scheduleDays: List<String> = listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
        val startTime: String = "00:00:00",
        val endTime: String = "23:59:59",
        val timezone: String = "America/Mexico_City",
        val isScheduleActive: Boolean = true,
        val zones: List<DetectionZone> = emptyList(),
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
                    val preset = status?.sensitivityPreset ?: "medium"
                    val schedType = status?.scheduleType ?: "24/7"
                    val schedDays = status?.scheduleDays ?: listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun")
                    val startT = status?.startTime ?: "00:00:00"
                    val endT = status?.endTime ?: "23:59:59"
                    val tz = status?.timezone ?: "America/Mexico_City"
                    val schedActive = status?.isScheduleActive ?: true

                    val zonesRes = eventRepository.getZones(cameraId)
                    val zones = zonesRes.getOrNull() ?: emptyList()

                    val eventsRes = eventRepository.getEvents(cameraId)
                    val initialEvents = eventsRes.getOrNull() ?: emptyList()

                    _uiState.value = StreamUiState.Success(
                        camera = camera,
                        isDetectingMotion = isActive,
                        motionEnabled = motionEnabled,
                        minArea = minArea,
                        threshold = threshold,
                        cooldownSeconds = cooldown,
                        sensitivityPreset = preset,
                        scheduleType = schedType,
                        scheduleDays = schedDays,
                        startTime = startT,
                        endTime = endT,
                        timezone = tz,
                        isScheduleActive = schedActive,
                        zones = zones,
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

    fun toggleMotionDetection(cameraId: String) {
        val currentState = _uiState.value as? StreamUiState.Success ?: return
        val newDetectState = !currentState.motionEnabled

        viewModelScope.launch {
            val action = if (newDetectState) "start" else "stop"
            val result = eventRepository.triggerMotionDetection(
                cameraId = cameraId,
                action = action,
                sensitivityPreset = currentState.sensitivityPreset,
                minArea = currentState.minArea,
                threshold = currentState.threshold,
                cooldownSeconds = currentState.cooldownSeconds,
                scheduleType = currentState.scheduleType,
                scheduleDays = currentState.scheduleDays,
                startTime = currentState.startTime,
                endTime = currentState.endTime,
                timezone = currentState.timezone
            )
            result.fold(
                onSuccess = { status ->
                    _uiState.value = currentState.copy(
                        isDetectingMotion = status.isActive,
                        motionEnabled = newDetectState,
                        isScheduleActive = status.isScheduleActive,
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

    fun updateMotionConfig(
        cameraId: String,
        sensitivityPreset: String,
        minArea: Int,
        threshold: Int,
        cooldownSeconds: Float,
        scheduleType: String,
        scheduleDays: List<String>,
        startTime: String,
        endTime: String,
        timezone: String
    ) {
        val currentState = _uiState.value as? StreamUiState.Success ?: return

        viewModelScope.launch {
            val result = eventRepository.triggerMotionDetection(
                cameraId = cameraId,
                action = "start",
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
            result.fold(
                onSuccess = { status ->
                    _uiState.value = currentState.copy(
                        isDetectingMotion = status.isActive,
                        motionEnabled = true,
                        minArea = status.minArea,
                        threshold = status.threshold,
                        cooldownSeconds = status.cooldownSeconds,
                        sensitivityPreset = status.sensitivityPreset,
                        scheduleType = status.scheduleType,
                        scheduleDays = status.scheduleDays,
                        startTime = status.startTime,
                        endTime = status.endTime,
                        timezone = status.timezone,
                        isScheduleActive = status.isScheduleActive,
                        statusMessage = "Ajustes de detección y horario guardados"
                    )
                },
                onFailure = { ex ->
                    _uiState.value = currentState.copy(
                        statusMessage = ex.message ?: "Error al guardar configuración"
                    )
                }
            )
        }
    }

    fun addZone(cameraId: String, name: String, points: List<NormalizedPoint>) {
        val currentState = _uiState.value as? StreamUiState.Success ?: return
        if (points.size < 3) {
            _uiState.value = currentState.copy(statusMessage = "Se requieren al menos 3 puntos para formar un polígono.")
            return
        }

        viewModelScope.launch {
            val res = eventRepository.createZone(cameraId, name, points)
            res.fold(
                onSuccess = {
                    val updatedZonesRes = eventRepository.getZones(cameraId)
                    _uiState.value = currentState.copy(
                        zones = updatedZonesRes.getOrNull() ?: emptyList(),
                        statusMessage = "Zona de detección guardada correctamente"
                    )
                },
                onFailure = { ex ->
                    _uiState.value = currentState.copy(
                        statusMessage = ex.message ?: "Error al guardar la zona"
                    )
                }
            )
        }
    }

    fun deleteZone(cameraId: String, zoneId: String) {
        val currentState = _uiState.value as? StreamUiState.Success ?: return
        viewModelScope.launch {
            val res = eventRepository.deleteZone(cameraId, zoneId)
            res.fold(
                onSuccess = {
                    val updatedZonesRes = eventRepository.getZones(cameraId)
                    _uiState.value = currentState.copy(
                        zones = updatedZonesRes.getOrNull() ?: emptyList(),
                        statusMessage = "Zona eliminada"
                    )
                },
                onFailure = { ex ->
                    _uiState.value = currentState.copy(
                        statusMessage = ex.message ?: "Error al eliminar la zona"
                    )
                }
            )
        }
    }

    fun clearAllZones(cameraId: String) {
        val currentState = _uiState.value as? StreamUiState.Success ?: return
        viewModelScope.launch {
            val res = eventRepository.clearAllZones(cameraId)
            res.fold(
                onSuccess = {
                    _uiState.value = currentState.copy(
                        zones = emptyList(),
                        statusMessage = "Detección en toda la imagen activada"
                    )
                },
                onFailure = { ex ->
                    _uiState.value = currentState.copy(
                        statusMessage = ex.message ?: "Error al restaurar detección completa"
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
