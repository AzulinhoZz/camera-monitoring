package com.cameramonitoring.app.ui.events

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.CameraEvent
import com.cameramonitoring.app.data.repository.EventRepository
import com.cameramonitoring.app.data.repository.StorageRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface EventHistoryUiState {
    object Loading : EventHistoryUiState
    data class Success(
        val events: List<CameraEvent>,
        val evidenceUrls: Map<String, String> = emptyMap(),
        val clipUrls: Map<String, String> = emptyMap()
    ) : EventHistoryUiState
    data class Error(val message: String) : EventHistoryUiState
}

class EventHistoryViewModel(
    private val eventRepository: EventRepository,
    private val storageRepository: StorageRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<EventHistoryUiState>(EventHistoryUiState.Loading)
    val uiState: StateFlow<EventHistoryUiState> = _uiState.asStateFlow()

    fun loadEvents(cameraId: String? = null) {
        viewModelScope.launch {
            _uiState.value = EventHistoryUiState.Loading
            val result = eventRepository.getEvents(cameraId)
            result.fold(
                onSuccess = { events ->
                    _uiState.value = EventHistoryUiState.Success(events)
                    fetchMediaUrls(events)
                },
                onFailure = { ex ->
                    _uiState.value = EventHistoryUiState.Error(ex.message ?: "Error al cargar el historial de eventos")
                }
            )
        }
    }

    fun reviewEvent(eventId: String, status: String) {
        viewModelScope.launch {
            eventRepository.reviewAlert(eventId, status).fold(
                onSuccess = { loadEvents() },
                onFailure = { _uiState.value = EventHistoryUiState.Error("No se pudo guardar la revisión. Reintenta.") }
            )
        }
    }

    fun toggleProtection(eventId: String, currentProtected: Boolean) {
        viewModelScope.launch {
            val newProtected = !currentProtected
            val res = storageRepository.setEventProtectionStatus(eventId, newProtected)
            res.fold(
                onSuccess = {
                    loadEvents()
                },
                onFailure = {
                    // Refresh
                    loadEvents()
                }
            )
        }
    }

    private fun fetchMediaUrls(events: List<CameraEvent>) {
        viewModelScope.launch {
            val evUrls = mutableMapOf<String, String>()
            val clUrls = mutableMapOf<String, String>()

            events.forEach { event ->
                if (event.hasEvidence || event.evidencePath != null) {
                    val evRes = eventRepository.getEventEvidence(event.id)
                    evRes.getOrNull()?.signedUrl?.let { url ->
                        evUrls[event.id] = url
                    }
                }
                if (event.hasClip || event.clipPath != null) {
                    val clRes = eventRepository.getEventClip(event.id)
                    clRes.getOrNull()?.signedUrl?.let { url ->
                        clUrls[event.id] = url
                    }
                }
            }

            val currentState = _uiState.value as? EventHistoryUiState.Success
            if (currentState != null) {
                _uiState.value = currentState.copy(
                    evidenceUrls = evUrls,
                    clipUrls = clUrls
                )
            }
        }
    }
}
