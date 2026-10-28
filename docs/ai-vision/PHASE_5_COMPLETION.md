# Fase 5 — cierre funcional: dashboard y multicámara

2026-10-27, America/Mexico_City. Rama `feat/ai-vision-platform`.
Usuario autoriza «pues termina la fase 5». **Implementación de fase 5 completada y validada en entorno controlado. No equivale a aprobación de producción. Fase 6 no iniciada.** El [primer incremento](PHASE_5_DASHBOARD_AND_MULTICAMERA.md) conserva su evidencia histórica; este informe establece el estado vigente.

## Inventario previo, plan y alcance final

Antes del cierre existían API de eventos con filtros/paginación, revisión humana y protección, configuración de reglas por cámara, render de laboratorio y métricas locales. Faltaban transporte autorizado de estado/previews, integración de overlays en app, aislamiento integral por cámara, admisión CPU/RAM, recuperación del proceso completo, selección segura de substream/original y estadísticas de ventana/selector de cámaras. El inventario detallado y dependencias del primer incremento se mantienen; plan maestro, módulos, Compose/gateway, tests y migraciones 006–011 fueron contrastados con el código real.

Se reutilizan Android Compose, autenticación, ACL, reglas/CAS, eventos, media y retención; no se duplica dashboard web ni esquema. Riesgos considerados: scope tras transferencia, telemetría/imagen obsoleta, geometría de overlays sobre otro frame, consumo nativo, procesos huérfanos y desalineación entre streams. **Sin migraciones, dependencias nuevas, pesos nuevos ni cambios a main.**

| Requisito | Implementación comprobable |
| --- | --- |
| Timeline, búsqueda y revisión | Filtros/paginación del incremento anterior, selector de cámaras autorizadas, revisión/protección/media existentes. |
| Estadísticas | Conteos exactos por ventana autorizada, separados del resumen de página; periodo hasta 31 días. |
| Estado IA por cámara | Snapshot tipado, mínimo y privado con TTL; endpoint autenticado y panel Android. |
| Overlays optativos | Previews base y dibujado de **un mismo frame**, geometría/aspecto preservados, caducidad de tres segundos, interruptores apagados por defecto. |
| Aislamiento / carga | Fleet con un grupo de procesos por cámara, afinidad de un CPU por grupo, admisión CPU/RAM, colas acotadas, límites/health/watchdog y reinicio acotado. |
| Substream/original | Selección server-only aprobada por scope/origen; inferencia en substream, carril de evidencia desde original con alineación acotada y rechazo si no hay muestra adecuada. |

## Transporte de dashboard y seguridad

`backend/app/vision/dashboard.py` define `Snapshot` v1 con camera/owner/org, sesión, UTC de publicación/frame, salud/estado, FPS observado de captura/inferencia, frames/descartes, RSS/CPU y versión del modelo. Solo dos JPEG, sin persistir coordenadas, trayectorias, identidades ni señales sensibles. Los campos se enumeran en el contrato: no se publica el JSON de health completo ni configuraciones/URLs/keys/paths del worker.

Activación explícita mediante `--dashboard-directory /run/vision-dashboard` y `VISION_DASHBOARD_DIRECTORY=/run/vision-dashboard` en API. Directorio absoluto, privado **0700**, propietario del UID de ambos servicios; usar **tmpfs** compartido con presupuesto recomendado 8 MiB para cuatro cámaras, no volumen público/durable. Un archivo por UUID de cámara, máximo 1 MiB, reemplazo atómico con archivo temporal 0600. Lectura rechaza symlink final, archivo no regular, exceso de tamaño, contrato inválido, scope distinto, fecha futura o publicación con más de 10 s. Requiere filesystem local compartido: no es un bus distribuido multihost. Un fallo no convierte el directorio en acceso público.

`GET /cameras/{camera_id}/vision-status?preview=false&overlay=false`:

