# Fase 3 — reglas y evidencias

Fecha: 2026-10-27 (America/Mexico_City). Rama: `feat/ai-vision-platform`.
Estado: implementación funcional de fase 3 terminada; validación de laboratorio descrita abajo. Sin despliegue, migración remota, merge ni fase 4. La validación semántica con vídeos reales y la aceptación operativa siguen siendo puertas de release, no resultados demostrados.

## Inventario y decisiones antes de la integración

| Área | Estado previo comprobado | Integración |
|---|---|---|
| Objetos / tracking | YOLOX CPU, IoU temporal, contrato v1 | Se conserva; sin identidad ni tracking entre cámaras |
| Zonas de movimiento | `zone_store.py`, rutas de `main.py`, migración 004 | Se conservan; las reglas de objetos son configuración separada |
| Horarios | `schedule_evaluator.py`, migración 007 | No se altera movimiento; reglas validan IANA/días/ventanas nocturnas |
| Eventos y revisión | `events.py`, `camera_events`, migración 009 | Mismas rutas y tabla; metadata de visión y resumen limitado |
| Evidencias | `evidence_uploader.py`, `clip_recorder.py`, 005/006 | Mismos buckets privados y encoder compartido; buffer acotado para el worker desacoplado |
| Protección / retención | `retention_manager.py`, `storage.py`, 008 | Mismos campos y lógica, ejercitados con evento de visión en PostgreSQL desechable |
| Persistencia de reglas | Faltaba | 011: configuración versionada por cámara, sin fallback a JSON local |
| API / UI de reglas | Faltaba | GET/PUT autenticados; editor Android y navegación desde transmisión |
| Riesgos previos | Android sin compilar, egress RTSP, ausencia de vídeo anotado | Toolchain preparado para validar build; otros límites siguen explícitos |

Se leyeron el plan maestro, código actual, pruebas y migraciones canónicas. No se duplican tablas de eventos, buckets, grabadores RTSP, protección ni políticas de retención. No se añaden dependencias Python/Android, modelos ni pesos. El JDK/SDK de validación vive en `/tmp`, no se incorpora a la aplicación.

## Reglas, horarios y falsos positivos

`backend/app/vision/rules.py` implementa polígonos simples de 3–32 vértices normalizados y líneas finitas orientadas. El punto usado es el centro de la caja. El borde del polígono está dentro. Dirección positiva/negativa usa producto cruzado respecto al orden de extremos, con Y hacia abajo en la imagen.

Reglas: intrusión, permanencia, cruce de línea, umbral de objetos visibles y **posible objeto abandonado**. Esta última detecta solamente centro estacionario durante un intervalo; no identifica propietario, demuestra abandono ni infiere delito. Se rechaza person en esa regla. Todos los eventos nacen pending y requieren revisión humana.

Cada regla tiene clases COCO válidas, confianza mínima, observaciones consecutivas, duración, cooldown, radio estacionario y margen de línea contra oscilación. El detector incluye las clases de las reglas habilitadas, manteniendo las configuradas por operador. La confianza de una regla no reduce el umbral global del detector. El formulario nuevo recomienda dos observaciones; el contrato conserva una como default para compatibilidad con el primer incremento.

La entrada inicial en zona puede disparar intrusión tras las observaciones requeridas. Permanencia/estacionariedad emite una vez por episodio; salida, ausencia o movimiento reinicia según tipo. Conteo emite al alcanzar el umbral desde abajo y cuenta tracks visibles, no personas únicas. Frames vacíos eliminan ausentes; huecos mayores de dos segundos reinician continuidad. Por ello un FPS insuficiente puede impedir confirmación temporal, en lugar de inventar continuidad.

Horarios IANA; 0=lunes y 6=domingo. La parte posterior a medianoche de una ventana nocturna pertenece al día de inicio. Cooldown por regla/cámara limita volumen y persiste en DB; no es por persona. La línea conserva el último lado fuera del margen. Estos filtros no sustituyen medir precisión, oclusión, cambios de ID y falsos positivos en secuencias permitidas.

## Configuración, permisos y concurrencia

`backend/app/vision_api.py`:

- `GET /cameras/{uuid}/vision-rules`: usuario con acceso efectivo, incluye can_manage.
- `PUT /cameras/{uuid}/vision-rules`: propietario o administrador de la organización vigente. Sustituye la lista completa; lista vacía elimina reglas. revision obligatorio evita sobrescribir cambios ajenos (409, recargar).
- El body de regla contiene rule_id y parámetros funcionales; **rechaza camera_id/owner_id/organization_id**. El servidor deriva scope de DB, valida geometría/horarios/clases y unicidad de IDs.
- Errores sin excepciones/credenciales en respuesta; DB ausente/migración pendiente da 503, sin guardar localmente.

