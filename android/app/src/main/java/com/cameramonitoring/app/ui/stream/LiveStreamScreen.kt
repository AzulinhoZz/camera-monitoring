package com.cameramonitoring.app.ui.stream

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CropFree
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.NotificationsNone
import androidx.compose.material.icons.filled.Polyline
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.hls.HlsMediaSource
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.cameramonitoring.app.data.model.CameraEvent
import com.cameramonitoring.app.data.model.DetectionZone
import com.cameramonitoring.app.data.model.NormalizedPoint

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LiveStreamScreen(
    cameraId: String,
    viewModel: LiveStreamViewModel,
    onBackClick: () -> Unit,
    onVisionRules: () -> Unit = {}
) {
    val context = LocalContext.current
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(cameraId) {
        viewModel.loadCamera(cameraId)
    }

    var exoPlayer by remember { mutableStateOf<ExoPlayer?>(null) }
    var showSettingsDialog by remember { mutableStateOf(false) }
    var showZoneEditorDialog by remember { mutableStateOf(false) }

    val owner = LocalLifecycleOwner.current
    DisposableEffect(owner, cameraId) {
        var stopped = false
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) {
                stopped = true; exoPlayer?.pause(); exoPlayer?.clearMediaItems(); viewModel.stopViewing()
            } else if (event == Lifecycle.Event.ON_START && stopped) {
                stopped = false; viewModel.loadCamera(cameraId)
            }
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer); viewModel.stopViewing() }
    }

    DisposableEffect(Unit) {
        val player = ExoPlayer.Builder(context).build().apply {
            playWhenReady = true
        }
        exoPlayer = player
        onDispose {
            player.release()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = (uiState as? StreamUiState.Success)?.camera?.name ?: "Transmisión en Vivo",
                            fontWeight = FontWeight.Bold,
                            fontSize = 18.sp
                        )
                        Text(
                            text = "Monitoreo en vivo",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    TextButton(onClick = onVisionRules) { Text("Reglas IA") }
                    IconButton(onClick = { showZoneEditorDialog = true }) {
                        Icon(Icons.Default.Polyline, contentDescription = "Zonas de Detección")
                    }
                    IconButton(onClick = { showSettingsDialog = true }) {
                        Icon(Icons.Default.Settings, contentDescription = "Ajustes de Detección")
                    }
                    IconButton(onClick = { viewModel.loadCamera(cameraId) }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Recargar Stream")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .background(MaterialTheme.colorScheme.background)
        ) {
            when (val state = uiState) {
                is StreamUiState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.height(12.dp))
                            Text("CONSULTANDO ESTADO EN SUPABASE...", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                is StreamUiState.Error -> {
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
                        Button(onClick = { viewModel.loadCamera(cameraId) }) {
                            Text("Reintentar Conexión")
                        }
                    }
                }
                is StreamUiState.Success -> {
                    val streamUrl = state.camera.hlsUrl

                    LaunchedEffect(streamUrl, state.camera.streamToken) {
                        exoPlayer?.let { player ->
                            val token = state.camera.streamToken
                            if (streamUrl.isNullOrBlank() || token.isNullOrBlank()) {
                                player.stop()
                                return@let
                            }
                            val http = DefaultHttpDataSource.Factory()
                                .setDefaultRequestProperties(mapOf("Authorization" to "Bearer $token"))
                            val mediaItem = MediaItem.fromUri(streamUrl)
                            player.setMediaSource(HlsMediaSource.Factory(http).createMediaSource(mediaItem))
                            player.prepare()
                            player.play()
                        }
                    }

                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        item {
                            VisionStatusPanel(cameraId) { preview, overlay -> viewModel.visionStatus(cameraId, preview, overlay) }
                        }
                        item {
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .aspectRatio(16f / 9f),
                                shape = RoundedCornerShape(16.dp),
                                colors = CardDefaults.cardColors(containerColor = Color.Black),
                                elevation = CardDefaults.cardElevation(defaultElevation = 8.dp)
                            ) {
                                Box(modifier = Modifier.fillMaxSize()) {
                                    AndroidView(
                                        factory = { ctx ->
                                            PlayerView(ctx).apply {
                                                player = exoPlayer
                                                useController = true
                                            }
                                        },
                                        modifier = Modifier.fillMaxSize()
                                    )

                                    Surface(
                                        color = Color.Black.copy(alpha = 0.65f),
                                        shape = RoundedCornerShape(8.dp),
                                        modifier = Modifier
                                            .padding(12.dp)
                                            .align(Alignment.TopStart)
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Box(
                                                modifier = Modifier
                                                    .size(10.dp)
                                                    .clip(CircleShape)
                                                    .background(Color(0xFF10B981))
                                            )
                                            Spacer(modifier = Modifier.width(6.dp))
                                            Text(
                                                text = "EN VIVO",
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = Color.White
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        item {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surface
                                ),
                                shape = RoundedCornerShape(16.dp)
                            ) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(20.dp)
                                ) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = "Estado de Monitoreo OpenCV",
                                            fontSize = 16.sp,
                                            fontWeight = FontWeight.Bold
                                        )

                                        val statusColor = when {
                                            state.motionEnabled && state.isScheduleActive && state.isDetectingMotion -> Color(0xFF10B981)
                                            state.motionEnabled && !state.isScheduleActive -> Color(0xFFF59E0B)
                                            else -> Color(0xFF94A3B8)
                                        }

                                        val statusText = when {
                                            state.motionEnabled && state.isScheduleActive && state.isDetectingMotion -> "MONITOREANDO"
                                            state.motionEnabled && !state.isScheduleActive -> "PAUSADO POR HORARIO"
                                            else -> "PAUSADO"
                                        }

                                        Surface(
                                            color = statusColor.copy(alpha = 0.15f),
                                            shape = RoundedCornerShape(20.dp)
                                        ) {
                                            Row(
                                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Box(
                                                    modifier = Modifier
                                                        .size(8.dp)
                                                        .clip(CircleShape)
                                                        .background(statusColor)
                                                )
                                                Spacer(modifier = Modifier.width(6.dp))
                                                Text(
                                                    text = statusText,
                                                    fontSize = 11.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = statusColor
                                                )
                                            }
                                        }
                                    }

                                    Spacer(modifier = Modifier.height(12.dp))

                                    Text(
                                        text = "Sensibilidad: Preset ${state.sensitivityPreset.uppercase()} (Área=${state.minArea}px, Umbral=${state.threshold}, Cooldown=${state.cooldownSeconds}s)",
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )

                                    Spacer(modifier = Modifier.height(4.dp))

                                    Text(
                                        text = "Programación: ${if (state.scheduleType == "24/7") "Continuo 24/7" else "Horario ${state.startTime.take(5)} - ${state.endTime.take(5)} (${state.timezone})"}",
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )

                                    Spacer(modifier = Modifier.height(16.dp))

                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                                    ) {
                                        Button(
                                            onClick = { showZoneEditorDialog = true },
                                            modifier = Modifier.weight(1f),
                                            shape = RoundedCornerShape(12.dp),
                                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                                        ) {
                                            Icon(Icons.Default.Polyline, contentDescription = null, modifier = Modifier.size(18.dp))
                                            Spacer(modifier = Modifier.width(6.dp))
                                            Text("Zonas", fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                                        }

                                        OutlinedButton(
                                            onClick = { showSettingsDialog = true },
                                            modifier = Modifier.weight(1f),
                                            shape = RoundedCornerShape(12.dp)
                                        ) {
                                            Icon(Icons.Default.Settings, contentDescription = null, modifier = Modifier.size(18.dp))
                                            Spacer(modifier = Modifier.width(6.dp))
                                            Text("Ajustes", fontSize = 13.sp)
                                        }
                                    }
                                }
                            }
                        }

                        item {
                            Text(
                                text = "Eventos recientes",
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface,
                                modifier = Modifier.padding(horizontal = 4.dp)
                            )
                        }

                        if (state.recentEvents.isEmpty()) {
                            item {
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = CardDefaults.cardColors(
                                        containerColor = MaterialTheme.colorScheme.surface
                                    ),
                                    shape = RoundedCornerShape(12.dp)
                                ) {
                                    Row(
                                        modifier = Modifier.padding(16.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.NotificationsNone,
                                            contentDescription = null,
                                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                        Spacer(modifier = Modifier.width(12.dp))
                                        Text(
                                            text = "No se han detectado eventos recientes en esta cámara.",
                                            fontSize = 13.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                        } else {
                            items(state.recentEvents.take(10)) { event ->
                                EventRowCard(event = event)
                            }
                        }
                    }

                    if (showSettingsDialog) {
                        DetectionSettingsDialog(
                            state = state,
                            onDismiss = { showSettingsDialog = false },
                            onSaveConfig = { preset, minArea, threshold, cooldown, schedType, days, startT, endT, tz ->
                                viewModel.updateMotionConfig(
                                    cameraId = cameraId,
                                    sensitivityPreset = preset,
                                    minArea = minArea,
                                    threshold = threshold,
                                    cooldownSeconds = cooldown,
                                    scheduleType = schedType,
                                    scheduleDays = days,
                                    startTime = startT,
                                    endTime = endT,
                                    timezone = tz
                                )
                                showSettingsDialog = false
                            },
                            onToggleMotion = {
                                viewModel.toggleMotionDetection(cameraId)
                            }
                        )
                    }

                    if (showZoneEditorDialog) {
                        ZoneEditorDialog(
                            cameraId = cameraId,
                            zones = state.zones,
                            onDismiss = { showZoneEditorDialog = false },
                            onSaveZone = { name, points ->
                                viewModel.addZone(cameraId, name, points)
                            },
                            onDeleteZone = { zoneId ->
                                viewModel.deleteZone(cameraId, zoneId)
                            },
                            onClearAllZones = {
                                viewModel.clearAllZones(cameraId)
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun DetectionSettingsDialog(
    state: StreamUiState.Success,
    onDismiss: () -> Unit,
    onSaveConfig: (
        preset: String,
        minArea: Int,
        threshold: Int,
        cooldown: Float,
        schedType: String,
        days: List<String>,
        startT: String,
        endT: String,
        tz: String
    ) -> Unit,
    onToggleMotion: () -> Unit
) {
    var selectedPreset by remember { mutableStateOf(state.sensitivityPreset) }
    var minAreaVal by remember { mutableIntStateOf(state.minArea) }
    var thresholdVal by remember { mutableIntStateOf(state.threshold) }
    var cooldownVal by remember { mutableFloatStateOf(state.cooldownSeconds) }

    var scheduleTypeVal by remember { mutableStateOf(state.scheduleType) }
    val selectedDays = remember { mutableStateListOf<String>().apply { addAll(state.scheduleDays) } }
    var startTimeVal by remember { mutableStateOf(state.startTime.take(5)) }
    var endTimeVal by remember { mutableStateOf(state.endTime.take(5)) }
    var timezoneVal by remember { mutableStateOf(state.timezone) }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surface
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(20.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Configuración de Sensibilidad y Horarios", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                    IconButton(onClick = onDismiss) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Cerrar")
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Estado General
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Estado del Monitoreo:", fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    Switch(
                        checked = state.motionEnabled,
                        onCheckedChange = { onToggleMotion() }
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))
                HorizontalDivider()
                Spacer(modifier = Modifier.height(16.dp))

                // Preset de Sensibilidad
                Text("Sensibilidad de Detección", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf("low" to "Baja", "medium" to "Media", "high" to "Alta", "custom" to "Pers.").forEach { (presetKey, label) ->
                        FilterChip(
                            selected = selectedPreset == presetKey,
                            onClick = {
                                selectedPreset = presetKey
                                when (presetKey) {
                                    "low" -> { minAreaVal = 3000; thresholdVal = 35; cooldownVal = 10.0f }
                                    "medium" -> { minAreaVal = 1500; thresholdVal = 25; cooldownVal = 5.0f }
                                    "high" -> { minAreaVal = 500; thresholdVal = 15; cooldownVal = 2.0f }
                                }
                            },
                            label = { Text(label, fontSize = 12.sp) }
                        )
                    }
                }

                if (selectedPreset == "custom") {
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Área Mínima: $minAreaVal px", fontSize = 12.sp)
                    Slider(
                        value = minAreaVal.toFloat(),
                        onValueChange = { minAreaVal = it.toInt() },
                        valueRange = 100f..10000f
                    )

                    Text("Umbral de Diferencia: $thresholdVal", fontSize = 12.sp)
                    Slider(
                        value = thresholdVal.toFloat(),
                        onValueChange = { thresholdVal = it.toInt() },
                        valueRange = 5f..100f
                    )

                    Text("Tiempo entre Alertas: ${cooldownVal.toInt()}s", fontSize = 12.sp)
                    Slider(
                        value = cooldownVal,
                        onValueChange = { cooldownVal = it },
                        valueRange = 1f..60f
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))
                HorizontalDivider()
                Spacer(modifier = Modifier.height(16.dp))

                // Horario de Detección
                Text("Programación de Horarios", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                Spacer(modifier = Modifier.height(8.dp))

                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(
                        selected = scheduleTypeVal == "24/7",
                        onClick = { scheduleTypeVal = "24/7" }
                    )
                    Text("Continuo 24/7", fontSize = 13.sp)

                    Spacer(modifier = Modifier.width(16.dp))

                    RadioButton(
                        selected = scheduleTypeVal == "scheduled",
                        onClick = { scheduleTypeVal = "scheduled" }
                    )
                    Text("Programado", fontSize = 13.sp)
                }

                if (scheduleTypeVal == "scheduled") {
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Días de Detección:", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    Spacer(modifier = Modifier.height(6.dp))

                    val allDays = listOf("mon" to "Lun", "tue" to "Mar", "wed" to "Mié", "thu" to "Jue", "fri" to "Vie", "sat" to "Sáb", "sun" to "Dom")
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        allDays.forEach { (dayCode, label) ->
                            val isChecked = selectedDays.contains(dayCode)
                            FilterChip(
                                selected = isChecked,
                                onClick = {
                                    if (isChecked) selectedDays.remove(dayCode) else selectedDays.add(dayCode)
                                },
                                label = { Text(label, fontSize = 10.sp) },
                                modifier = Modifier.weight(1f).padding(horizontal = 1.dp)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        OutlinedTextField(
                            value = startTimeVal,
                            onValueChange = { startTimeVal = it },
                            label = { Text("Hora Inicio (ej. 22:00)") },
                            singleLine = true,
                            modifier = Modifier.weight(1f)
                        )

                        OutlinedTextField(
                            value = endTimeVal,
                            onValueChange = { endTimeVal = it },
                            label = { Text("Hora Fin (ej. 06:00)") },
                            singleLine = true,
                            modifier = Modifier.weight(1f)
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedTextField(
                        value = timezoneVal,
                        onValueChange = { timezoneVal = it },
                        label = { Text("Zona Horaria IANA") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }

                Spacer(modifier = Modifier.height(24.dp))

                Button(
                    onClick = {
                        val sTime = if (startTimeVal.length == 5) "$startTimeVal:00" else startTimeVal
                        val eTime = if (endTimeVal.length == 5) "$endTimeVal:00" else endTimeVal
                        onSaveConfig(
                            selectedPreset,
                            minAreaVal,
                            thresholdVal,
                            cooldownVal,
                            scheduleTypeVal,
                            selectedDays.toList(),
                            sTime,
                            eTime,
                            timezoneVal
                        )
                    },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text("Guardar Configuración", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
fun ZoneEditorDialog(
    cameraId: String,
    zones: List<DetectionZone>,
    onDismiss: () -> Unit,
    onSaveZone: (name: String, points: List<NormalizedPoint>) -> Unit,
    onDeleteZone: (zoneId: String) -> Unit,
    onClearAllZones: () -> Unit
) {
    var zoneName by remember { mutableStateOf("Zona 1") }
    val draftPoints = remember { mutableStateListOf<NormalizedPoint>() }
    var containerSize by remember { mutableStateOf(IntSize.Zero) }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surface
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Configurar Zonas de Detección", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                    IconButton(onClick = onDismiss) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Cerrar")
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "Toque sobre el video para marcar los puntos del polígono (mínimo 3 puntos).",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                Spacer(modifier = Modifier.height(12.dp))

                // Interactive 16:9 Video Canvas for Polygon Zone Editing
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(16f / 9f)
                        .background(Color.Black)
                        .onGloballyPositioned { coordinates ->
                            containerSize = coordinates.size
                        }
                        .pointerInput(Unit) {
                            detectTapGestures { offset ->
                                if (containerSize.width > 0 && containerSize.height > 0) {
                                    val normX = (offset.x / containerSize.width.toFloat()).coerceIn(0f, 1f)
                                    val normY = (offset.y / containerSize.height.toFloat()).coerceIn(0f, 1f)
                                    draftPoints.add(NormalizedPoint(normX, normY))
                                }
                            }
                        }
                ) {
                    Canvas(modifier = Modifier.fillMaxSize()) {
                        val w = size.width
                        val h = size.height

                        // Render existing active zones as green shapes
                        zones.forEach { zone ->
                            if (zone.polygon.size >= 3) {
                                val path = Path().apply {
                                    val p0 = zone.polygon[0]
                                    moveTo(p0.x * w, p0.y * h)
                                    for (i in 1 until zone.polygon.size) {
                                        val p = zone.polygon[i]
                                        lineTo(p.x * w, p.y * h)
                                    }
                                    close()
                                }
                                drawPath(path, color = Color(0xFF10B981).copy(alpha = 0.25f))
                                drawPath(path, color = Color(0xFF10B981), style = Stroke(width = 3f))
                            }
                        }

                        // Render current draft polygon in amber
                        if (draftPoints.isNotEmpty()) {
                            val path = Path().apply {
                                val p0 = draftPoints[0]
                                moveTo(p0.x * w, p0.y * h)
                                for (i in 1 until draftPoints.size) {
                                    val p = draftPoints[i]
                                    lineTo(p.x * w, p.y * h)
                                }
                                if (draftPoints.size >= 3) {
                                    close()
                                }
                            }

                            if (draftPoints.size >= 3) {
                                drawPath(path, color = Color(0xFFF59E0B).copy(alpha = 0.3f))
                            }
                            drawPath(path, color = Color(0xFFF59E0B), style = Stroke(width = 4f))

                            // Draw control points as circles
                            draftPoints.forEach { pt ->
                                drawCircle(
                                    color = Color(0xFFF59E0B),
                                    radius = 12f,
                                    center = Offset(pt.x * w, pt.y * h)
                                )
                                drawCircle(
                                    color = Color.White,
                                    radius = 6f,
                                    center = Offset(pt.x * w, pt.y * h)
                                )
                            }
                        }
                    }

                    if (draftPoints.isEmpty()) {
                        Text(
                            text = "Toque aquí para dibujar los puntos de la zona",
                            color = Color.White.copy(alpha = 0.6f),
                            fontSize = 12.sp,
                            modifier = Modifier.align(Alignment.Center)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = zoneName,
                        onValueChange = { zoneName = it },
                        label = { Text("Nombre de la Zona") },
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )

                    Button(
                        onClick = {
                            if (draftPoints.size >= 3) {
                                onSaveZone(zoneName, draftPoints.toList())
                                draftPoints.clear()
                                zoneName = "Zona ${zones.size + 2}"
                            }
                        },
                        enabled = draftPoints.size >= 3,
                        modifier = Modifier.align(Alignment.CenterVertically)
                    ) {
                        Text("Guardar Zona")
                    }
                }

                if (draftPoints.isNotEmpty()) {
                    Row(
                        modifier = Modifier.padding(top = 4.dp),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Puntos marcados: ${draftPoints.size}", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.width(16.dp))
                        TextButton(onClick = { draftPoints.clear() }) {
                            Text("Limpiar Puntos", fontSize = 12.sp)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                Text("Zonas Guardadas / Opciones", fontWeight = FontWeight.Bold, fontSize = 14.sp)

                Spacer(modifier = Modifier.height(8.dp))

                OutlinedButton(
                    onClick = {
                        onClearAllZones()
                        draftPoints.clear()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.CropFree, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Detectar en toda la imagen (Restaurar sin zonas)")
                }

                Spacer(modifier = Modifier.height(8.dp))

                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(zones) { zone ->
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 12.dp, vertical = 8.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(zone.name, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                                    Text("Polígono de ${zone.polygon.size} puntos", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                IconButton(
                                    onClick = { zone.id?.let { onDeleteZone(it) } }
                                ) {
                                    Icon(Icons.Default.Delete, contentDescription = "Eliminar Zona", tint = MaterialTheme.colorScheme.error)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun EventRowCard(event: CameraEvent) {
    Card(
        modifier = Modifier.fillMaxWidth(),
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
            Surface(
                shape = CircleShape,
                color = MaterialTheme.colorScheme.error.copy(alpha = 0.15f),
                modifier = Modifier.size(38.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Alerta",
                        tint = MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = event.cameraName ?: "Cámara",
                        fontWeight = FontWeight.Bold,
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = event.detectedAt?.take(19)?.replace("T", " ") ?: "",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Spacer(modifier = Modifier.height(2.dp))

                Text(
                    text = event.description ?: "Movimiento detectado por OpenCV",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