- Autenticación y acceso efectivo vigente; el servidor obtiene scope actual desde cameras y lo compara con snapshot. Revocación devuelve 403; traslado/snapshot ausente, vencido, corrupto o transporte desactivado devuelve estado unavailable sin imagen.
- Respuesta omite owner/org y ambos JPEG internos. `preview=true` solicita solo la variante base o overlay elegida; solo con worker saludable y frame de antigüedad <=3 s. `Cache-Control: no-store, private`. Sin endpoints públicos de ingestión ni URLs de imágenes reutilizables.
- FPS son observados acumulados desde inicio, no objetivos garantizados. RSS/CPU del worker incluyen contadores conocidos de procesos de captura/pose; sumas RSS, no PSS ni RAM exclusiva. La vista es por cámara; el supervisor mide el grupo completo por separado. Salud de captura/inferencia no certifica entrega a DB/Storage: delivery_degraded y fallos de evidencia siguen disponibles en métricas internas, no se convierten en una afirmación de entrega correcta del panel.
- `__main__.py` publica a intervalos de un segundo cuando se activa dashboard, descarta resultados obsoletos y elimina archivos al cerrar. Fleet elimina también snapshots al matar/reiniciar un hijo. Si una muerte abrupta impide limpiar, el TTL niega lectura; **el TTL no borra bytes**: tmpfs se debe desmontar/limpiar al retirar el servicio.

Los previews contienen imágenes de cámara: el flag del operador autoriza su generación transitoria y el usuario habilita su visualización. No se guardan en Git, DB, Storage ni logs. No activar este flag sin política de acceso/privacidad del despliegue. Un servicio con acceso de escritura al directorio es un componente confiable; esto no es un sandbox ni firma criptográfica contra otro proceso comprometido del mismo UID.

## Overlays y Android

`vision/dashboard.py:preview` valida detección/scope/sesión/timestamp y esqueleto/scope/secuencia/timestamp antes del render. Conserva original sin mutación. Ambas variantes JPEG se generan juntas, respetan aspecto y tienen límites de dimensiones/tamaño. Se incluyen cajas y esqueleto corporal con calidad conocida; manos sin scores permanecen ocultas según política conservadora de fase 4. Ningún efecto visual se interpreta como acción.

`ui/stream/VisionStatusPanel.kt`, integrado en `LiveStreamScreen.kt`, muestra estado/FPS/frames descartados/RSS/CPU y una vista optativa del frame analizado con toggle de dibujo. **La imagen de análisis se muestra separada del HLS**: no se afirman coincidencias con un frame HLS cuyo reloj/PTS no está disponible. El overlay sí corresponde exactamente a su JPEG, sin proyección sobre vídeo desfasado ni transformación por recorte. `ContentScale.Fit` conserva geometría.

Consulta cancelable de tres segundos, comprobación de camera_id, recálculo de vida restante restando antigüedad del servidor y RTT completo. Preview se retira antes de otra solicitud o al agotar ese plazo, también ante red colgada. `VisionPreviewPolicy.kt` rechaza scope incorrecto, valores no finitos/negativos y estado no saludable. Se deshabilitan caches Coil de memoria/disco para esas imágenes; filtros/scope/cámara reinician estado. No se representa unavailable como inferencia saludable. API puede funcionar sin transporte configurado, mostrando estado no disponible.

`EventHistoryScreen.kt` añade cámaras del `CameraRepository` autorizado y estadísticas por periodo. `EventHistoryViewModel.kt` conserva cancelación/generación de consultas y limita una página a 30; revisión/protección conservan filtros. `GET /events/statistics` usa ACL actual, filtros cámara/tipo/revisión, UTC, ventana por defecto 24 h y máximo 31 días. Ejecuta hasta dos consultas HEAD de conteo exacto, sin cargar eventos/media: total filtrado y pendientes dentro del filtro. No son conteos de la página ni conteos de personas. Si el filtro excluye pending, pendientes es cero. Con historial sin límite de periodo, el panel indica explícitamente que estadísticas son últimas 24 h. Si falla ese endpoint, el historial sigue visible.

Los dos conteos no forman un snapshot transaccional: escrituras/revisión concurrentes pueden cambiar resultados entre consultas. Verificar latencia/índices y límites de PostgREST en el entorno administrado antes de grandes historiales. No se inventan resultados de esa base ni se agregan índices sin medir.

## Fleet, límites y recuperación

