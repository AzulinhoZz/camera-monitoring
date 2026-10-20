package com.cameramonitoring.app.data.remote

import android.R
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.cameramonitoring.app.MainActivity
import com.cameramonitoring.app.data.local.SessionManager
import com.cameramonitoring.app.data.repository.AuthRepository
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MyFirebaseMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.i("FCM", "New FCM Token received: ${token.take(20)}...")

        val sessionManager = SessionManager(applicationContext)
        sessionManager.saveFCMToken(token)

        if (sessionManager.isLoggedIn()) {
            val apiService = ApiClient.getApiService(sessionManager)
            val authRepository = AuthRepository(apiService, sessionManager)
            CoroutineScope(Dispatchers.IO).launch {
                authRepository.registerFCMToken(token)
            }
        }
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)
        Log.i("FCM", "Message received from FCM: ${remoteMessage.notification?.title}")

        val title = remoteMessage.notification?.title ?: "¡Alerta de Movimiento!"
        val body = remoteMessage.notification?.body ?: remoteMessage.data["description"] ?: "Se detectó movimiento en su cámara."
        val cameraId = remoteMessage.data["camera_id"] ?: ""

        showNotification(title, body, cameraId)
    }

    private fun showNotification(title: String, body: String, cameraId: String) {
        val channelId = "camera_monitoring_alerts"
        val notificationId = System.currentTimeMillis().toInt()

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("camera_id", cameraId)
        }

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Alertas de Movimiento",
                NotificationManager.IMPORTANCE_DEFAULT // Default importance without heads-up banner
            ).apply {
                description = "Notificaciones de detección de movimiento con OpenCV"
            }
            notificationManager.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        try {
            NotificationManagerCompat.from(this).notify(notificationId, notification)
        } catch (e: SecurityException) {
            Log.e("FCM", "Permission missing for notification: ${e.message}")
        }
    }
}