Migración `backend/migrations/011_vision_rules_and_events.sql`: tabla camera_vision_configs, RLS SELECT correlacionado con cámaras visibles y scope vigente; authenticated/anon sin escritura directa. RPCs de escritura disponibles exclusivamente a service_role. save_vision_config vuelve a comprobar actor, rol y organización en la transacción, bloquea perfiles/cámara/configuración e incrementa revisión. Un traslado de cámara oculta reglas anteriores; se mantiene revisión para una edición deliberada en el nuevo ámbito.

Los eventos usan camera_events con vision_metadata nullable; el tipo es vision_<regla>. ingest_vision_event verifica scope actual, revisión, regla habilitada/tipo y timestamp fresco (hasta cinco minutos de antigüedad, treinta segundos futuros). Serializa por configuración, deduplica event_id y aplica cooldown durable incluso tras reiniciar sesión. Replays no modifican revisiones humanas ni protección. Cambiar configuración conserva cooldowns de las reglas retenidas si scope no cambia y elimina las claves retiradas (máximo 32); cambiar scope los reinicia.

`RULE_EVENT_V1.schema.json` documenta el contrato interno separado del DetectionEvent v1 existente. Los IDs de track son temporales y solo tienen significado junto a camera_id/session_id. No hay endpoint de ingestión público ni escritura de eventos arbitrarios desde la app.

## Worker y evidencia

`backend/app/vision/__main__.py` incorpora `--persist-events`, desactivado por defecto y condicionado a `--resolve-scopes`. Carga reglas desde DB y refresca revisiones en cada intervalo de métricas. Cambios de source/scope o DB inaccesible detienen captura; una revisión obsoleta se rechaza también en DB antes de persistir. Sin ese flag, el comportamiento anterior sigue sin escrituras. La cámara requiere vision_enabled y modelo auditado del operador: la app no inicia análisis por guardar una regla.

`persistence.py` valida contrato/scope; `evidence.py` consume el carril recording existente sin nueva conexión RTSP. Reutiliza FrameRingBuffer y el encoder `encode_clip_frames` extraído de clip_recorder.py, manteniendo sus interfaces y pruebas legacy.

Límites: una evidencia pendiente por cámara, 10 frames previos + 15 posteriores a 5 FPS objetivo, máximo 320×180 y un snapshot de la muestra exacta de inferencia. Hasta aproximadamente dos segundos previos y tres posteriores; no se prometen esas duraciones si faltan frames. Ventana sin frames se cierra a los tres segundos. Reiniciar sesión descarta la evidencia pendiente anterior para no mezclar secuencias. Con slot ocupado se intenta persistir el evento sin media; no se abre otro grabador.

Una cola global de cuatro trabajos y un único consumidor de I/O. Solo referencias/copies acotadas; aproximadamente 4.4 MB de píxeles por clip de 25 frames, además del buffer, cola y snapshot. Máximo 16 MiB por MP4. Los límites de contenedor deben considerar este coste además de la inferencia; el benchmark anterior de cuatro cámaras próximo a 512 MiB no habilita cuatro cámaras con evidencia en ese presupuesto.

Primero se inserta el evento; duplicado/cooldown evita upload. Rutas canónicas owner/camera/event.jpg y .mp4 en motion-evidence/motion-clips. Comprobación de scope antes de subir y de nuevo al adjuntar. Si falla el adjunto, se intenta borrar solo el objeto recién creado. Un fallo de limpieza puede dejar un objeto huérfano privado; requiere reconciliación operativa, no se borra contenido ajeno. No se sobreescriben objetos existentes.

Métricas: persisted/suppressed/failed, snapshots/clips y errores, evidence_busy, queue_dropped, session_dropped, shutdown_pending, delivery_degraded. Fallos de entrega o cola perdida dan salida no cero al finalizar una ejecución acotada. Timeouts de PostgREST/Storage cinco segundos y drenaje máximo quince al cerrar; puede quedar trabajo sin terminar. No hay outbox durable ni promesa de entrega exactamente una vez: caída del proceso antes de insertar o saturación puede perder candidatos y se contabiliza cuando es observable. No se reintenta ilimitadamente.

`events.py` añade resumen (regla, tipo, conteo y dirección), sin trayectorias. Para media de visión valida scope vigente y prefijo antes de firmar. Tras traslado o pérdida de metadata no firma media de visión. Se conserva consulta legacy cuando 011 aún no existe mediante fallback exclusivo a columna ausente; errores externos se devuelven sin excepciones crudas; ninguna autorización ni RPC tiene fallback permisivo. Las URLs firmadas conservan expiración existente; son capacidades válidas hasta expirar, incluso si posteriormente se revoca un permiso.