`python -m app.vision.fleet` carga config de operador de una a cuatro cámaras y crea un proceso/grupo separado por cámara con config 0600 temporal. Cada grupo tiene su propio detector/tracker/reglas, captura, pose y evidencias; una inferencia bloqueada no bloquea el bucle de otra cámara. No se comparte el detector nativo entre cámaras en este modo. El entrypoint anterior sigue disponible para compatibilidad; **usar fleet para este aislamiento**.

- `--cpu-slots` 1–4, número de cámaras <=slots; valida afinidad y cuota cgroup conocida. Cada hijo fija afinidad a un CPU distinto disponible antes de importar modelos; descendientes heredan la máscara. Thread pools configurados a uno. El control es local al fleet: múltiples fleets deben coordinar cpuset/cuota; no es un scheduler global.
- `--camera-memory-mib` 128–8192 y `--memory-mib` 128–32768; suma admitida por cámara <=total y total <=cgroup conocido. Conserva mínimo de fase 4: pose 768 MiB/cámara +256 MiB si objetos. Budgets incluyen margen y no certifican capacidad. Ejemplo completo objetos+pose requiere 1024 MiB por cámara, más margen del supervisor/contenedor.
- Muestrea grupos cada ~250 ms: suma RSS/CPU y número de procesos, CPU observado. Exceso RSS por cámara o >32 procesos provoca cierre/reinicio; CPU >1.5 cores tras 30 s de gracia también. Muestreo no es un límite instantáneo: **cgroup/mem_limit/cpus/pids_limit siguen siendo obligatorios** como límite duro. Puede existir sobrepaso entre muestras y RSS suma memoria compartida varias veces. El ejemplo Compose sin modelos limita 2 CPUs/1 GiB/96 tareas y raíz de solo lectura.
- Health del worker debe estar fresco en 20 s después de gracia de arranque 30 s. Muerte, límite o watchdog cierra solo el grupo propio y reintenta con backoff 2/4/8 s; máximo tres reinicios. Agotamiento da salida 1. Ejecución acotada sin cámara saludable nunca se declara exitosa.
- Parent-death SIGKILL y validación del PID padre antes de cargar modelos. Desalojo forzoso espera dos segundos y mata restos del grupo; cierre normal envía SIGTERM a todos y comparte ventana de drenaje de 15 s antes de SIGKILL. Crash/límites pueden perder trabajos en memoria: no se promete entrega exactamente una vez.
- Health agregado contiene solo cámaras, recursos y contadores; no se publica directamente a usuarios. El endpoint por cámara revalida ACL/scope. Leases de captura siguen siendo locales al host/volumen, no distribuidos.

## Substream para inferencia, original para evidencia

`CameraConfig.inference_source` es opcional, excluido de serialización pública y logs. Sin él permanece la captura común anterior. En archivos privados del operador puede indicar un substream diferente, con el mismo tipo de origen; para vídeos exige ruta absoluta existente, para RTSP se aplica la misma validación de esquema/puerto/DNS/CIDRs en decoder. No hay endpoint cliente para elegir URLs ni se aceptan credenciales nativas en RTSP.

Para RTSP se exige además `VISION_SUBSTREAM_REGISTRY`, archivo privado del operador con hasta 64 KiB. Forma de cada entrada (valores reales solo fuera de Git): clave camera UUID y campos owner_id, organization_id, original, inference. En cada autorización/revalidación, scope y URL original deben coincidir con cameras y substream con ese registro. Transferencia, sustitución, revocación o archivo ausente detienen el proceso; no hay fallback hacia otra cámara o URL arbitraria. Proteger el registro con permisos 0600. La validación de URL **no** sustituye el confinamiento de egress de FFmpeg ante redirects, gate anterior aún vigente.

El proceso mantiene lease canónico de cámara mientras captura substream y una lease interna derivada para el lector original; así el capturador legacy no abre original simultáneamente. El presupuesto de buffers considera ambos lectores. El original tiene consumidor independiente; la evidencia reutiliza buffers/encoder/storage/retención existentes y sigue acotada a 320×180. “Original” describe la fuente, no implica evidencia full HD ni otra política de retención.

`EvidenceCollector(separate_recording=True)` selecciona snapshot del original dentro de ±0.5 s del tiempo de captura **del servidor**, y pre/postframes de su sesión. Si no hay muestra contemporánea, inserta evento sin media y cuenta unmatched_original; cambios de sesión descartan continuidad. No copia el frame de inferencia como si fuera original. **No se garantiza sincronización de sensores/PTS**: redes o buffers distintos pueden invalidar correspondencia física pese a proximidad de recepción; validar equipos destino o mantener captura común. Esto no certifica uso forense.

