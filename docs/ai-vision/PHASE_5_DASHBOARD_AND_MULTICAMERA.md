> **Informe histórico del primer incremento.** El cierre funcional y los resultados vigentes están en [PHASE_5_COMPLETION.md](PHASE_5_COMPLETION.md).

# Fase 5 — dashboard y multicámara: primer incremento

Fecha: 2026-10-27 (America/Mexico_City). Rama `feat/ai-vision-platform`.
Autorización del usuario: «inicia la fase 5». **Fase 5 iniciada, no completada.** Se implementa búsqueda paginada y resumen del historial en la app existente. No se despliega ni se activan cámaras/alertas.

## Inventario previo a cambios

| Área | Evidencia existente | Estado / intervención |
| --- | --- | --- |
| App/dashboard | Android Compose, `ui/events/EventHistoryScreen.kt`, `ui/stream/LiveStreamScreen.kt` | Historial y reproducción existentes; no dashboard web separado. Reutilizar Android. |
| Timeline/revisión | `backend/app/events.py`, revisión y media firmada de fase 3 | Existían últimos 100 eventos y filtro camera_id; faltaban filtros temporales/tipo/revisión y paginación. Primer incremento. |
| Configuración por cámara | `vision_api.py`, `VisionRulesScreen.kt`, migración 011 | Reglas con ACL y CAS existentes. No duplicar ni activar análisis al guardar reglas. |
| Overlays | `vision/pose_rendering.py`, contratos de detección/landmarks | Render de laboratorio; falta transporte autorizado y sincronización con playback en Android. Pendiente. |
| Inferencia/salud | `vision/__main__.py`, `worker.py`, `pose_process.py` | Métricas y health locales; falta exponer estado fresco por scope en API/app. No confundir detección legacy con salud del worker IA. |
| Multicámara/cargas | Captura/hijos de pose aislados, queues/timeouts/backoff; Compose con límites CPU/RAM | Inferencia de objetos compartida y secuencial. Falta aislamiento integral por cámara/admisión y control de carga. El límite 512 MiB no habilita pose. |
| Substream/evidencia | Captura común con carriles recording/inference y lease por origen | No existe selección separada de substream y original. No abrir una segunda conexión sin diseño de leases/scope/sincronización y medición. |
| Datos/permisos | Migraciones 006–009, helpers 010, eventos/config 011 | Clips, horarios, retención, roles/org/revisión se reutilizan; no hacen falta migraciones para este incremento. |

Inspeccionados plan maestro completo, cierre de fase 4, README (con afirmaciones históricas desactualizadas), Compose, gateway MediaMTX, módulos, contratos, pruebas y migraciones existentes. No se interpreta README como estado efectivo. Sin nuevas dependencias, pesos ni servicios. Riesgos: consultas costosas sin índices adecuados, cambios concurrentes del historial, respuestas Android atrasadas y confundir conteos de página con totales globales.

## Cambios del incremento

### API existente GET /events

`backend/app/event_timeline.py` y `events.py` añaden parámetros opcionales:

| Parámetro | Contrato |
| --- | --- |
| camera_id | Acceso efectivo comprobado por servidor; comportamiento anterior conservado. |
| event_type | Coincidencia exacta; 1–64 letras ASCII/dígitos/guion/underscore. |
| review_status | pending, reviewed_ok o help_requested. |
| since / until | Fechas con zona horaria, normalizadas a UTC; extremos inclusivos, since <= until. |
| limit | 1–100, por defecto 100 para clientes anteriores. Android nuevo usa 30. |
| cursor | Base64 de UTC e ID UUID canónicos, máximo 512 caracteres; sin expresiones PostgREST arbitrarias. |

Filtros y autorización antes del límite. Orden descendente estable por `(detected_at, id)`; se lee como máximo limit+1 registros para detectar continuidad. El cursor selecciona estrictamente registros anteriores a esa pareja, incluyendo timestamps repetidos sin duplicarlos por el desempate. Cada solicitud recalcula acceso; el cursor **no** concede permisos ni guarda listas de cámaras. No incluye credenciales, paths de media ni scope de usuario. Puede modificarse para cambiar la posición dentro del conjunto autorizado; no es una capacidad firmada ni pretende serlo.

Se conservan `total` y `events`. **total sigue siendo cantidad devuelta en la página**, no un COUNT global. Se añaden `has_more`, `next_cursor` y `summary` con `scope=page`, `by_type`, `by_review_status`. El resumen se calcula sobre la página devuelta, sin consultas globales costosas ni rutas nuevas. Se preserva el fallback exclusivo a ausencia de vision_metadata anterior a 011, sin fallback de autorización. Errores externos no incluyen excepciones crudas.

No es un snapshot transaccional de todas las páginas: inserciones más recientes se ven al volver al inicio; cambios concurrentes de detected_at/revisión/filtros o transferencias pueden cambiar el conjunto. Cambiar filtros debe descartar cursor. La consulta anterior estaba limitada a 100; la nueva permite avanzar sin cargar todo en memoria. No se ha medido latencia PostgREST ni plan de índices sobre la base administrada. Revisarlos antes de operar grandes historiales; no se inventan índices ni migraciones.

### Android