Protección/retención funcionan sobre los mismos eventos/paths: no se añade borrado automático nuevo ni FCM. El botón Solicitar ayuda guarda help_requested; no promete contactar personas o servicios.

## App Android

- `data/model/Models.kt`, `data/remote/ApiService.kt`: DTOs sin scope en escritura y rutas GET/PUT.
- `ui/vision/VisionRulesScreen.kt`: lista, edición, eliminación, activación explícita, clases, filtros, horarios/días; canvas para polígonos y líneas en coordenadas completas de imagen. Es un plano de coordenadas marcado como tal, no una falsa vista de cámara. No se corta ni cambia el sistema de coordenadas.
- Navegación Regla IA desde `LiveStreamScreen`/`AppNavigation`; acceso de lectura sin botones de edición. La API siempre valida permisos efectivos.
- `EventHistoryScreen`/`EventHistoryViewModel`: revisión humana y resumen de visión, fotografía, clip, protección y estados de error. La UI no atribuye delito/identidad a tracks.
- Corregido fragmento duplicado en loadCamera que usaba refreshAt fuera de alcance. El refresh cada cuarenta segundos permanece en startEventPolling. Este error previo solo quedó expuesto cuando se pudo compilar Android.

## Validación reproducible

1. `.venv/bin/python -m pytest -q backend --disable-warnings --junitxml=/tmp/camera-phase3/tests.xml` — **129 passed**, cinco advertencias legacy. Sin acceso a Supabase/cámaras reales; fixtures bloquean red. Incluye regresión de movimiento, clips, retención, ACL y todos los tipos de regla, geometría, horarios, deduplicación, scope y fallos de entrega.
2. `.venv/bin/python backend/scripts/validate_database_security.py` — PostgreSQL propio --network none, migraciones 001–011, RLS/privilegios/CAS/replay/cooldown, scopes y rollback/reapply 010/011. Preserva filas, media, review y protección al retirar 011; metadata/configuración se pierden si se ejecuta down sin exportar.
3. Ese runner ejecuta `vision_workflow_fixture.py`: API real de FastAPI + PostgreSQL real desechable, detector geométrico inyectado, Auth y Storage **sustitutos locales explícitos**. Configura regla, procesa frame, persiste una vez, genera JPEG/MP4 legible de 25 frames, consulta media, revisa, protege y conserva al limpiar; al desproteger permite retención sin borrar evento/revisión. No certifica Supabase administrado ni exactitud del detector. Resultado: `PHASE_3_WORKFLOW_RESULT.json`.
4. `.venv/bin/python backend/scripts/benchmark_rules.py` — 100 muestras tras warmup, 32 reglas × 100 tracks por cámara, lotes secuenciales. p50/p95: 1 cámara 14.629/19.134 ms; 2 cámaras 30.737/43.522 ms; 4 cámaras 65.234/77.573 ms. RSS proceso ~56.5/61.0/69.9 MiB, acumulado en el mismo proceso. Solo motor sintético, excluye captura/modelo/DB/storage; no es capacidad multicámara. Datos: `PHASE_3_BENCHMARK.json`.

Resultados Android/Docker en el cierre al pie.

## Runbook y rollback

Revisar/exportar esquemas y backup antes de aplicar 011 a un entorno autorizado. Migración comprobada únicamente en fixture; no se ha aplicado a Supabase real. Aplicar 011 una sola vez después de 010 antes de habilitar configuración/eventos; desplegar backend/app y worker compatibles. Mantener protegidos secretos Supabase y credenciales MediaMTX; nunca ponerlos en la app o flags CLI.

Preparar modelo auditado con downloader existente; validar config de operador, source/política CIDR, captura única y scope antes de arrancar con `python -m app.vision --config <archivo-servidor> --model <peso-verificado> --resolve-scopes --persist-events`. La red debe permitir Supabase y origen autorizado, con **confinamiento real de egress nativo RTSP**. La validación de URL por sí sola no contiene redirects de FFmpeg. No activar cámaras remotas hasta validar esa puerta. Leases actuales son de un host/volumen compartido, no distribuidos.

La demo existente de Compose sigue network none y sin persistencia. Para reglas en esa demo, montar `backend/vision-rules.example.json` como `/config/rules.json:ro` (lectura para UID65534) y pasar `--config /config/rules.json --model /models/yolox_s.onnx --emit-detections --duration 8`. Geometría sintética sin objetos COCO puede producir cero eventos; el fixture del punto 3 comprueba el recorrido positivo con detector inyectado y lo declara.