## Validación ejecutada

Recepciones/checksums y detalles: [PHASE_5_COMPLETION_VALIDATION.json](PHASE_5_COMPLETION_VALIDATION.json), [PHASE_5_FLEET_VALIDATION.json](PHASE_5_FLEET_VALIDATION.json).

1. `.venv/bin/python -m pytest -q backend --disable-warnings --junitxml=/tmp/camera-phase5-completion/backend-tests.xml` — **172 passed**, cinco avisos legacy, 17.46 s. Red bloqueada por fixtures. Incluye regresión y siete casos nuevos de dashboard/estadísticas: TTL/futuro/scope/symlink/permisos, ACL/transferencia/no-cache, geometría/frame exacto/no mutación, admisión/grupo propio, registro de substream, original contemporáneo/ausente y conteos autorizados/periodos.
2. Android `:app:testDebugUnitTest :app:assembleDebug --offline --no-daemon --max-workers=2` — **BUILD SUCCESSFUL**, 12 pruebas, cero fallos/errores/skips, APK debug. Los 76 archivos de fuente/configuración copiados al build temporal se compararon SHA256. Dos casos nuevos comprueban expiración/scope/NaN/red y estado unavailable/estadísticas de ventana. JDK25/Gradle9.6/SDK anteriores, pines/checksums/TLS sin cambiar. Imagen/TTL se verifican por contrato; no se declara prueba visual en dispositivo.
3. Modelo/captura/preview/evidencia concurrente y recuperación reales de procesos, mediante:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/validate_dashboard_fleet.py --model .models/yolox_s.onnx --pose-python /tmp/camera-phase4-completion/runtime-tasks/bin/python --output /tmp/camera-phase5-completion/fleet-final-affinity
```

Resultado **PASS, 1/2/4 cámaras**, salidas 0, salud por cámara, JPEG de preview decodificado, retirada al cerrar. Captura geométrica sintética y modelos YOLOX_s/MediaPipe Tasks reales CPU; negativos COCO, no precisión de acciones. Evidencias **inyectadas explícitamente** en paralelo, JPEG y MP4 de 25 frames por encoder real, con RPC/Storage locales sustitutos: no se atribuyen esos positivos al modelo ni a Supabase administrado. En dos cámaras se mata un worker propio, se observa su recuperación y salud de la otra durante el reinicio. No se mata ningún proceso externo.

| Cámaras | Duración configurada | Inferencias por cámara (último snapshot) | FPS observado por cámara | Pico RSS sumado por grupo MiB | JPEG / MP4 locales | Descartes cola evidencia fixture |
| --- | ---: | --- | --- | --- | --- | ---: |
| 1 | 16 s | 12 | 0.83 | 576.5 | 9 / 9 | 0 |
| 2 | 30 s | 20 / 27 | 0.84 / 0.92 | 576.4 / 576.7 | 32 / 32 | 0 |
| 4 | 16 s | 11 / 11 / 9 / 9 | 0.69 / 0.68 / 0.57 / 0.59 | 575.8 / 575.3 / 575.4 / 575.4 | 36 / 36 | 0 |

Objetivo configurado 3 FPS **no alcanzado** en este host compartido con un core por grupo. Descartes de inferencia: 28; 45/52; 31/31/33/33 respectivamente. Backpressure mantiene límites; no es garantía de FPS ni ausencia de pérdidas. Un ensayo anterior bajo saturación sin afinidad produjo descartes de la cola de evidencia; se conservó su diagnóstico local y se implementó afinidad. La tabla corresponde únicamente a la repetición final, no oculta esa limitación. Revisar hardware/CPU y reducción de FPS/modelos antes de habilitar escenarios; estos resultados no cualifican acciones sensibles a 2 FPS efectivos.

4. Dos vídeos geométricos locales diferentes, `inference_source` explícito, YOLOX real: ejecución acotada seis segundos, snapshots saludables simultáneos de original/substream y cierre. Fixture unitario comprueba que el snapshot adjunto sale del original y que la ausencia de alineación deja media vacía. No es una prueba RTSP de PTS de sensores ni ingestión con base real.
5. Contenedor de demo: fuente actual transmitida por tar a tmpfs en imagen de dependencias ya existente; dos cámaras sintéticas, sin modelos, saludables y detenidas, sin OOM. **network none, UID65534, raíz read-only, 2 CPUs/1 GiB/96 tareas.** Confirma funcionamiento del supervisor en ese aislamiento, no una nueva imagen release. Compose añadido `docker-compose.fleet.yml`; la prueba usó comandos equivalentes para no iniciar API/servicios reales.
6. Build Docker de imagen nueva: **FALLÓ por espacio agotado** del overlay del entorno. No se cambió TLS ni se borraron imágenes/volúmenes ajenos para ocultarlo. Solo se retiraron IDs exactos de caché creados por ese intento; modelo ignorado de 35 MiB trasladado a `/tmp/camera-phase5-completion/yolox_s.onnx` manteniendo enlace local. Se recuperó el espacio y se ejecutó el smoke anterior. Reconstruir la imagen de entrega con disco suficiente sigue siendo gate de release, no se declara aprobado.

NO EJECUTADAS (no hay dispositivo/emulador ni equipos RTSP de prueba; no se usan credenciales/datos reales): prueba visual/instrumentada en dispositivo, integración Supabase administrado/PostgREST y planes de índices, RTSP substream de equipos reales/PTS, política de egress nativo en redes remotas, precisión de modelos/caídas y soak prolongado. No hay cambios SQL ni pesos: no se repiten migraciones ni auditorías de modelos como evidencia nueva. Las condiciones/limitaciones de fase 4 siguen vigentes.

## Operación reproducible y rollback

Modelo y runtime de pose se preparan con los instaladores/hashes documentados en fase 4, separados de dependencias API. Configs reales y registro de substream nunca van al cliente ni a Git. Ejemplo aislado sin modelos:

```sh
PYTHONPATH=backend .venv/bin/python -m app.vision.fleet --config backend/vision-fleet.example.json --cpu-slots 2 --memory-mib 1024 --camera-memory-mib 512 --duration 10
```

Para dashboard, montar **el mismo tmpfs privado** en API y fleet con igual UID y modo 0700, fijar variable API y pasar --dashboard-directory al fleet. El ejemplo Compose no expone dashboard ni incorpora pose automáticamente. Para RTSP usar --resolve-scopes, configurar políticas CIDR/puerto y egress, proporcionar registro aprobado si substream. Para persistencia añadir --persist-events únicamente con permisos/migraciones/configuración anteriores verificados. No se ejecutó esa activación contra producción.

Rollback: detener fleet con SIGTERM, drenar y desactivar flags/transporte; retirar variable API y configs de substream para volver a captura común. Revertir commits de este cierre en orden inverso si se requiere rollback de código. Sin nuevas tablas/datos que migrar. Borrar/desmontar solo tmpfs propio de previews al retirar el servicio; no se borran evidencias existentes ni se cambia retención. API/app manejan transporte ausente como unavailable; clientes anteriores conservan eventos/reglas.

## Aceptación y cierre

Se completan los componentes funcionales de fase 5 y su prueba controlada, con limitaciones medidas. Se conservan como **gates de release** el dispositivo, infraestructura administrada, índices/latencia reales, red/PTS/hardware, nuevo build de imagen con espacio y precisión/condiciones de modelos. No afirmar dashboard HLS con coordenadas sincronizadas: el producto entrega una vista IA del mismo frame y HLS independiente. No hay activación sensible, identidad persistente, nuevas notificaciones, migración/despliegue real ni push/merge. Main intacta. Esperar instrucción antes de fase 6. Los SHA efectivos se entregan al crear commits; no se inventan en este documento.

Commits de implementación verificados: `0b3f080` backend/transporte/supervisión/substreams/pruebas y `90eb473` app/política de preview/estadísticas. Ambos en `feat/ai-vision-platform`. El SHA documental se reporta tras crearlo. `git diff --check` correcto; backend final 172/172, Android 12/12, benchmark final 1/2/4 PASS y smoke aislado con dos cámaras saludables. No se han hecho push, merge ni despliegue.
