package com.cameramonitoring.app.ui.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cameramonitoring.app.data.model.Camera

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel,
    userFullName: String,
    userEmail: String,
    onAddCameraClick: () -> Unit,
    onCameraSelect: (String) -> Unit,
    onEventsClick: () -> Unit,
    onStorageClick: () -> Unit,
    onAccountClick: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    var editingCamera by remember { mutableStateOf<Camera?>(null) }
    var deletingCamera by remember { mutableStateOf<Camera?>(null) }

    LaunchedEffect(Unit) {
        viewModel.loadCameras()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "Hola, $userFullName",
                            fontWeight = FontWeight.Bold,
                            fontSize = 18.sp
                        )
                        Text(
                            text = "Mis cámaras de seguridad",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadCameras() }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Actualizar listado"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        },
        bottomBar = {
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.surface
            ) {
                NavigationBarItem(
                    selected = true,
                    onClick = { },
                    icon = { Icon(Icons.Default.Videocam, contentDescription = null) },
                    label = { Text("Mis cámaras", fontSize = 11.sp) }
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onEventsClick,
                    icon = { Icon(Icons.Default.Notifications, contentDescription = null) },
                    label = { Text("Alertas", fontSize = 11.sp) }
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onStorageClick,
                    icon = { Icon(Icons.Default.SdCard, contentDescription = null) },
                    label = { Text("Fotos/Clips", fontSize = 11.sp) }
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onAccountClick,
                    icon = { Icon(Icons.Default.Person, contentDescription = null) },
                    label = { Text("Mi cuenta", fontSize = 11.sp) }
                )
            }
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onAddCameraClick,
                icon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text("Agregar cámara", fontWeight = FontWeight.Bold) },
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = Color.White
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
                is DashboardUiState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                    }
                }
                is DashboardUiState.Error -> {
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
                        Button(onClick = { viewModel.loadCameras() }) {
                            Text("Reintentar")
                        }
                    }
                }
                is DashboardUiState.Success -> {
                    if (state.actionError != null) {
                        AlertDialog(
                            onDismissRequest = { viewModel.dismissActionError() },
                            title = { Text("Error de Operación", fontWeight = FontWeight.Bold) },
                            text = { Text(state.actionError) },
                            confirmButton = {
                                TextButton(onClick = { viewModel.dismissActionError() }) {
                                    Text("Entendido")
                                }
                            }
                        )
                    }

                    if (state.cameras.isEmpty()) {
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(32.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center
                        ) {
                            Surface(
                                shape = CircleShape,
                                color = MaterialTheme.colorScheme.surfaceVariant,
                                modifier = Modifier.size(80.dp)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(
                                        imageVector = Icons.Default.VideocamOff,
                                        contentDescription = "Sin cámaras",
                                        modifier = Modifier.size(40.dp),
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = "No hay cámaras registradas",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "Toque el botón + para agregar su primera cámara.",
                                fontSize = 14.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    } else {
                        val connectedCount = state.cameras.count { it.status.lowercase() == "online" }

                        LazyColumn(
                            contentPadding = PaddingValues(16.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                            modifier = Modifier.fillMaxSize()
                        ) {
                            item {
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                                    shape = RoundedCornerShape(14.dp)
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(16.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column {
                                            Text("Resumen de la Unidad", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                                            Text("${state.cameras.size} cámara(s) registrada(s)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }

                                        Surface(
                                            color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.15f),
                                            shape = RoundedCornerShape(20.dp)
                                        ) {
                                            Text(
                                                text = "$connectedCount Conectada(s)",
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = MaterialTheme.colorScheme.secondary,
                                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                                            )
                                        }
                                    }
                                }
                            }

                            items(state.cameras) { camera ->
                                CameraCardItem(
                                    camera = camera,
                                    onPlayClick = { onCameraSelect(camera.id) },
                                    onCheckConnectionClick = { viewModel.checkCameraConnection(camera.id) },
                                    onEditClick = { editingCamera = camera },
                                    onDeleteClick = { deletingCamera = camera }
                                )
                            }
                        }
                    }
                }
            }
        }

        // Edit Camera Dialog
        editingCamera?.let { camera ->
            EditCameraDialog(
                camera = camera,
                onDismiss = { editingCamera = null },
                onConfirm = { newName, newRtspUrl ->
                    viewModel.updateCamera(camera.id, newName, newRtspUrl)
                    editingCamera = null
                }
            )
        }

        // Confirm Delete Dialog
        deletingCamera?.let { camera ->
            ConfirmDeleteDialog(
                camera = camera,
                onDismiss = { deletingCamera = null },
                onConfirm = {
                    viewModel.deleteCamera(camera.id)
                    deletingCamera = null
                }
            )
        }
    }
}

@Composable
fun CameraCardItem(
    camera: Camera,
    onPlayClick: () -> Unit,
    onCheckConnectionClick: () -> Unit,
    onEditClick: () -> Unit,
    onDeleteClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Surface(
                        shape = RoundedCornerShape(10.dp),
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                        modifier = Modifier.size(44.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = Icons.Default.Videocam,
                                contentDescription = "Camera Icon",
                                tint = MaterialTheme.colorScheme.primary
                            )
                        }
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Column {
                        Text(
                            text = camera.name,
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            text = camera.rtspUrl,
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }

                Row {
                    IconButton(onClick = onCheckConnectionClick) {
                        Icon(
                            imageVector = Icons.Default.Sync,
                            contentDescription = "Verificar conexión",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    IconButton(onClick = onEditClick) {
                        Icon(
                            imageVector = Icons.Default.Edit,
                            contentDescription = "Editar cámara",
                            tint = MaterialTheme.colorScheme.primary
                        )
                    }
                    IconButton(onClick = onDeleteClick) {
                        Icon(
                            imageVector = Icons.Default.Delete,
                            contentDescription = "Eliminar cámara",
                            tint = MaterialTheme.colorScheme.error
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            val isOnline = camera.status.lowercase() == "online"
            val statusColor = if (isOnline) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.error
            val statusText = if (isOnline) "Conectada" else "Sin conexión"

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(10.dp)
                                .clip(CircleShape)
                                .background(statusColor)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = statusText,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = statusColor
                        )
                    }
                    if (camera.lastSeenAt != null) {
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = "Última conexión: ${camera.lastSeenAt.take(19).replace("T", " ")}",
                            fontSize = 10.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Button(
                    onClick = onPlayClick,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.PlayArrow,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Ver cámara", fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
fun EditCameraDialog(
    camera: Camera,
    onDismiss: () -> Unit,
    onConfirm: (name: String, rtspUrl: String) -> Unit
) {
    var name by remember { mutableStateOf(camera.name) }
    var rtspUrl by remember { mutableStateOf(camera.rtspUrl) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Configurar Cámara", fontWeight = FontWeight.Bold) },
        text = {
            Column {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it; errorMessage = null },
                    label = { Text("Nombre de la Cámara") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp)
                )
                Spacer(modifier = Modifier.height(12.dp))
                OutlinedTextField(
                    value = rtspUrl,
                    onValueChange = { rtspUrl = it; errorMessage = null },
                    label = { Text("Dirección de la cámara (RTSP)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp)
                )
                if (errorMessage != null) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = errorMessage!!,
                        color = MaterialTheme.colorScheme.error,
                        fontSize = 12.sp
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val trimmedName = name.trim()
                    val trimmedUrl = rtspUrl.trim()
                    if (trimmedName.isBlank()) {
                        errorMessage = "Ingrese un nombre válido"
                        return@Button
                    }
                    if (trimmedUrl.isBlank() || (!trimmedUrl.startsWith("rtsp://") && !trimmedUrl.startsWith("rtsps://"))) {
                        errorMessage = "Ingrese una dirección RTSP válida (ej. rtsp://...)"
                        return@Button
                    }
                    onConfirm(trimmedName, trimmedUrl)
                }
            ) {
                Text("Guardar Cambios")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancelar")
            }
        }
    )
}

@Composable
fun ConfirmDeleteDialog(
    camera: Camera,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("¿Eliminar cámara?", fontWeight = FontWeight.Bold) },
        text = {
            Text("¿Está seguro de que desea eliminar '${camera.name}'? Se detendrá la vigilancia de movimiento asociada.")
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error
                )
            ) {
                Text("Eliminar")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancelar")
            }
        }
    )
}
