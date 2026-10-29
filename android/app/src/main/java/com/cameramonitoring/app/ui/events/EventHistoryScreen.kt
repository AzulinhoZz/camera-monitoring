package com.cameramonitoring.app.ui.events

import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.platform.LocalConfiguration
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
import coil.request.ImageRequest
import coil.request.CachePolicy
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.cameramonitoring.app.data.model.incidentReason
import com.cameramonitoring.app.data.model.eventTimestampLabel
import com.cameramonitoring.app.data.model.eventSearchRange
import com.cameramonitoring.app.data.model.EventSearchRange
import com.cameramonitoring.app.data.model.CameraEvent

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EventHistoryScreen(
    viewModel: EventHistoryViewModel,
    onBackClick: () -> Unit,
    onStorageClick: () -> Unit = {},
    initialCameraId: String? = null,
    initialPending: Boolean = false
) {
    val uiState by viewModel.uiState.collectAsState()
    val cameras by viewModel.cameras.collectAsState()
    val rules by viewModel.rules.collectAsState()
    var selectedRule by rememberSaveable { mutableStateOf<String?>(null) }
    var selectedCamera by rememberSaveable(initialCameraId) { mutableStateOf(initialCameraId) }
    LaunchedEffect(Unit) { viewModel.loadCameras() }
    var selectedEventForDetail by remember { mutableStateOf<CameraEvent?>(null) }
    var activePlayingClipUrl by remember { mutableStateOf<String?>(null) }

    var customSince by rememberSaveable { mutableStateOf<String?>(null) }
    var customUntil by rememberSaveable { mutableStateOf<String?>(null) }
    var showRange by remember { mutableStateOf(false) }
    var eventType by rememberSaveable { mutableStateOf<String?>(null) }
    var reviewStatus by rememberSaveable(initialPending) { mutableStateOf<String?>(if (initialPending) "pending" else null) }
    var hours by rememberSaveable(initialPending) { mutableStateOf<Long?>(if (initialPending) 24L else null) }
    LaunchedEffect(eventType, reviewStatus, hours, selectedCamera, selectedRule, customSince, customUntil) {
        selectedEventForDetail = null
        activePlayingClipUrl = null
        viewModel.search(eventType, reviewStatus, hours, selectedCamera, selectedRule, customSince, customUntil)
    }

    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        var stopped = false
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) {
                stopped = true; selectedEventForDetail = null; activePlayingClipUrl = null; viewModel.clearMedia()
            } else if (event == Lifecycle.Event.ON_START && stopped) {
                stopped = false; viewModel.loadCameras(); viewModel.loadEvents()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer); viewModel.clearMedia() }
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
                    FilterChip(selected = selectedCamera == null, onClick = { selectedCamera = null; selectedRule = null }, label = { Text("Todas las cámaras") })
                    cameras.forEach { camera ->
                        FilterChip(selected = selectedCamera == camera.id, onClick = { selectedCamera = camera.id; selectedRule = null }, label = { Text(camera.name) })
                    }
                }
                if (selectedCamera != null && (rules.isNotEmpty() || selectedRule != null)) Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = selectedRule == null, onClick = { selectedRule = null }, label = { Text("Todas las reglas / zonas") })
                    if (selectedRule != null && rules.none { it.ruleId == selectedRule }) FilterChip(selected = true, onClick = { selectedRule = null }, label = { Text("Regla anterior · quitar filtro") })
                    rules.forEachIndexed { index, rule ->
                        FilterChip(selected = selectedRule == rule.ruleId, onClick = { selectedRule = rule.ruleId }, label = { Text("Regla / zona ${index + 1}${if (rule.enabled) "" else " · pausada"}") })
                    }
                }
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
                        FilterChip(selected = hours == value && customSince == null, onClick = { hours = value; customSince = null; customUntil = null }, label = { Text(label) })
                    }
                    FilterChip(selected = customSince != null, onClick = { showRange = true }, label = { Text("Fecha y hora") })
                }
                if (customSince != null) Text("${eventTimestampLabel(customSince)} — ${eventTimestampLabel(customUntil)}", style = MaterialTheme.typography.bodySmall)
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
                            state.actionMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                            state.statistics?.let { stats ->
                                Text("Estadísticas · ${if (customSince != null) "rango seleccionado" else if (hours == null) "últimas 24 h" else if (hours == 24L) "últimas 24 h" else "últimos 7 días"}", style = MaterialTheme.typography.titleMedium)
                                Text("${stats.total} eventos · ${stats.pending} pendientes (cámaras y filtros seleccionados)")
                            } ?: Text("Estadísticas no disponibles; los eventos siguen visibles.")
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
                                onClick = { selectedEventForDetail = event; viewModel.loadEventMedia(event.id) }
                            )
                        }
                    }
                }
            }
            }
        }

        if (showRange) EventSearchRangeDialog(onDismiss = { showRange = false }, onApply = { range ->
            hours = null; customSince = range.since; customUntil = range.until; showRange = false
        })

        selectedEventForDetail?.let { event ->
            val currentImgUrl = (uiState as? EventHistoryUiState.Success)?.evidenceUrls?.get(event.id)
            val currentClipUrl = (uiState as? EventHistoryUiState.Success)?.clipUrls?.get(event.id)

            EventDetailDialog(
                event = event,
                imageUrl = currentImgUrl,
                clipUrl = currentClipUrl,
                mediaUnavailable = (uiState as? EventHistoryUiState.Success)?.mediaErrors?.contains(event.id) == true,
                onRetryMedia = { viewModel.loadEventMedia(event.id) },
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
                        model = ImageRequest.Builder(LocalContext.current).data(imageUrl).memoryCachePolicy(CachePolicy.DISABLED).diskCachePolicy(CachePolicy.DISABLED).build(),
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
                        text = eventTimestampLabel(event.detectedAt),
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
    onReview: (String) -> Unit = {},
    mediaUnavailable: Boolean = false,
    onRetryMedia: () -> Unit = {}
) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth(0.92f)
                .heightIn(max = LocalConfiguration.current.screenHeightDp.dp * 0.9f)
                .wrapContentHeight(),
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surface
        ) {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()).padding(20.dp)
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
                            model = ImageRequest.Builder(LocalContext.current).data(imageUrl).memoryCachePolicy(CachePolicy.DISABLED).diskCachePolicy(CachePolicy.DISABLED).build(),
                            contentDescription = "Evidencia Completa de Movimiento",
                            contentScale = ContentScale.Fit,
                            modifier = Modifier
                                .fillMaxSize()
                                .background(Color.Black)
                        )
                    }
                } else if ((event.hasEvidence || event.evidencePath != null) && !mediaUnavailable) {
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
                            Text(if (mediaUnavailable) "Captura no disponible" else "Sin captura de evidencia fotográfica", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "Fecha y hora: ${eventTimestampLabel(event.detectedAt)}",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurface
                )

                Spacer(modifier = Modifier.height(6.dp))

                Text("Motivo: ${event.incidentReason()}", style = MaterialTheme.typography.titleMedium)
                if (mediaUnavailable) {
                    Text("No se pudo cargar toda la evidencia. Comprueba tu conexión o permisos.")
                    TextButton(onClick = onRetryMedia) { Text("Reintentar evidencia") }
                }
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
                } else if ((event.hasClip || event.clipPath != null) && !mediaUnavailable) {
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
    var playbackFailed by remember(clipUrl) { mutableStateOf(false) }

    DisposableEffect(clipUrl) {
        val player = ExoPlayer.Builder(context).build().apply {
            addListener(object : androidx.media3.common.Player.Listener {
                override fun onPlayerError(error: androidx.media3.common.PlaybackException) { playbackFailed = true }
            })
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
                    Text(if (playbackFailed) "No se pudo reproducir. Revisa la conexión y vuelve a abrir el incidente." else "Reproduciendo Clip MP4", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 16.sp)
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


@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EventSearchRangeDialog(onDismiss: () -> Unit, onApply: (EventSearchRange) -> Unit) {
    var start by remember { mutableStateOf(java.time.LocalDateTime.now().minusDays(1).withSecond(0).withNano(0)) }
    var end by remember { mutableStateOf(java.time.LocalDateTime.now().withSecond(0).withNano(0)) }
    var editDate by remember { mutableStateOf<Boolean?>(null) }
    var editTime by remember { mutableStateOf<Boolean?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val formatter = remember { java.time.format.DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm") }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Buscar por fecha y hora") }, text = {
        Column(Modifier.heightIn(max = LocalConfiguration.current.screenHeightDp.dp * 0.6f).verticalScroll(rememberScrollState())) {
            Text("Hora del teléfono: ${java.time.ZoneId.systemDefault().id}")
            Text("Desde: ${start.format(formatter)}")
            Row { TextButton(onClick = { editDate = true }) { Text("Fecha inicial") }; TextButton(onClick = { editTime = true }) { Text("Hora inicial") } }
            Text("Hasta: ${end.format(formatter)} (minuto incluido)")
            Row { TextButton(onClick = { editDate = false }) { Text("Fecha final") }; TextButton(onClick = { editTime = false }) { Text("Hora final") } }
            Text("Máximo 31 días para incluir las estadísticas.")
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { TextButton(onClick = {
        runCatching { eventSearchRange(start,end) }.fold(onSuccess = onApply, onFailure = { error = it.message ?: "Rango inválido" })
    }) { Text("Buscar") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } })
    editDate?.let { initial ->
        val value = if (initial) start else end
        val state = rememberDatePickerState(initialSelectedDateMillis = value.toLocalDate().atStartOfDay(java.time.ZoneOffset.UTC).toInstant().toEpochMilli())
        DatePickerDialog(onDismissRequest = { editDate = null }, confirmButton = {
            TextButton(onClick = {
                state.selectedDateMillis?.let { millis ->
                    val date = java.time.Instant.ofEpochMilli(millis).atZone(java.time.ZoneOffset.UTC).toLocalDate()
                    if (initial) start = java.time.LocalDateTime.of(date,start.toLocalTime()) else end = java.time.LocalDateTime.of(date,end.toLocalTime())
                }
                editDate = null; error = null
            }) { Text("Aceptar") }
        }, dismissButton = { TextButton(onClick = { editDate = null }) { Text("Cancelar") } }) { DatePicker(state) }
    }
    editTime?.let { initial ->
        val value = if (initial) start else end
        val state = rememberTimePickerState(initialHour = value.hour,initialMinute = value.minute,is24Hour = true)
        AlertDialog(onDismissRequest = { editTime = null }, title = { Text(if (initial) "Hora inicial" else "Hora final") },
            text = { Box(Modifier.heightIn(max = LocalConfiguration.current.screenHeightDp.dp * 0.6f).verticalScroll(rememberScrollState())) { TimePicker(state) } }, confirmButton = {
                TextButton(onClick = {
                    if (initial) start = start.withHour(state.hour).withMinute(state.minute) else end = end.withHour(state.hour).withMinute(state.minute)
                    editTime = null; error = null
                }) { Text("Aceptar") }
            }, dismissButton = { TextButton(onClick = { editTime = null }) { Text("Cancelar") } })
    }
}
