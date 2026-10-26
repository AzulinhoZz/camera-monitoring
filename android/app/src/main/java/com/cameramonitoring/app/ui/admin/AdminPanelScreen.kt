package com.cameramonitoring.app.ui.admin

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.DirectionsBus
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Videocam
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
fun AdminPanelScreen(
    viewModel: AdminViewModel,
    onBackClick: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var showAddUnitDialog by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        viewModel.loadFleetData()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Administración de Flota", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadFleetData() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Actualizar")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { showAddUnitDialog = true },
                icon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text("Registrar Unidad", fontWeight = FontWeight.Bold) },
                containerColor = MaterialTheme.colorScheme.primary
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
                is AdminUiState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                    }
                }
                is AdminUiState.Error -> {
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
                        Button(onClick = { viewModel.loadFleetData() }) {
                            Text("Reintentar")
                        }
                    }
                }
                is AdminUiState.Success -> {
                    val overview = state.overview

                    if (state.statusMessage != null) {
                        AlertDialog(
                            onDismissRequest = { viewModel.dismissStatusMessage() },
                            title = { Text("Administración de Flota", fontWeight = FontWeight.Bold) },
                            text = { Text(state.statusMessage) },
                            confirmButton = {
                                TextButton(onClick = { viewModel.dismissStatusMessage() }) {
                                    Text("Entendido")
                                }
                            }
                        )
                    }

                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        item {
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
                                    Text("Resumen de Organización", fontWeight = FontWeight.Bold, fontSize = 16.sp)

                                    Spacer(modifier = Modifier.height(16.dp))

                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        AdminStatBadge(icon = Icons.Default.People, label = "Conductores", value = "${overview.driversCount}")
                                        AdminStatBadge(icon = Icons.Default.DirectionsBus, label = "Unidades", value = "${overview.unitsCount}")
                                        AdminStatBadge(icon = Icons.Default.Videocam, label = "Cámaras", value = "${overview.camerasCount}")
                                    }
                                }
                            }
                        }

                        item {
                            Text("Unidades de Transporte (Combis)", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        }

                        if (state.units.isEmpty()) {
                            item {
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                                    shape = RoundedCornerShape(12.dp)
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(24.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text("No hay unidades de transporte registradas en la flota.", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        } else {
                            items(state.units) { unit ->
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(12.dp),
                                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(16.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Icon(Icons.Default.DirectionsBus, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                                        Spacer(modifier = Modifier.width(12.dp))
                                        Column {
                                            Text("Unidad ${unit.unitNumber}", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                                            unit.plateNumber?.let { plate ->
                                                Text("Placa: $plate", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        if (showAddUnitDialog) {
            AddUnitDialog(
                onDismiss = { showAddUnitDialog = false },
                onConfirm = { unitNumber, plateNumber ->
                    viewModel.addTransportUnit(unitNumber, plateNumber)
                    showAddUnitDialog = false
                }
            )
        }
    }
}

@Composable
fun AdminStatBadge(
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

@Composable
fun AddUnitDialog(
    onDismiss: () -> Unit,
    onConfirm: (unitNumber: String, plateNumber: String?) -> Unit
) {
    var unitNumber by remember { mutableStateOf("") }
    var plateNumber by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Registrar Unidad de Transporte", fontWeight = FontWeight.Bold) },
        text = {
            Column {
                OutlinedTextField(
                    value = unitNumber,
                    onValueChange = { unitNumber = it },
                    label = { Text("Número de Económico / Unidad (ej. Combi 04)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(12.dp))
                OutlinedTextField(
                    value = plateNumber,
                    onValueChange = { plateNumber = it },
                    label = { Text("Placas de la Unidad (Opcional)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (unitNumber.isNotBlank()) {
                        onConfirm(unitNumber.trim(), if (plateNumber.isNotBlank()) plateNumber.trim() else null)
                    }
                }
            ) {
                Text("Registrar")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancelar")
            }
        }
    )
}
