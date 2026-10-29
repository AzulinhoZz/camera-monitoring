package com.cameramonitoring.app.ui.stream

import android.os.SystemClock
import android.util.Base64
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.CachePolicy
import coil.request.ImageRequest
import androidx.compose.ui.platform.LocalContext
import com.cameramonitoring.app.data.model.VisionStatus
import com.cameramonitoring.app.data.model.previewLifetimeMillis
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withTimeoutOrNull

@Composable
fun VisionStatusPanel(cameraId: String, load: suspend (Boolean, Boolean) -> VisionStatus?) {
    var preview by remember(cameraId) { mutableStateOf(false) }
    var overlay by remember(cameraId) { mutableStateOf(false) }
    var snapshot by remember(cameraId) { mutableStateOf<VisionStatus?>(null) }
    var image by remember(cameraId) { mutableStateOf<ByteArray?>(null) }
    val owner = LocalLifecycleOwner.current
    var details by rememberSaveable(cameraId) { mutableStateOf(false) }
    LaunchedEffect(cameraId, preview, overlay, owner) {
        owner.lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
        try {
        snapshot = null; image = null
        while (isActive) {
            val started = SystemClock.elapsedRealtime()
            val result = withTimeoutOrNull(3000) { load(preview, overlay) }
            snapshot = result?.takeIf { it.cameraId == cameraId }
            val roundTrip = (SystemClock.elapsedRealtime() - started) / 1000.0
            val lifetime = previewLifetimeMillis(cameraId, snapshot, roundTrip)
            val fresh = lifetime > 0
            image = if (preview && fresh) snapshot?.imageBase64?.takeIf { it.length <= 450000 }?.let {
                runCatching { Base64.decode(it, Base64.DEFAULT) }.getOrNull()
            } else null
            // No cached image survives the server's frame-age deadline, even during a stalled request.
            val remaining = lifetime.coerceAtMost(1000)
            delay(if (image != null) remaining else 1000)
            image = null
            snapshot = null
        }
        } finally { snapshot = null; image = null }
        }
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Análisis IA", style = MaterialTheme.typography.titleMedium)
            val current = snapshot
            Text(if (current == null || current.state == "unavailable") "Estado no disponible" else if (current.healthy) "Análisis activo" else "Sin señal de análisis saludable")
            current?.diagnostics?.codes?.forEach { code ->
                val label = when (code) {
                    "capture_unavailable" -> "La cámara no está enviando señal saludable."
                    "frame_stale" -> "La imagen de análisis está retrasada."
                    "inference_not_ready" -> "El análisis aún no está listo."
                    "inference_below_target" -> "El análisis no alcanza la velocidad objetivo; revisa la capacidad del servidor."
                    "inference_drops_observed" -> "Se han omitido imágenes de análisis; revisa la carga si continúa."
                    else -> null
                }
                label?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
            Row { Switch(details, { details = it }); Text(" Detalles de diagnóstico") }
            if (details) current?.let {
                Text("Captura: ${"%.1f".format(it.captureFps)} FPS · Inferencia: ${"%.1f".format(it.inferenceFps)} FPS · ${it.inferenceFrames} frames analizados · ${it.inferenceDropped} descartados")
                Text("Memoria: ${it.rssBytes / 1048576} MiB · CPU acumulada: ${"%.1f".format(it.cpuSeconds)} s")
            }
            Row { Switch(preview, { preview = it }); Text(" Vista del frame analizado") }
            if (preview) {
                Row { Switch(overlay, { overlay = it }); Text(" Dibujar detecciones y esqueleto") }
                Text("Imagen de análisis con caducidad; el vídeo en vivo se muestra por separado.")
                image?.let { pixels ->
                    AsyncImage(model = ImageRequest.Builder(LocalContext.current).data(pixels)
                        .memoryCachePolicy(CachePolicy.DISABLED).diskCachePolicy(CachePolicy.DISABLED).build(), contentDescription = "Frame analizado con overlays opcionales",
                        modifier = Modifier.fillMaxWidth().heightIn(max = 320.dp), contentScale = ContentScale.Fit)
                    current?.frameAt?.let { Text("Capturado: $it", style = MaterialTheme.typography.bodySmall) }
                } ?: Text("No hay un frame reciente disponible.")
            }
        }
    }
}
