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
import kotlinx.coroutines.async
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.time.Instant

sealed interface EventHistoryUiState {
    object Loading : EventHistoryUiState
    data class Success(
        val events: List<CameraEvent>,
        val evidenceUrls: Map<String, String> = emptyMap(),
        val clipUrls: Map<String, String> = emptyMap(),
        val nextCursor: String? = null,
        val hasMore: Boolean = false,
        val statistics: EventStatistics? = null,
        val mediaErrors: Set<String> = emptySet(),
        val actionMessage: String? = null
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
    private var cameraRequest: Job? = null
    fun loadCameras() { cameraRequest?.cancel(); _cameras.value = emptyList(); cameraRequest = viewModelScope.launch { _cameras.value = cameraRepository.getCameras().getOrDefault(emptyList()) } }
    private val _rules = MutableStateFlow<List<com.cameramonitoring.app.data.model.VisionRule>>(emptyList())
    val rules = _rules.asStateFlow()
    private var ruleRequest: Job? = null
    private var mediaRequest: Job? = null
    private val openedMedia = mutableSetOf<String>()
    private var ruleId: String? = null
    private var request: Job? = null
    private var generation = 0L
    private var selectedCamera: String? = null
    private var eventType: String? = null
    private var reviewStatus: String? = null
    private var since: String? = null
    private var cursor: String? = null

    fun search(type: String?, review: String?, hours: Long?, cameraId: String? = null, selectedRuleId: String? = null) {
        val cameraChanged = cameraId != selectedCamera
        selectedCamera = cameraId
        if (cameraChanged) { ruleRequest?.cancel(); _rules.value = emptyList() }
        ruleId = selectedRuleId
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
        if (cameraId != null && _rules.value.isEmpty()) {
            ruleRequest?.cancel()
            ruleRequest = viewModelScope.launch {
                val result = eventRepository.getVisionRules(cameraId)
                if (currentCoroutineContext().isActive && selectedCamera == cameraId) _rules.value = result
            }
        }
        request?.cancel(); mediaRequest?.cancel(); openedMedia.clear()
        val currentGeneration = ++generation
        request = viewModelScope.launch {
            _uiState.value = EventHistoryUiState.Loading
            eventRepository.getEventPage(selectedCamera, eventType, reviewStatus, since, cursor, ruleId).fold(
                onSuccess = { page ->
                    if (!currentCoroutineContext().isActive || generation != currentGeneration) return@launch
                    _uiState.value = EventHistoryUiState.Success(page.events, nextCursor = page.nextCursor, hasMore = page.hasMore)
                    launch {
                        val statistics = withTimeoutOrNull(5000) { eventRepository.getStatistics(selectedCamera, eventType, reviewStatus, since, ruleId) }
                        if (currentCoroutineContext().isActive && generation == currentGeneration) {
                            val state = _uiState.value as? EventHistoryUiState.Success
                            if (state != null) _uiState.value = state.copy(statistics = statistics)
                        }
                    }
                    // Bounded thumbnail requests; clips are signed only on opening an incident.
                    val slots = Semaphore(4)
                    page.events.filter { it.hasEvidence || it.evidencePath != null }.forEach { event ->
                        launch {
                            slots.withPermit {
                                val url = withTimeoutOrNull(6000) { eventRepository.getEventEvidence(event.id).getOrNull()?.signedUrl }
                                if (currentCoroutineContext().isActive && generation == currentGeneration && event.id !in openedMedia) {
                                    val state = _uiState.value as? EventHistoryUiState.Success
                                    if (state != null) _uiState.value = if (url != null) state.copy(evidenceUrls = state.evidenceUrls + (event.id to url))
                                        else state.copy(mediaErrors = state.mediaErrors + event.id)
                                }
                            }
                        }
                    }
                },
                onFailure = {
                    if (currentCoroutineContext().isActive && generation == currentGeneration)
                        _uiState.value = EventHistoryUiState.Error("No se pudo cargar el historial. Reintenta.")
                }
            )
        }
    }

    fun loadEventMedia(eventId: String) {
        val state = _uiState.value as? EventHistoryUiState.Success ?: return
        val event = state.events.find { it.id == eventId } ?: return
        val currentGeneration = generation
        openedMedia.add(eventId)
        mediaRequest?.cancel()
        _uiState.value = state.copy(evidenceUrls = state.evidenceUrls - eventId,
            clipUrls = state.clipUrls - eventId, mediaErrors = state.mediaErrors - eventId)
        mediaRequest = viewModelScope.launch {
            val pendingImage = async { if (event.hasEvidence || event.evidencePath != null)
                withTimeoutOrNull(6000) { eventRepository.getEventEvidence(eventId).getOrNull()?.signedUrl } else null }
            val pendingClip = async { if (event.hasClip || event.clipPath != null)
                withTimeoutOrNull(6000) { eventRepository.getEventClip(eventId).getOrNull()?.signedUrl } else null }
            val image = pendingImage.await()
            val clip = pendingClip.await()
            if (currentCoroutineContext().isActive && generation == currentGeneration) {
                val current = _uiState.value as? EventHistoryUiState.Success ?: return@launch
                val failed = ((event.hasEvidence || event.evidencePath != null) && image == null) ||
                    ((event.hasClip || event.clipPath != null) && clip == null)
                _uiState.value = current.copy(
                    evidenceUrls = if (image != null) current.evidenceUrls + (eventId to image) else current.evidenceUrls - eventId,
                    clipUrls = if (clip != null) current.clipUrls + (eventId to clip) else current.clipUrls - eventId,
                    mediaErrors = if (failed) current.mediaErrors + eventId else current.mediaErrors - eventId)
            }
        }
    }

    fun clearMedia() {
        ++generation; request?.cancel(); mediaRequest?.cancel(); cameraRequest?.cancel(); ruleRequest?.cancel(); _rules.value = emptyList(); _cameras.value = emptyList()
        val state = _uiState.value as? EventHistoryUiState.Success ?: return
        _uiState.value = state.copy(evidenceUrls = emptyMap(), clipUrls = emptyMap(), mediaErrors = emptySet())
    }

    fun reviewEvent(eventId: String, status: String) {
        val currentGeneration = generation
        viewModelScope.launch {
            val result = eventRepository.reviewAlert(eventId, status)
            if (generation != currentGeneration) return@launch
            result.fold(onSuccess = { loadEvents() }, onFailure = { actionFailed("No se pudo guardar la revisión. Reintenta.") })
        }
    }

    private fun actionFailed(message: String) {
        val state = _uiState.value as? EventHistoryUiState.Success ?: return
        _uiState.value = state.copy(actionMessage = message)
    }

    fun toggleProtection(eventId: String, currentProtected: Boolean) {
        val currentGeneration = generation
        viewModelScope.launch {
            val result = storageRepository.setEventProtectionStatus(eventId, !currentProtected)
            if (generation != currentGeneration) return@launch
            result.fold(onSuccess = { loadEvents() }, onFailure = { actionFailed("No se pudo cambiar la protección. Reintenta.") })
        }
    }
}
