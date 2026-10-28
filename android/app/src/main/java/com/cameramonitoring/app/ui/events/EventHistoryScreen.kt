package com.cameramonitoring.app.ui.events

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.LockOpen
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.NotificationsNone
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SdCard
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import coil.compose.AsyncImage
import com.cameramonitoring.app.data.model.CameraEvent

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EventHistoryScreen(
    viewModel: EventHistoryViewModel,
    onBackClick: () -> Unit,
    onStorageClick: () -> Unit = {}
) {
    val uiState by viewModel.uiState.collectAsState()
    var selectedEventForDetail by remember { mutableStateOf<Triple<CameraEvent, String?, String?>?>(null) }
    var activePlayingClipUrl by remember { mutableStateOf<String?>(null) }

    var eventType by rememberSaveable { mutableStateOf<String?>(null) }
    var reviewStatus by rememberSaveable { mutableStateOf<String?>(null) }
    var hours by rememberSaveable { mutableStateOf<Long?>(null) }
    LaunchedEffect(eventType, reviewStatus, hours) {
        selectedEventForDetail = null
        activePlayingClipUrl = null
        viewModel.search(eventType, reviewStatus, hours)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Historial de Eventos", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    IconButton(onClick = onStorageClick) {
                        Icon(Icons.Default.SdCard, contentDescription = "Gestión Almacenamiento", tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = { viewModel.loadEvents() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Actualizar")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .background(MaterialTheme.colorScheme.background)
        ) {
            Column(Modifier.padding(horizontal = 16.dp)) {
                Text("Buscar eventos", style = MaterialTheme.typography.titleMedium)
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(null to "Todos", "motion_detected" to "Movimiento", "vision_intrusion" to "Intrusión",
                        "vision_dwell" to "Permanencia", "vision_line_crossing" to "Cruce",
                        "vision_count" to "Conteo", "vision_probable_abandoned_object" to "Posible abandono").forEach { (value, label) ->
                        FilterChip(selected = eventType == value, onClick = { eventType = value }, label = { Text(label) })
                    }
                }
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(null to "Toda revisión", "pending" to "Pendientes", "reviewed_ok" to "Revisados", "help_requested" to "Ayuda solicitada").forEach { (value, label) ->
                        FilterChip(selected = reviewStatus == value, onClick = { reviewStatus = value }, label = { Text(label) })
                    }
                }
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(null to "Todo el periodo", 24L to "Últimas 24 h", 168L to "Últimos 7 días").forEach { (value, label) ->
                        FilterChip(selected = hours == value, onClick = { hours = value }, label = { Text(label) })
                    }
                }
            }
            Box(Modifier.weight(1f)) {
            when (val state = uiState) {
                is EventHistoryUiState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                    }
                }
                is EventHistoryUiState.Error -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Warning,
                            contentDescription = "Error",
                            tint = MaterialTheme.colorScheme.error,
                            modifier = Modifier.size(48.dp)
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = state.message,
                            color = MaterialTheme.colorScheme.error,
                            fontSize = 15.sp
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = { viewModel.loadEvents() }) {
                            Text("Reintentar")
                        }
                    }
                }
                is EventHistoryUiState.Success -> {
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        modifier = Modifier.fillMaxSize()
                    ) {
                        item {
                            Text("Resumen de esta página", style = MaterialTheme.typography.titleMedium)
                            Text("${state.events.size} eventos · ${state.events.count { it.reviewStatus == "pending" }} pendientes")
                            Text("Los conteos corresponden a esta página, no al total del historial.", style = MaterialTheme.typography.bodySmall)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedButton(onClick = { viewModel.firstPage() }) { Text("Inicio") }
                                Button(onClick = { viewModel.nextPage() }, enabled = state.hasMore && state.nextCursor != null) { Text("Siguiente") }
                            }
                        }
                        if (state.events.isEmpty()) item {
                            Text("Sin eventos para estos filtros. Puedes cambiar el periodo o volver al inicio.")
                        }
                        items(state.events, key = { it.id }) { event ->
                            val imageUrl = state.evidenceUrls[event.id]
                            val clipUrl = state.clipUrls[event.id]
                            EventItemCard(
                                event = event,
                                imageUrl = imageUrl,
                                hasClip = clipUrl != null || event.hasClip || event.clipPath != null,
                                onClick = { selectedEventForDetail = Triple(event, imageUrl, clipUrl) }
                            )
                        }
                    }
                }
            }
            }
        }

        selectedEventForDetail?.let { (event, initialImgUrl, initialClipUrl) ->
            val currentImgUrl = (uiState as? EventHistoryUiState.Success)?.evidenceUrls?.get(event.id) ?: initialImgUrl
            val currentClipUrl = (uiState as? EventHistoryUiState.Success)?.clipUrls?.get(event.id) ?: initialClipUrl

            EventDetailDialog(
                event = event,
                imageUrl = currentImgUrl,
                clipUrl = currentClipUrl,
                onDismiss = { selectedEventForDetail = null },
                onPlayClip = { url ->
                    activePlayingClipUrl = url
                },
                onReview = { status ->
                    viewModel.reviewEvent(event.id, status)
                    selectedEventForDetail = null
                },
                onToggleProtect = {
                    viewModel.toggleProtection(event.id, event.isProtected)
                    selectedEventForDetail = null
                }
            )
        }

        activePlayingClipUrl?.let { clipUrl ->
            ClipPlayerDialog(
                clipUrl = clipUrl,
                onDismiss = { activePlayingClipUrl = null }
            )
        }
    }
}

