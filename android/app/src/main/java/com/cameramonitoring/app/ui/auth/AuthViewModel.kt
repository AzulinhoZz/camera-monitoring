package com.cameramonitoring.app.ui.auth

import android.util.Patterns
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.cameramonitoring.app.data.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface AuthUiState {
    object Idle : AuthUiState
    object Loading : AuthUiState
    data class Success(val message: String? = null) : AuthUiState
    data class Error(val message: String) : AuthUiState
}

class AuthViewModel(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<AuthUiState>(
        if (authRepository.isLoggedIn()) AuthUiState.Success() else AuthUiState.Idle
    )
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun login(email: String, password: String) {
        if (email.isBlank() || password.isBlank()) {
            _uiState.value = AuthUiState.Error("Por favor, ingrese correo y contraseña")
            return
        }

        if (!Patterns.EMAIL_ADDRESS.matcher(email.trim()).matches()) {
            _uiState.value = AuthUiState.Error("Ingrese un correo electrónico válido")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = authRepository.login(email.trim(), password)
            result.fold(
                onSuccess = {
                    _uiState.value = AuthUiState.Success("Inicio de sesión exitoso")
                },
                onFailure = { ex ->
                    _uiState.value = AuthUiState.Error(ex.message ?: "Error al iniciar sesión")
                }
            )
        }
    }

    fun register(fullName: String, email: String, password: String, confirmPassword: String) {
        if (fullName.isBlank() || email.isBlank() || password.isBlank() || confirmPassword.isBlank()) {
            _uiState.value = AuthUiState.Error("Por favor, complete todos los campos")
            return
        }

        if (!Patterns.EMAIL_ADDRESS.matcher(email.trim()).matches()) {
            _uiState.value = AuthUiState.Error("Ingrese un correo electrónico válido")
            return
        }

        if (password.length < 8) {
            _uiState.value = AuthUiState.Error("La contraseña debe tener al menos 8 caracteres")
            return
        }

        if (password != confirmPassword) {
            _uiState.value = AuthUiState.Error("Las contraseñas no coinciden")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = authRepository.register(fullName.trim(), email.trim(), password)
            result.fold(
                onSuccess = { msg ->
                    _uiState.value = AuthUiState.Success(msg)
                },
                onFailure = { ex ->
                    _uiState.value = AuthUiState.Error(ex.message ?: "Error al registrar cuenta")
                }
            )
        }
    }

    fun forgotPassword(email: String) {
        if (email.isBlank() || !Patterns.EMAIL_ADDRESS.matcher(email.trim()).matches()) {
            _uiState.value = AuthUiState.Error("Ingrese un correo electrónico válido")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = authRepository.forgotPassword(email.trim())
            result.fold(
                onSuccess = { msg ->
                    _uiState.value = AuthUiState.Success(msg)
                },
                onFailure = { ex ->
                    _uiState.value = AuthUiState.Error(ex.message ?: "Error al solicitar recuperación")
                }
            )
        }
    }

    fun logout() {
        viewModelScope.launch {
            authRepository.logout()
            _uiState.value = AuthUiState.Idle
        }
    }

    fun getUserEmail(): String {
        return authRepository.getUserEmail() ?: "Conductor"
    }

    fun getUserFullName(): String {
        return authRepository.getUserFullName() ?: getUserEmail()
    }

    fun clearError() {
        if (_uiState.value is AuthUiState.Error) {
            _uiState.value = AuthUiState.Idle
        }
    }
}
