# Operación de las mejoras de producto

Estos comandos preparan o verifican artefactos; no autorizan producción. Ejecutar desde la raíz del repositorio en un entorno de desarrollo aislado. La candidata conserva NO_GO: [entrega y límites](PHASE_7_PRODUCT_DELIVERY.md). No usar el proyecto configurado como staging hasta que su operador lo identifique explícitamente así.

## Android

JDK25, SDK35, build-tools36; wrapper Gradle fijado. No introducir claves Supabase/Firebase de servidor en el APK ni en las propiedades Gradle.

```bash
cd android
bash gradlew :app:testDebugUnitTest :app:assembleDebug
bash gradlew :app:validateReleaseEndpoint -PcameraApiBaseUrl=https://api.example.invalid/
```

La URL de ejemplo solo verifica formato y no es un servicio operativo. Para una compilación destinada a un entorno autorizado, pasar `-PcameraApiBaseUrl=https://HOST_AUTORIZADO/` a la tarea de build. Se requiere barra final, sin credenciales, query ni fragmento. Release exige HTTPS y tiene `usesCleartextTraffic=false`; debug admite desarrollo local. El debug predeterminado `http://10.0.2.2:8000/` funciona desde emulador hacia el host, no representa un endpoint accesible desde teléfono. Un teléfono requiere una URL real y conectividad al entorno autorizado. HTTPS sintáctico no garantiza cadena TLS, identidad del servicio o acceso por usuario.

El dashboard muestra pendientes de las últimas24h. Si la API informa respuesta incompleta, una cámara ausente tiene conteo desconocido. El acceso directo conserva cámara/estado/ventana. En historial, fecha/hora se interpreta en zona del teléfono, se convierte a UTC y se incluye todo el minuto final; ventana máxima31 días. Horas DST ambiguas/inexistentes se rechazan, no se elige un offset silenciosamente. Cambiar cámara elimina una regla incompatible; el chip permite retirar un filtro de una regla ya eliminada. Un error de compatibilidad de `applied_filters` exige actualizar API antes de usar ese filtro.

Al abrir evidencia se solicita autorización vigente. No recuperar una URL antigua frente a un fallo de autorización; el usuario puede reintentar. La desactivación de caché Coil protege las miniaturas privadas en esa biblioteca, sin afirmar ausencia universal de buffers/cachés del sistema o del reproductor. Verificar reproducción, navegación/background y caducidad en dispositivo mediante la matriz pendiente.

Inventario y gate (requieren generar `resolved.json` con la tarea Gradle ya usada en CI):

```bash
bash android/gradlew -p android :app:exportPhase6Inventory -I android/gradle/release-inventory.gradle -PreleaseInventoryOutput=/tmp/camera-resolved.json --no-configuration-cache
python backend/scripts/android_inventory.py --resolved /tmp/camera-resolved.json --apk android/app/build/outputs/apk/debug/app-debug.apk --pom-cache "$HOME/.gradle/caches/modules-2/files-2.1" --output /tmp/camera-android-inventory
python backend/scripts/scan_android_dependencies.py --sbom /tmp/camera-android-inventory/android.cdx.json --inventory /tmp/camera-android-inventory/android-inventory.json --apk android/app/build/outputs/apk/debug/app-debug.apk --cache /tmp/camera-android-scan-cache --output /tmp/camera-android-scan
```

La resolución puede consultar repositorios públicos de dependencias; no necesita secretos de aplicación. El scanner revisado fija versión/hash y valida DB reciente. El gate cubre matches Maven; las `.so` solo se inventarían, sin certificarlas. Comprobar `apk_sha256` y no trasladar un resultado limpio a otro APK.

## Índices de eventos

`012_event_query_indexes.sql` es aditiva. Requiere esquema/migraciones anteriores y conexión privada proporcionada por el operador, nunca claves en chat/commits. Usar `psql` con autocommit y `ON_ERROR_STOP`; **no** `--single-transaction`, `BEGIN` o migrador que envuelva todo el archivo en una transacción. Revisar espacio/IO, índices existentes y ventana de operación antes de ejecutarla en un entorno autorizado.

Después, comprobar `pg_index.indisvalid/indisready` para `idx_camera_events_camera_timeline_v1`, `idx_camera_events_pending_window_v1` y `idx_camera_events_rule_window_v1`. El archivo falla si no están listos/válidos; `IF NOT EXISTS` no repara un índice inválido de un intento interrumpido. Inspeccionarlo y planificar retirar/recrear únicamente el índice propio que corresponda; no borrar índices de terceros para forzar un PASS. El rollback `backend/migrations/rollback/012_event_query_indexes.sql` elimina solo esos tres índices concurrentemente y conserva filas. No aplicar rollback011 por una reversión de012.

Validación local segura usada en esta entrega:

```bash
SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= python backend/scripts/validate_database_security.py
```

El script utiliza PostgreSQL desechable con datos generados; no sustituye drift, PostgREST ni Storage del servicio administrado.

## Respaldo cifrado offline y restauración

`encrypted_backup.py` es una herramienta Linux para **exports ya consistentes preparados por el operador**. No exporta Supabase ni obtiene snapshots coherentes por sí sola. Requiere `cryptography` fijado por las dependencias del repositorio y `renameat2(RENAME_NOREPLACE)`; no tiene fallback que sobrescriba destinos.

Ejemplo de laboratorio: crear directorios privados propios, fuera del repositorio; colocar únicamente exports autorizados en `source`. No ejecutar sobre datos activos ni copiar claves dentro de `source`.

