package com.cameramonitoring.app.ui.storage

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CleaningServices
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SdCard
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StorageManagementScreen(
    viewModel: StorageViewModel,
    onBackClick: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadStorageStats()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Gestión de Almacenamiento", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadStorageStats() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Actualizar")
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
                is StorageUiState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                    }
                }
                is StorageUiState.Error -> {
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
                        Button(onClick = { viewModel.loadStorageStats() }) {
                            Text("Reintentar")
                        }
                    }
                }
                is StorageUiState.Success -> {
                    val stats = state.stats

                    if (state.statusMessage != null) {
                        AlertDialog(
                            onDismissRequest = { viewModel.dismissStatusMessage() },
                            title = { Text("Información de Almacenamiento", fontWeight = FontWeight.Bold) },
                            text = { Text(state.statusMessage) },
                            confirmButton = {
                                TextButton(onClick = { viewModel.dismissStatusMessage() }) {
                                    Text("Entendido")
                                }
                            }
                        )
                    }

                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        // Resumen de Uso
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                        ) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(20.dp)
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = Icons.Default.SdCard,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Spacer(modifier = Modifier.width(10.dp))
                                    Text("Uso de Almacenamiento Privado", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                                }

                                Spacer(modifier = Modifier.height(16.dp))

                                Text(
                                    text = "${stats.totalStorageMb} MB Utilizados",
                                    fontSize = 24.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary
                                )

                                Spacer(modifier = Modifier.height(16.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    StorageStatBadge(
                                        icon = Icons.Default.Image,
                                        label = "Fotos",
                                        value = "${stats.photosCount}"
                                    )
                                    StorageStatBadge(
                                        icon = Icons.Default.Movie,
                                        label = "Videos MP4",
                                        value = "${stats.clipsCount}"
                                    )
                                    StorageStatBadge(
                                        icon = Icons.Default.Lock,
                                        label = "Protegidos",
                                        value = "${stats.protectedEventsCount}"
                                    )
                                }
                            }
                        }

                        // Política de Retención
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                        ) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(20.dp)
                            ) {
                                Text("Política de Retención de Evidencias", fontWeight = FontWeight.Bold, fontSize = 16.sp)

                                Spacer(modifier = Modifier.height(12.dp))

                                Text(
                                    text = "Conservar archivos de evidencia por:",
                                    fontSize = 13.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )

                                Spacer(modifier = Modifier.height(8.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    listOf(7, 15, 30, 90).forEach { days ->
                                        FilterChip(
                                            selected = stats.retentionDays == days,
                                            onClick = {
                                                viewModel.updateRetentionPolicy(
                                                    retentionDays = days,
                                                    autoCleanupEnabled = stats.autoCleanupEnabled
                                                )
                                            },
                                            label = { Text("$days días", fontSize = 12.sp) }
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(16.dp))
                                HorizontalDivider()
                                Spacer(modifier = Modifier.height(16.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text("Limpieza Periódica Automática", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                                        Text(
                                            text = "Elimina automáticamente fotos y videos vencidos que no estén protegidos.",
                                            fontSize = 12.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }

                                    Switch(
                                        checked = stats.autoCleanupEnabled,
                                        onCheckedChange = { enabled ->
                                            viewModel.updateRetentionPolicy(
                                                retentionDays = stats.retentionDays,
                                                autoCleanupEnabled = enabled
                                            )
                                        }
                                    )
                                }
                            }
                        }

                        // Acciones de Limpieza
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                        ) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(20.dp)
                            ) {
                                Text("Acciones de Limpieza Manual", fontWeight = FontWeight.Bold, fontSize = 16.sp)

                                Spacer(modifier = Modifier.height(8.dp))

                                Text(
                                    text = "Los eventos protegidos nunca se eliminan. La base de datos histórica de eventos permanece 100% intacta.",
                                    fontSize = 12.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )

                                Spacer(modifier = Modifier.height(16.dp))

                                OutlinedButton(
                                    onClick = { viewModel.runCleanup(dryRun = true) },
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(10.dp)
                                ) {
                                    Icon(Icons.Default.Folder, contentDescription = null, modifier = Modifier.size(18.dp))
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("Simular Limpieza (Dry Run)")
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                Button(
                                    onClick = { viewModel.runCleanup(dryRun = false) },
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(10.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                                ) {
                                    Icon(Icons.Default.CleaningServices, contentDescription = null, modifier = Modifier.size(18.dp))
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("Ejecutar Limpieza Manual de Vencidos")
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
fun StorageStatBadge(
    icon: ImageVector,
    label: String,
    value: String
) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(imageVector = icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
            Spacer(modifier = Modifier.height(4.dp))
            Text(value, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            Text(label, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
