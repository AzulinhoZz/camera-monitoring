package com.cameramonitoring.app.ui.vision

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import com.cameramonitoring.app.data.model.*
import com.cameramonitoring.app.data.remote.ApiService
import kotlinx.coroutines.launch
import java.util.UUID

private val kinds = linkedMapOf("intrusion" to "Intrusión", "dwell" to "Permanencia",
    "line_crossing" to "Cruce de línea", "count" to "Conteo",
    "probable_abandoned_object" to "Posible objeto abandonado")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisionRulesScreen(cameraId: String, api: ApiService, onBack: () -> Unit) {
    val coroutine = rememberCoroutineScope()
    var config by remember(cameraId) { mutableStateOf<VisionConfig?>(null) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var draft by remember { mutableStateOf<VisionRule?>(null) }
    suspend fun reload() {
        busy = true
        try {
            val response = api.getVisionRules(cameraId)
            if (response.isSuccessful) config = response.body()
            else message = "No se pudieron cargar las reglas (${response.code()})."
        } catch (_: Exception) { message = "No se pudo conectar. Reintenta." }
        finally { busy = false }
    }
    fun save(rules: List<VisionRule>) {
        val current = config ?: return
        coroutine.launch {
            busy = true
            try {
                val response = api.saveVisionRules(cameraId, VisionConfigUpdate(current.revision, rules))
                if (response.isSuccessful) {
                    config = response.body(); draft = null; message = "Reglas guardadas."
                } else message = when (response.code()) {
                    409 -> "Otro cambio fue guardado. Recarga y revisa antes de guardar."
                    403 -> "No tienes permiso para editar esta cámara."
                    422 -> "Comprueba los puntos, clases, límites y horario de la regla."
                    else -> "No se pudo guardar (${response.code()})."
                }
            } catch (_: Exception) { message = "No se pudo guardar. Recarga para comprobar el estado." }
            finally { busy = false }
        }
    }
    LaunchedEffect(cameraId) { reload() }
    Scaffold(topBar = { TopAppBar(title = { Text("Reglas de visión") },
        navigationIcon = { TextButton(onClick = onBack) { Text("Volver") } }) }) { padding ->
        Column(Modifier.padding(padding).padding(16.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Las detecciones requieren revisión humana. Un objeto estacionario no demuestra abandono.")
            Text("Guardar reglas no inicia el análisis de la cámara. Su activación se administra en el servidor.")
            message?.let { Text(it) }
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            OutlinedButton(onClick = { coroutine.launch { reload() } }, enabled = !busy) { Text("Recargar") }
            config?.let { current ->
                current.rules.forEach { rule ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp)) {
                            Text("${kinds[rule.kind] ?: rule.kind} · ${if (rule.enabled) "Activada" else "Desactivada"}")
                            Text(rule.classes.joinToString())
                            if (current.canManage) Row {
                                TextButton(onClick = { draft = rule }, enabled = !busy) { Text("Editar") }
                                TextButton(onClick = { save(current.rules.filter { it.ruleId != rule.ruleId }) }, enabled = !busy) { Text("Eliminar") }
                            }
                        }
                    }
                }
                if (current.canManage && draft == null) Button(
                    onClick = { draft = VisionRule(UUID.randomUUID().toString()) },
                    enabled = !busy && current.rules.size < 32) { Text("Añadir regla") }
                if (!current.canManage) Text("Acceso de lectura. Solo el propietario o administrador puede editar.")
                draft?.let { rule ->
                    key(rule.ruleId) {
                        RuleEditor(rule, !busy, onCancel = { draft = null }, onSave = { edited ->
                            save(current.rules.filter { it.ruleId != edited.ruleId } + edited)
                        })
                    }
                }
            }
        }
    }
}