@Composable
fun EventItemCard(
    event: CameraEvent,
    imageUrl: String?,
    hasClip: Boolean,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (imageUrl != null) {
                Box {
                    AsyncImage(
                        model = imageUrl,
                        contentDescription = "Evidencia Fotograma",
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .size(56.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color.DarkGray)
                    )
                    if (hasClip) {
                        Surface(
                            color = Color.Black.copy(alpha = 0.65f),
                            shape = CircleShape,
                            modifier = Modifier
                                .align(Alignment.Center)
                                .size(24.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = Icons.Default.PlayCircle,
                                    contentDescription = "Tiene Video Clip",
                                    tint = Color.White,
                                    modifier = Modifier.size(16.dp)
                                )
                            }
                        }
                    }
                }
            } else if (event.hasEvidence || event.evidencePath != null) {
                Box(
                    modifier = Modifier
                        .size(56.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                }
            } else {
                Surface(
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.error.copy(alpha = 0.15f),
                    modifier = Modifier.size(44.dp)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = if (hasClip) Icons.Default.Movie else Icons.Default.Warning,
                            contentDescription = "Alerta Movimiento",
                            tint = MaterialTheme.colorScheme.error,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.width(14.dp))

            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = event.cameraName ?: "Cámara",
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        if (event.isProtected) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Icon(
                                imageVector = Icons.Default.Lock,
                                contentDescription = "Protegido",
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(14.dp)
                            )
                        }
                    }
                    Text(
                        text = event.detectedAt?.take(19)?.replace("T", " ") ?: "",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Spacer(modifier = Modifier.height(4.dp))

                Text(
                    text = event.description ?: "Movimiento detectado por algoritmo OpenCV",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                Row(
                    modifier = Modifier.padding(top = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    if (event.hasEvidence || event.evidencePath != null) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Image,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(12.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "Foto",
                                fontSize = 10.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                    if (hasClip) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Movie,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.secondary,
                                modifier = Modifier.size(12.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "Grabación Clip MP4",
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.secondary
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun EventDetailDialog(
    event: CameraEvent,
    imageUrl: String?,
    clipUrl: String?,
    onDismiss: () -> Unit,
    onPlayClip: (String) -> Unit,
    onToggleProtect: () -> Unit,
    onReview: (String) -> Unit = {}
) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth(0.92f)
                .wrapContentHeight(),
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surface
        ) {
            Column(
                modifier = Modifier.padding(20.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = event.cameraName ?: "Detalle del Evento",
                            fontWeight = FontWeight.Bold,
                            fontSize = 18.sp
                        )
                        if (event.isProtected) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Icon(Icons.Default.Lock, contentDescription = "Protegido", tint = MaterialTheme.colorScheme.primary)
                        }
                    }
                    IconButton(onClick = onDismiss) {
                        Icon(Icons.Default.Close, contentDescription = "Cerrar")
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                if (imageUrl != null) {
                    Card(
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(16f / 9f)
                    ) {
                        AsyncImage(
                            model = imageUrl,
                            contentDescription = "Evidencia Completa de Movimiento",
                            contentScale = ContentScale.Fit,
                            modifier = Modifier
                                .fillMaxSize()
                                .background(Color.Black)
                        )
                    }
                } else if (event.hasEvidence || event.evidencePath != null) {
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(140.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                CircularProgressIndicator(modifier = Modifier.size(28.dp))
                                Spacer(modifier = Modifier.height(8.dp))
                                Text("Obteniendo foto de evidencia desde Supabase...", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                } else {
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(100.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text("Sin captura de evidencia fotográfica", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "Fecha y hora: ${event.detectedAt?.take(19)?.replace("T", " ") ?: "Desconocida"}",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurface
                )

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = "Descripción: ${event.description ?: "Movimiento detectado por OpenCV"}",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                Spacer(modifier = Modifier.height(16.dp))

                if (clipUrl != null) {
                    Button(
                        onClick = { onPlayClip(clipUrl) },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.secondary)
                    ) {
                        Icon(Icons.Default.PlayCircle, contentDescription = null, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Ver grabación", fontWeight = FontWeight.Bold)
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                } else if (event.hasClip || event.clipPath != null) {
                    OutlinedButton(
                        onClick = { },
                        enabled = false,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Cargando clip de video...", fontSize = 13.sp)
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                }

                Text("Estado de revisión: ${event.reviewStatus}")
                if (event.eventType.startsWith("vision_")) {
                    Text("Detección automática sujeta a revisión humana; puede ser un falso positivo.")
                    val labels = mapOf("intrusion" to "Intrusión", "dwell" to "Permanencia", "count" to "Conteo", "line_crossing" to "Cruce de línea", "probable_abandoned_object" to "Posible objeto abandonado")
                    Text(labels[event.visionSummary?.eventType] ?: "Regla de visión")
                    event.visionSummary?.count?.let { Text("Objetos visibles: $it") }
                    event.visionSummary?.direction?.let { Text("Dirección: ${if (it == "positive") "positiva" else "negativa"}") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { onReview("reviewed_ok") }) { Text("Revisado / sin incidencia") }
                    TextButton(onClick = { onReview("help_requested") }) { Text("Solicitar ayuda") }
                }
                OutlinedButton(
                    onClick = onToggleProtect,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(if (event.isProtected) Icons.Default.LockOpen else Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(if (event.isProtected) "Desproteger Evento" else "Proteger Evento de Limpieza Automática")
                }

                Spacer(modifier = Modifier.height(8.dp))

                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Cerrar")
                }
            }
        }
    }
}

@Composable
fun ClipPlayerDialog(
    clipUrl: String,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    var exoPlayer by remember { mutableStateOf<ExoPlayer?>(null) }

    DisposableEffect(clipUrl) {
        val player = ExoPlayer.Builder(context).build().apply {
            setMediaItem(MediaItem.fromUri(clipUrl))
            prepare()
            playWhenReady = true
        }
        exoPlayer = player
        onDispose {
            player.release()
        }
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth(0.95f)
                .wrapContentHeight(),
            shape = RoundedCornerShape(16.dp),
            color = Color.Black
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Reproduciendo Clip MP4", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    IconButton(onClick = onDismiss) {
                        Icon(Icons.Default.Close, contentDescription = "Cerrar Video", tint = Color.White)
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(16f / 9f)
                        .clip(RoundedCornerShape(8.dp))
                ) {
                    AndroidView(
                        factory = { ctx ->
                            PlayerView(ctx).apply {
                                player = exoPlayer
                                useController = true
                            }
                        },
                        modifier = Modifier.fillMaxSize()
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                Button(
                    onClick = onDismiss,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.DarkGray)
                ) {
                    Text("Cerrar Reproductor", color = Color.White)
                }
            }
        }
    }
}
