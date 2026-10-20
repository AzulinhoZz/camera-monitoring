package com.cameramonitoring.app.ui.events

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.CameraEvent
import com.cameramonitoring.app.data.repository.EventRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface EventHistoryUiState {
    object Loading : EventHistoryUiState
    data class Success(val events: List<CameraEvent>) : EventHistoryUiState
    data class Error(val message: String) : EventHistoryUiState
}

class EventHistoryViewModel(
    private val eventRepository: EventRepository
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
                },
                onFailure = { ex ->
                    _uiState.value = EventHistoryUiState.Error(ex.message ?: "Error al cargar el historial de eventos")
                }
            )
        }
    }
}