Rollback funcional: desactivar reglas por API o retirar --persist-events; parar worker y drenar antes de rollback de código. Para rollback SQL usar `backend/migrations/rollback/011_vision_rules_and_events.sql` en mantenimiento y con export previo: elimina configuración/metadata de visión pero conserva eventos, evidencias, clips, review_status/is_protected y retención. La API moderna niega firma de media vision_ sin metadata; se conserva para revisión controlada/export, no se habilita acceso más amplio. No usar down para borrar evidencias o revertir 010 en un entorno activo.

## Puertas operativas que permanecen

Vídeos permitidos/anotados y evaluación de exactitud/ID switches/oclusiones/falsos positivos, prueba visual/instrumentada en dispositivo, integración con Auth/Storage Supabase administrado y drift de esquema, confinamiento de red RTSP y carga con evidencia en hardware objetivo. No son aprobaciones de producción. No se han incorporado poses, gestos ni acciones de fase 4.

## Cierre de validación Android y Docker

Android: **BUILD SUCCESSFUL**, `:app:testDebugUnitTest :app:assembleDebug --no-daemon --max-workers=2`, ocho pruebas, cero fallos/errores/skips (incluye dos nuevas de contrato). APK de depuración generado, 25,255,573 bytes; SHA256 en `PHASE_3_ANDROID_VALIDATION.json`. Ejecutado en copia temporal: comprobados los 72 archivos de fuente/configuración contra el workspace byte a byte; solo se añade local.properties temporal para el SDK. Se mantiene el criterio JDK25 del repositorio. No se cambiaron versiones Gradle/AGP/Kotlin, checksum ni TLS.

Toolchain: Gradle9.6.0 descargado oficialmente y comparado con el SHA256 del wrapper; Oracle JDK25.0.5.0.3 comparado con checksum oficial; SDK platform35, build-tools36.0.0, command-line tools23.0 (metadatos oficiales). Descargas a `/tmp/camera-phase3/android`. Para reproducir, proporcionar JAVA_HOME JDK25 completo y ANDROID_HOME con esos paquetes, ANDROID_USER_HOME escribible y Gradle user home escribible; configurar proxy/CA del entorno en propiedades de usuario, sin desactivar verificación TLS. Comando normal del proyecto: `bash ./gradlew :app:testDebugUnitTest :app:assembleDebug --no-daemon --max-workers=2` desde android. En esta validación se usó directamente bin/gradle de la distribución verificada para evitar el bootstrap DNS del wrapper. Pruebas instrumentadas/visuales: **NO EJECUTADA**, no hay dispositivo/emulador. Advertencia legacy de icono de cuenta obsoleto y biblioteca nativa empaquetada sin strip; sin error de compilación.

Docker: build correcto con CA pública montada mediante BuildKit secret (sin incluir credenciales). Demo network none, readonly y UID65534 con `vision-rules.example.json`, ONNX auditado y duración ocho segundos: salida cero, siete lotes reales de inferencia, tres snapshots healthy, cero descartes de grabación y colas vacías al detener. Cero detecciones COCO/positivos en las figuras geométricas; **no** se atribuye precisión de personas/objetos a esta demo. Inferencia neural y reglas se validan por separado del recorrido positivo con detector inyectado declarado.

Artefactos temporales: `/tmp/camera-phase3/tests.xml`, `pytest.log`, `sql.log`, `docker-build.log`, `docker-demo.log`; build Android y reportes JUnit bajo `/tmp/camera-phase3/android`. Los contenedores de prueba se eliminan al terminar.

## Evidencia de commits y entorno

Implementación backend/migración/fixtures: `8ea5828`. App/contratos/revisión y corrección de compilación: `cebf47d`. Rama `feat/ai-vision-platform`. Main intacta; sin push ni merge.

La última ejecución completa backend produjo 129 passed, cinco advertencias, 12.87 s. PostgreSQL final también confirma preservación de cooldown al editar una regla y eliminación de claves de reglas retiradas. Un intento final encontró disco insuficiente antes de crear el fixture; el runner ahora usa tmpfs de 256 MiB para PGDATA, red deshabilitada y elimina solo su contenedor propio. Se retiraron archivos de descarga ya verificados e imágenes intermedias de esta sesión. El virtualenv se trasladó a `/tmp/camera-phase3/python-venv` manteniendo `.venv` mediante enlace local excluido de Git; versión/imports comprobados. El runner definitivo terminó correctamente. Nada de ello migra, limpia o prueba datos reales.
