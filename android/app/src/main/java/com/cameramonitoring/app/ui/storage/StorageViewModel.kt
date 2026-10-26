package com.cameramonitoring.app.ui.storage

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.model.CleanupResultResponse
import com.cameramonitoring.app.data.model.StorageStatsResponse
import com.cameramonitoring.app.data.repository.StorageRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface StorageUiState {
    object Loading : StorageUiState
    data class Success(
        val stats: StorageStatsResponse,
        val cleanupResult: CleanupResultResponse? = null,
        val statusMessage: String? = null
    ) : StorageUiState
    data class Error(val message: String) : StorageUiState
}

class StorageViewModel(
    private val storageRepository: StorageRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<StorageUiState>(StorageUiState.Loading)
    val uiState: StateFlow<StorageUiState> = _uiState.asStateFlow()

    fun loadStorageStats() {
        viewModelScope.launch {
            _uiState.value = StorageUiState.Loading
            val result = storageRepository.getStorageStats()
            result.fold(
                onSuccess = { stats ->
                    _uiState.value = StorageUiState.Success(stats = stats)
                },
                onFailure = { ex ->
                    _uiState.value = StorageUiState.Error(ex.message ?: "Error al cargar estadísticas de almacenamiento")
                }
            )
        }
    }

    fun updateRetentionPolicy(retentionDays: Int, autoCleanupEnabled: Boolean) {
        val currentState = _uiState.value as? StorageUiState.Success ?: return

        viewModelScope.launch {
            val res = storageRepository.updateRetentionPolicy(retentionDays, autoCleanupEnabled)
            res.fold(
                onSuccess = {
                    loadStorageStats()
                },
                onFailure = { ex ->
                    _uiState.value = currentState.copy(statusMessage = ex.message ?: "Error al guardar política de retención")
                }
            )
        }
    }

    fun runCleanup(dryRun: Boolean) {
        val currentState = _uiState.value as? StorageUiState.Success ?: return

        viewModelScope.launch {
            val res = storageRepository.triggerStorageCleanup(dryRun = dryRun)
            res.fold(
                onSuccess = { cleanupRes ->
                    val freshStats = storageRepository.getStorageStats().getOrNull() ?: currentState.stats
                    val msg = if (dryRun) {
                        "Simulación: Se liberarían ${cleanupRes.freedMb} MB (${cleanupRes.deletedPhotos} fotos, ${cleanupRes.deletedClips} videos)"
                    } else {
                        "Limpieza Ejecutada: Se liberaron ${cleanupRes.freedMb} MB (${cleanupRes.deletedPhotos} fotos, ${cleanupRes.deletedClips} videos)"
                    }
                    _uiState.value = StorageUiState.Success(
                        stats = freshStats,
                        cleanupResult = cleanupRes,
                        statusMessage = msg
                    )
                },
                onFailure = { ex ->
                    _uiState.value = currentState.copy(statusMessage = ex.message ?: "Error al ejecutar limpieza")
                }
            )
        }
    }

    fun dismissStatusMessage() {
        val currentState = _uiState.value as? StorageUiState.Success ?: return
        _uiState.value = currentState.copy(statusMessage = null)
    }
}
