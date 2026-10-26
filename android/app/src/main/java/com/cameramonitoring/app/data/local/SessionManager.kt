package com.cameramonitoring.app.data.local

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import com.cameramonitoring.app.data.model.SessionData

open class SessionManager {

    private val prefs: SharedPreferences?

    constructor(context: Context) {
        this.prefs = createEncryptedPrefs(context)
    }

    protected constructor() {
        this.prefs = null
    }

    private fun createEncryptedPrefs(context: Context): SharedPreferences {
        val fileName = "secure_session_prefs"
        return try {
            val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
            EncryptedSharedPreferences.create(
                fileName,
                masterKeyAlias,
                context,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.values()[0],
                EncryptedSharedPreferences.PrefValueEncryptionScheme.values()[0]
            )
        } catch (e: Exception) {
            Log.e("SessionManager", "Error creating EncryptedSharedPreferences, attempting reset", e)
            try {
                context.deleteSharedPreferences(fileName)
                val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
                EncryptedSharedPreferences.create(
                    fileName,
                    masterKeyAlias,
                    context,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.values()[0],
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.values()[0]
                )
            } catch (e2: Exception) {
                Log.e("SessionManager", "Failed to recreate EncryptedSharedPreferences safely", e2)
                context.getSharedPreferences("empty_dummy_prefs", Context.MODE_PRIVATE)
            }
        }
    }

    open fun saveSession(
        accessToken: String,
        refreshToken: String?,
        userId: String,
        userEmail: String?,
        fullName: String? = null
    ) {
        prefs?.edit()
            ?.putString(KEY_ACCESS_TOKEN, accessToken)
            ?.putString(KEY_REFRESH_TOKEN, refreshToken ?: "")
            ?.putString(KEY_USER_ID, userId)
            ?.putString(KEY_USER_EMAIL, userEmail ?: "")
            ?.putString(KEY_FULL_NAME, fullName ?: "")
            ?.apply()
    }

    open fun saveFCMToken(fcmToken: String) {
        prefs?.edit()?.putString(KEY_FCM_TOKEN, fcmToken)?.apply()
    }

    open fun getFCMToken(): String? {
        val token = prefs?.getString(KEY_FCM_TOKEN, null)
        return if (token.isNullOrBlank()) null else token
    }

    open fun getSession(): SessionData? {
        val token = prefs?.getString(KEY_ACCESS_TOKEN, null) ?: return null
        if (token.isBlank()) return null
        val refreshToken = prefs.getString(KEY_REFRESH_TOKEN, null)
        val userId = prefs.getString(KEY_USER_ID, "") ?: ""
        val userEmail = prefs.getString(KEY_USER_EMAIL, null)
        val fullName = prefs.getString(KEY_FULL_NAME, null)

        return SessionData(
            accessToken = token,
            refreshToken = refreshToken,
            userId = userId,
            userEmail = userEmail,
            fullName = if (fullName.isNullOrBlank()) null else fullName
        )
    }

    open fun getAccessToken(): String? {
        val token = prefs?.getString(KEY_ACCESS_TOKEN, null) ?: return null
        return if (token.isBlank()) null else token
    }

    open fun isLoggedIn(): Boolean {
        val token = prefs?.getString(KEY_ACCESS_TOKEN, null)
        return !token.isNullOrBlank()
    }

    open fun clearSession() {
        prefs?.edit()?.clear()?.apply()
    }

    companion object {
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_USER_EMAIL = "user_email"
        private const val KEY_FULL_NAME = "full_name"
        private const val KEY_FCM_TOKEN = "fcm_token"
    }
}