- `data/model/Models.kt`: campos opcionales/aditivos de paginación; decodifica también respuestas legacy.
- `data/remote/ApiService.kt`, `data/repository/EventRepository.kt`: filtros/cursor de Retrofit y nueva consulta de página; `getEvents` anterior sigue para consumidores de streaming.
- `ui/events/EventHistoryScreen.kt`: chips de tipo, revisión y periodo (todo/24 h/7 días), lista cronológica, inicio/siguiente y resumen de eventos/pendientes de **esta página**. Filtros visibles también con cero resultados o error, revisión/protección/evidencias existentes conservadas. No se muestra actividad sensible experimental como evento persistido: fase 4 no la ingiere.
- `ui/events/EventHistoryViewModel.kt`: una página de 30, cancelación de solicitud previa y generación antes de publicar datos/URLs, sin acumulación infinita de páginas. Cambiar filtros/cámara reinicia cursor; revisión/protección y reintento conservan filtros/cámara. La ventana relativa se fija cuando se selecciona un filtro/entra a la pantalla; recargar conserva esa búsqueda. Los filtros locales se restauran con rememberSaveable. No hay búsqueda de texto libre ni selector nuevo de cámara en esta iteración; la API conserva camera_id.

Los chips no muestran una captura de cámara ni datos de inferencia inventados. No se incorporan landmarks transitorios a DB/logs. No se activan flags de pose/gestos/caídas, FCM ni nuevas evidencias automáticas.

## Validación

Backend:

```sh
.venv/bin/python -m pytest -q backend --disable-warnings --junitxml=/tmp/camera-phase5/backend-tests.xml
```

Resultado: **165 passed**, cinco advertencias legacy, 13.82 s. Once casos nuevos con FastAPI/TestClient y store de memoria que filtra: límite y orden, empates de timestamp/páginas disjuntas, filtros aplicados antes de paginar, cursor que no amplía scope, cámara denegada, compatibilidad de respuesta, resumen por página, normalización UTC y parámetros/cursor/rango inválidos. Conexiones de red bloqueadas por fixtures. No representa un ensayo sobre PostgREST/Supabase administrado.

Android: contrato legacy y petición Retrofit con filtros, cursor escapado, límite y respuesta nueva mediante MockWebServer local. **BUILD SUCCESSFUL** en 44 s: 10 pruebas unitarias, 0 fallos, 0 errores y 0 skips; APK debug generado (25,376,568 bytes). Recibo/checksum: [PHASE_5_INITIAL_VALIDATION.json](PHASE_5_INITIAL_VALIDATION.json). Copia temporal a `/tmp/camera-phase3/android/project`, con los 73 archivos fuente/configuración comparados SHA256 contra este checkout; SDK/JDK/cache fuera del repo. No se cambian pines, checksums ni TLS para compilar. Comando con toolchain previamente verificada:

```sh
JAVA_HOME=/tmp/camera-phase3/android/jdk/jdk-25.0.5.0.3 ANDROID_HOME=/tmp/camera-phase3/android/sdk ANDROID_USER_HOME=/tmp/camera-phase3/android/user-home GRADLE_USER_HOME=/tmp/camera-phase3/android/gradle-home bash /tmp/camera-phase3/android/gradle-9.6.0/bin/gradle -p /tmp/camera-phase3/android/project :app:testDebugUnitTest :app:assembleDebug --offline --no-daemon --max-workers=2
```

NO EJECUTADAS: UI visual/instrumentada en dispositivo, PostgREST administrado, benchmark de consultas/índices, pruebas de carga multicámara integral, substream/original ni overlays sobre vídeo en vivo. No hay cambios SQL, de modelos o del worker: no se repiten sus benchmarks/migraciones como si fueran evidencia nueva. `git diff --check` forma parte del cierre.

## Seguridad, operación y rollback

ACL actual, autenticación y media firmada de fases anteriores se conservan. El cliente nunca decide organization_id/owner_id ni usa claves servidor. Filtros de cursor solo contienen fecha UUID validadas. Sin cambios de grants/RLS/ingestión. Capacidades firmadas de media mantienen expiración anterior; no se promete revocación instantánea tras su emisión.

Rollback: revertir los commits de este incremento; los campos/parámetros son aditivos, cliente anterior funciona y cliente nuevo interpreta respuesta anterior sin next_cursor como última página. Sin migración de datos, recuperación de modelos ni acciones externas. No se modifica main, hace push/merge, despliega ni usa producción.

## Próximos incrementos de fase 5

1. Estado fresco y autorizado de inferencia por cámara: contrato mínimo de salud/FPS/colas/modelo/CPU/RSS y transporte servidor con TTL; rechazar snapshots de scope/sesión anteriores. No exponer ficheros de salud completos ni URLs/secretos por un endpoint genérico.
2. Overlay optativo sincronizado con frame/tiempo y scope, expiración, filtros de calidad y desactivación ante datos obsoletos. Verificar geometría/aspecto en dispositivo; no confundir landmarks de mano sin scores con confianza conocida.
3. Aislamiento integral y admisión por CPU/RAM, equidad entre cámaras, degradación/backpressure, recuperación y pruebas 1/2/4 con captura+objetos+pose+evidencia. Reutilizar presupuestos de fase 4, sin presumir capacidad de 512 MiB.
4. Evaluar substream explícito para inferencia y original para evidencia sin duplicar leases/capturas; contrato de sincronización, SSRF/egress y fallback comprobados antes de nuevos campos o migración.
5. Completar estadísticas/timeline globales y selección multicámara según índices y medición; prueba visual/instrumentada y gates operativos anteriores. Los filtros actuales y resumen de página no cierran esos requisitos.

La fase 5 permanece abierta. Fase 6 no iniciada.

## Cierre del primer incremento

Commits verificados: `ffff939` backend/11 casos nuevos; `d0abdeb` Android/dos casos nuevos. Rama `feat/ai-vision-platform`. Backend 165/165 y Android 10/10; build offline exitoso y APK con hash registrado. `git diff --check` sin errores. No hay migraciones, push, merge ni despliegue. El SHA del commit documental se entrega al finalizar. Quedan los siguientes incrementos de esta fase y las validaciones operativas explícitas; no se declara fase 5 terminada.