```bash
install -d -m 700 /tmp/camera-backup-lab
install -d -m 700 /tmp/camera-backup-lab/keys /tmp/camera-backup-lab/source /tmp/camera-backup-lab/archives /tmp/camera-backup-lab/restores
python backend/scripts/encrypted_backup.py generate-key --key-file /tmp/camera-backup-lab/keys/export.key
python backend/scripts/encrypted_backup.py encrypt --source /tmp/camera-backup-lab/source --key-file /tmp/camera-backup-lab/keys/export.key --archive /tmp/camera-backup-lab/archives/export.enc
python backend/scripts/encrypted_backup.py restore --archive /tmp/camera-backup-lab/archives/export.enc --key-file /tmp/camera-backup-lab/keys/export.key --destination /tmp/camera-backup-lab/restores/recovered
```

El ejemplo necesita archivos en `source`; vacío falla intencionalmente. La clave es32 bytes generados aleatoriamente, archivo0600, directorio0700 del usuario. No se imprime. Generar otra sobre el mismo path o restaurar sobre un destino existente falla; elegir paths nuevos. Clave y archive deben estar fuera de la fuente. Límite100GiB/100000 archivos; rechaza symlinks y archivos especiales. AES-256-GCM autentica completamente antes de parsear/extraer tar; paths absolutos/traversal y miembros no regulares se rechazan. Se procesa en streaming y puede necesitar espacio temporal para el tar autenticado y contenido extraído. Entorno local y fuente deben ser de confianza y no cambiar durante el export.

Conservar **la clave exacta** separada del bundle, en custodia operativa aprobada; perderla hace irrecuperable el respaldo. La clave local fixture retenida solo demuestra recuperación entre procesos. Faltan política de KMS/escrow, rotación, separación de funciones, retención de bundles, copia fuera de sitio y simulacro con recuperación administrada de DB+Storage, RPO/RTO acordados. El tiempo de la fixture no es un RTO operativo. No subir keys, bundles ni exports reales a Git o artefactos CI.

## Evaluación de alertas

```bash
python backend/scripts/evaluate_alert_quality.py --input backend/app/tests/fixtures/alert-quality.synthetic.json --threshold 0.5 --output /tmp/camera-quality.json
```

La fixture es un esquema reproducible de timestamps, no vídeos naturales. Para datos reales: derechos/consentimiento aplicables, `dataset_kind=authorized_video_annotations`, `rights_reference`, SHA256 del vídeo y secuencias con duración, escenario, ventanas esperadas y predicciones temporales/tipo/confianza. Ver esquema validado en el script y su fixture; conservar los vídeos privados fuera del repositorio. Ventanas del mismo tipo en una secuencia no se solapan; cada esperado admite una sola predicción; duplicados y alertas fuera de ventana son FP. Valores indefinidos se reportan `null`, no100%.

Separar vídeos de `calibration` y `test` antes de elegir umbral/cooldown; el programa no impide que un operador reutilice indebidamente los mismos vídeos entre archivos. Solo calibración genera curva; congelar configuración y evaluar test sin retocar por sus resultados. Medir día/noche/lluvia/mascotas/sombras/oclusiones y negativos representativos. El programa compara salidas suministradas: falta ejecutar y enlazar inferencia con vídeos reales, revisar etiquetas y reportar resultados independientes por regla/escenario. No cambia configuración ni habilita alertas.

## Capacidad y diagnóstico

```bash
python backend/scripts/download_vision_model.py --output /tmp/camera-yolox.onnx
SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= python backend/scripts/benchmark_vision.py --model /tmp/camera-yolox.onnx --inference-fps 3 --memory-mib 1024 > /tmp/camera-shared-benchmark.json
python backend/scripts/benchmark_fleet_capacity.py --model /tmp/camera-yolox.onnx --duration 12 --output /tmp/camera-fleet-benchmark
```

El downloader y benchmark verifican identidad del modelo revisado. El benchmark de fleet usa grupos aislados, un CPU y512MiB presupuestados por cámara, aplica admisión y ejecuta1/2/4 solo si el host lo permite. Son frames sintéticos sin acceso remoto; poses OFF. No confundir memoria sumada de grupos con memoria del detector compartido. Para aceptación, repetir en hardware objetivo con RTSP/substreams autorizados, concurrencia prevista, evidencia/grabación y una prueba sostenida. Incluir reconexiones, saturación, red, almacenamiento y latencia, no solo FPS.

`VISION_MIN_EFFECTIVE_FPS` configura umbral técnico0.1..60, default2; no es una garantía de capacidad. `capture_unavailable`, `frame_stale`, `inference_not_ready`, `inference_below_target` requieren investigar fuente/modelo/carga. `inference_drops_observed` recuerda descartes acumulados y es informativo; no clasifica personas ni produce incidentes/FCM. El panel muestra detalles técnicos bajo acción explícita.

## Gate de entrega

```bash
python backend/scripts/check_release_readiness.py --manifest docs/ai-vision/PRODUCT_ACCEPTANCE_MANIFEST.json
```

Resultado esperado actual: exit1, **NO_GO**, `deploy_authorized=false`. Los recibos tienen caducidad; un manifiesto editado no es firma ni aprobación. Corregir realmente runtime nativo y actualizar artefacto/scan, completar aceptación externa y revisión del operador antes de cualquier solicitud de despliegue.
