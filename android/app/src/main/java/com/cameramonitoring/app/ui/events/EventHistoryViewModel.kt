package com.cameramonitoring.app.ui.events

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.Camera
import com.cameramonitoring.app.data.model.EventStatistics
import com.cameramonitoring.app.data.repository.CameraRepository
import com.cameramonitoring.app.data.model.CameraEvent
import com.cameramonitoring.app.data.repository.EventRepository
import com.cameramonitoring.app.data.repository.StorageRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.isActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.Instant

sealed interface EventHistoryUiState {
    object Loading : EventHistoryUiState
    data class Success(
        val events: List<CameraEvent>,
        val evidenceUrls: Map<String, String> = emptyMap(),
        val clipUrls: Map<String, String> = emptyMap(),
        val nextCursor: String? = null,
        val hasMore: Boolean = false,
        val statistics: EventStatistics? = null
    ) : EventHistoryUiState
    data class Error(val message: String) : EventHistoryUiState
}

class EventHistoryViewModel(
    private val eventRepository: EventRepository,
    private val storageRepository: StorageRepository,
    private val cameraRepository: CameraRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow<EventHistoryUiState>(EventHistoryUiState.Loading)
    val uiState: StateFlow<EventHistoryUiState> = _uiState.asStateFlow()
    private val _cameras = MutableStateFlow<List<Camera>>(emptyList())
    val cameras = _cameras.asStateFlow()
    fun loadCameras() { viewModelScope.launch { _cameras.value = cameraRepository.getCameras().getOrDefault(emptyList()) } }
    private var request: Job? = null
    private var generation = 0L
    private var selectedCamera: String? = null
    private var eventType: String? = null
    private var reviewStatus: String? = null
    private var since: String? = null
    private var cursor: String? = null

    fun search(type: String?, review: String?, hours: Long?, cameraId: String? = null) {
        selectedCamera = cameraId
        eventType = type; reviewStatus = review
        since = hours?.let { Instant.now().minusSeconds(it * 3600).toString() }
        cursor = null
        loadEvents()
    }

    fun firstPage() { cursor = null; loadEvents() }
    fun nextPage() {
        val state = _uiState.value as? EventHistoryUiState.Success ?: return
        if (!state.hasMore || state.nextCursor == null) return
        cursor = state.nextCursor
        loadEvents()
    }

    fun loadEvents(cameraId: String? = selectedCamera) {
        if (cameraId != selectedCamera) cursor = null
        selectedCamera = cameraId
        request?.cancel()
        val currentGeneration = ++generation
        request = viewModelScope.launch {
            _uiState.value = EventHistoryUiState.Loading
            eventRepository.getEventPage(selectedCamera, eventType, reviewStatus, since, cursor).fold(
                onSuccess = { page ->
                    if (!currentCoroutineContext().isActive || generation != currentGeneration) return@launch
                    _uiState.value = EventHistoryUiState.Success(page.events, nextCursor = page.nextCursor, hasMore = page.hasMore)
                    val statistics = eventRepository.getStatistics(selectedCamera, eventType, reviewStatus, since)
                    if (!currentCoroutineContext().isActive || generation != currentGeneration) return@launch
                    val firstState = _uiState.value as? EventHistoryUiState.Success
                    if (firstState != null) _uiState.value = firstState.copy(statistics = statistics)
                    // Media belongs only to this request; a newer search cancels it.
                    val evUrls = mutableMapOf<String, String>()
                    val clUrls = mutableMapOf<String, String>()
                    for (event in page.events) {
                        if (!currentCoroutineContext().isActive || generation != currentGeneration) return@launch
                        if (event.hasEvidence || event.evidencePath != null)
                            eventRepository.getEventEvidence(event.id).getOrNull()?.signedUrl?.let { evUrls[event.id] = it }
                        if (!currentCoroutineContext().isActive || generation != currentGeneration) return@launch
                        if (event.hasClip || event.clipPath != null)
                            eventRepository.getEventClip(event.id).getOrNull()?.signedUrl?.let { clUrls[event.id] = it }
                    }
                    if (currentCoroutineContext().isActive && generation == currentGeneration) {
                        val state = _uiState.value as? EventHistoryUiState.Success
                        if (state != null) _uiState.value = state.copy(evidenceUrls = evUrls, clipUrls = clUrls)
                    }
                },
                onFailure = {
                    if (currentCoroutineContext().isActive && generation == currentGeneration)
                        _uiState.value = EventHistoryUiState.Error("No se pudo cargar el historial. Reintenta.")
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
            storageRepository.setEventProtectionStatus(eventId, !currentProtected)
            loadEvents()
        }
    }
}