@Composable
private fun RuleEditor(initial: VisionRule, editable: Boolean, onCancel: () -> Unit, onSave: (VisionRule) -> Unit) {
    var kind by remember { mutableStateOf(initial.kind) }
    var enabled by remember { mutableStateOf(initial.enabled) }
    var classes by remember { mutableStateOf(initial.classes.joinToString(",")) }
    var points by remember { mutableStateOf(if (initial.kind == "line_crossing") initial.line.orEmpty() else initial.polygon) }
    var duration by remember { mutableStateOf(initial.durationSeconds.toString()) }
    var cooldown by remember { mutableStateOf(initial.cooldownSeconds.toString()) }
    var confidence by remember { mutableStateOf(initial.minConfidence.toString()) }
    var observations by remember { mutableStateOf(initial.minObservations.toString()) }
    var margin by remember { mutableStateOf(initial.lineMargin.toString()) }
    var threshold by remember { mutableStateOf(initial.threshold.toString()) }
    var radius by remember { mutableStateOf(initial.stationaryRadius.toString()) }
    var direction by remember { mutableStateOf(initial.direction) }
    var zone by remember { mutableStateOf(initial.timezoneName) }
    var start by remember { mutableStateOf(initial.start) }
    var end by remember { mutableStateOf(initial.end) }
    var days by remember { mutableStateOf(initial.weekdays) }
    var error by remember { mutableStateOf<String?>(null) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Tipo de regla")
        kinds.forEach { (value, label) -> FilterChip(selected = kind == value, enabled = editable,
            onClick = { if (kind != value) { kind = value; points = emptyList() } }, label = { Text(label) }) }
        Row { Switch(checked = enabled, onCheckedChange = { enabled = it }, enabled = editable); Text(" Activada") }
        Text("Toca el plano para marcar ${if (kind == "line_crossing") "dos extremos" else "3 a 32 vértices"}. Arriba corresponde a la parte superior de la imagen completa, sin recorte.")
        // Explicit coordinate plan, not a fake live image. Geometry is normalized.
        Canvas(Modifier.fillMaxWidth().aspectRatio(16f/9f).background(Color(0xFF17212B))
            .pointerInput(kind, points, editable) {
                detectTapGestures { p ->
                    if (editable && points.size < (if (kind == "line_crossing") 2 else 32))
                        points = points + NormalizedPoint((p.x/size.width).coerceIn(0f,1f), (p.y/size.height).coerceIn(0f,1f))
                }
            }) {
            for (i in 1..3) {
                drawLine(Color.Gray, Offset(size.width*i/4,0f), Offset(size.width*i/4,size.height))
                drawLine(Color.Gray, Offset(0f,size.height*i/4), Offset(size.width,size.height*i/4))
            }
            if (points.isNotEmpty()) {
                val path = Path().apply {
                    moveTo(points[0].x*size.width,points[0].y*size.height)
                    points.drop(1).forEach { lineTo(it.x*size.width,it.y*size.height) }
                    if (kind != "line_crossing" && points.size >= 3) close()
                }
                drawPath(path,Color.Yellow,style = Stroke(4f))
                points.forEach { drawCircle(Color.White,6f,Offset(it.x*size.width,it.y*size.height)) }
            }
        }
        Text("Plano de coordenadas: ${points.size} puntos. No es una vista de la cámara.")
        TextButton(onClick = { points = emptyList() }, enabled = editable) { Text("Borrar puntos") }
        OutlinedTextField(classes, { classes = it }, label = { Text("Clases: person, car, backpack…") }, enabled = editable)
        OutlinedTextField(confidence, { confidence = it }, label = { Text("Confianza mínima (0.01 a 1)") }, enabled = editable)
        OutlinedTextField(observations, { observations = it }, label = { Text("Observaciones consecutivas mínimas") }, enabled = editable)
        OutlinedTextField(margin, { margin = it }, label = { Text("Margen contra oscilación de línea (0 a 0.1)") }, enabled = editable)
        OutlinedTextField(duration, { duration = it }, label = { Text("Permanencia / estacionario (segundos)") }, enabled = editable)
        OutlinedTextField(cooldown, { cooldown = it }, label = { Text("Intervalo mínimo entre eventos (segundos)") }, enabled = editable)
        OutlinedTextField(threshold, { threshold = it }, label = { Text("Umbral de objetos visibles") }, enabled = editable)
        OutlinedTextField(radius, { radius = it }, label = { Text("Tolerancia estacionaria (0.001 a 0.2)") }, enabled = editable)
        if (kind == "line_crossing") {
            Text("Dirección respecto al orden de los extremos, con eje Y hacia abajo:")
            listOf("both" to "Ambas", "positive" to "Hacia lado positivo", "negative" to "Hacia lado negativo").forEach { (v,l) ->
                FilterChip(selected = direction == v, onClick = { direction = v }, enabled = editable, label = { Text(l) })
            }
        }
        OutlinedTextField(zone, { zone = it }, label = { Text("Zona horaria, p. ej. America/Mexico_City") }, enabled = editable)
        OutlinedTextField(start, { start = it }, label = { Text("Inicio HH:mm:ss") }, enabled = editable)
        OutlinedTextField(end, { end = it }, label = { Text("Fin HH:mm:ss") }, enabled = editable)
        Text("Días de inicio (las ventanas nocturnas continúan al día siguiente)")
        listOf("Lun","Mar","Mié","Jue","Vie","Sáb","Dom").forEachIndexed { index, label ->
            FilterChip(selected = index in days, enabled = editable, onClick = {
                days = if (index in days) days - index else days + index
            }, label = { Text(label) })
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(enabled = editable, onClick = {
            val confidenceValue = confidence.toDoubleOrNull(); val observationsValue = observations.toIntOrNull(); val marginValue = margin.toDoubleOrNull()
            val d = duration.toDoubleOrNull(); val c = cooldown.toDoubleOrNull()
            val t = threshold.toIntOrNull(); val r = radius.toDoubleOrNull()
            val labels = classes.split(",").map { it.trim() }.filter { it.isNotEmpty() }
            val validTimes = runCatching { java.time.LocalTime.parse(start); java.time.LocalTime.parse(end); java.time.ZoneId.of(zone) }.isSuccess
            if (confidenceValue == null || confidenceValue !in 0.01..1.0 || observationsValue == null || observationsValue !in 1..60 || marginValue == null || marginValue !in 0.0..0.1 || d == null || d !in 1.0..86400.0 || c == null || c !in 0.0..86400.0 || t == null || t !in 1..100 || r == null || r !in 0.001..0.2 || labels.isEmpty() || days.isEmpty() || !validTimes ||
                (if (kind == "line_crossing") points.size != 2 else points.size < 3)) {
                error = "Revisa geometría, clases, valores y horario."
            } else {
                onSave(initial.copy(kind = kind, enabled = enabled, classes = labels,
                    polygon = if (kind == "line_crossing") emptyList() else points,
                    line = if (kind == "line_crossing") points else null,
                    durationSeconds = d, cooldownSeconds = c, threshold = t, stationaryRadius = r,
                    minConfidence = confidenceValue, minObservations = observationsValue, lineMargin = marginValue,
                    direction = direction, timezoneName = zone, weekdays = days.sorted(), start = start, end = end))
            }
        }) { Text("Guardar regla") }
        TextButton(onClick = onCancel, enabled = editable) { Text("Cancelar") }
    }
}
