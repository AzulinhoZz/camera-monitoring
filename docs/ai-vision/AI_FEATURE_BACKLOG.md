# Backlog verificable — Camera Monitoring AI 2.0

Fecha: 2026-10-26. Rama documental: `feat/ai-vision-platform`. Fuente: [plan maestro](MASTER_PROMPT_AI_2_0.md) leído completo y [auditoría técnica](CURRENT_ARCHITECTURE_AUDIT.md) sobre main `fae1bad6211a58d770ab4396fc43a157846a411f` + plan `74fc4cbbe70e48383bf552bc8fd77e749598be04`.

**Historial de FASES 0/1; avance de FASE 2 en sección H.** El usuario autorizó continuar con FASE 1 el 2026-10-26. El estado actual se detalla en [el informe de infraestructura](PHASE_1_VISION_INFRASTRUCTURE.md); las tablas originales se conservan como trazabilidad del plan. En la auditoría original solo se ejecutó FASE 0. En la auditoría original no había migraciones nuevas ni IA implementada. Los avances posteriores se registran abajo; una prueba mocked no resuelve por sí sola una historia.

## Estado de la iteración

| Entregable FASE 0 | Resultado real |
| --- | --- |
| Inventario de código, endpoints, arquitectura, auth, workers, UI y SQL | Documentado en auditoría con rutas y símbolos. |
| Pruebas Python seguras | 35 aprobadas / 6 fallidas sin variables; diagnóstico y repetición con fixtures aisladas: 41 aprobadas, 0 omitidas/xfail. |
| PostgreSQL local | Cadena 001–009 aplicable al fixture; seguridad con resultados mixtos, no suite totalmente aprobada. |
| Android | Bootstrap intentado; tests NO EJECUTADOS por UnknownHostException del wrapper. |
| Métricas disponibles | Microbenchmark sintético de motion a 640×480 y 1280×720; sin FPS IA ni SLO end-to-end. |
| Propuesta de arquitectura | Incluida en auditoría, sujeta a revisión. |
| Código, esquema remoto y producción | Sin cambios. |
| Paso a FASE 1 | Autorizado después de esta línea base; ver actualización al final. |

## Reglas para ejecutar futuras historias

Antes de cada fase: actualizar inventario existe/parcial/falta/riesgo, alcance, dependencias, archivos previstos, migraciones justificadas y pruebas. Prohibido trabajar directamente en main, forzar push, hacer merge o producción sin autorización. Commits pequeños convencionales; informar SHA real.

Cada historia debe incluir definición funcional y permisos, pruebas positivas/negativas/regresión, contrato de datos, manejo de errores/logs sin secretos, métricas y límites medidos, demo reproducible o impedimento expreso. Si necesita SQL, exigir migración aditiva revisada, rollback probado y análisis de compatibilidad/backfill en DB desechable. No editar/aplicar versiones históricas para ocultar drift.

Prioridades: **P0** seguridad, pipeline, contratos y pruebas; **P1** objetos/tracking/reglas/evidencias; **P2** poses/gestos/acciones experimentales; **P3** analítica y optimización. No iniciar P2/P3 antes de cerrar los bloqueos P0/P1. Las rutas indicadas abajo son existentes salvo donde se dice “por definir”; no se presentan archivos futuros como implementados.

## A. Prerrequisitos P0 para una FASE 1 segura

Las correcciones de esta sección **no se realizaron en la auditoría**. Revisar y aprobar su inclusión en la siguiente iteración antes de implementarlas. Sin migraciones a entornos reales.

| ID | Estado / prioridad | Historia y evidencia | Dependencias / archivos previstos | SQL | Aceptación verificable |
| --- | --- | --- | --- | --- | --- |
| GATE-00 | Pendiente / P0 | Revisar auditoría/backlog, acordar los bloqueos y autorizar alcance FASE 1. | Ambos documentos y decisión del usuario. | No | Aprobación explícita registrada; lista de historias autorizadas, riesgos y pruebas de salida. Sin aprobación no escribir código de FASE 1. |
| AUTH-01 | Parcial, riesgo / P0 | Aislar grants por organización y separar leer/editar/borrar/crear evento. SEC-01/02. | `backend/app/admin.py`, `permissions.py`, `cameras.py`, `events.py`, pruebas existentes y nuevas de permisos por definir. | Evaluar 009; no duplicar grants | Administrador de org A no concede cámara de B ni a destinatario de B; lector con grant no edita/borra salvo política explícita aprobada. Probar API con clave backend simulando bypass RLS y SQL con roles reales de prueba. Positivos para owner y admin autorizado, negativos anon/tenant cruzado, revocación efectiva. |
| AUTH-02 | Defecto reproducido / P0 | Corregir selección organization_id en has_camera_access y coherencia owner/grant/admin en lectura/configuración. BUG-03. | `permissions.py`, `main.py`, `storage.py`, `retention_manager.py`, tests tenant. | Solo si matriz revisada lo exige | Fixtures respetan select; admin de misma org obtiene acceso previsto, otro tenant no. Matriz explicita qué acciones owner-only siguen siéndolo y cuáles admiten flota. No ampliar permisos por accidente. |
| AUTH-03 | Parcial, riesgo / P0 | Autenticación efectiva gateway→API y usuario→HLS/RTSP. SEC-03. | `gateway/mediamtx.yml`, `auth.py`, Compose, `LiveStreamScreen.kt`, API de stream. | No prevista | Gateway autentica callback y no confía en ip/action arbitrarias. Publicar y leer sin credencial se rechaza según política, path coincide exactamente, revocación corta acceso, playlist y segmentos protegidos. Video sintético; nada de cámaras reales. |
| AUTH-04 | Falta / P0 | Política SSRF para RTSP y redacción de URLs/logs. SEC-04. | `cameras.py`, `connectivity_checker.py`, `motion_detector.py`, configuración de red por definir. | No prevista; credenciales servidor requieren diseño si se habilitan | Rechazar esquemas/puertos/destinos prohibidos, loopback/metadata/redes no autorizadas y DNS cambiante. Permitir redes de cámaras explícitamente autorizadas sin prohibir indiscriminadamente toda LAN. No devolver ni registrar userinfo/secretos legados. Probar redirects/resolución según transporte y límites de conexión. |
| DB-01 | Defecto validado / P0 | Resolver ruta canónica de 009 y permisos mínimos de helpers. SEC-05. | `backend/migrations/009_roles_and_organizations.sql`, copia `backend/app/migrations/...`, Dockerfile, tests SQL. | Requiere estrategia revisada; posible migración correctiva aditiva | Instalación con roles mínimos funciona sin GRANT ALL ON ALL FUNCTIONS. authenticated usa solo helpers necesarios; anon no ejecuta funciones indebidas. Verificar RLS como non-superuser y bypass explícito de backend. Determinar drift antes de tocar históricos; fixture existente y datos preservados. |
| DB-02 | Parcial / P0 | Hacer verificable SQL de seguridad, corregir caso 6 y separar expected errors. QA-01. | `backend/app/tests/setup_test_db.sql`, `run_real_postgres_security_tests.sql`, `test_sql_009_isolated.py`; runner por definir. | No migración funcional | Conteos, permisos denegados y SQLSTATE comprobados con exit status fiable; unidad cruzada alcanza la instrucción pretendida. Pruebas de alta/update, grants, organizaciones, perfiles y service_role vs authenticated; entorno efímero sin red, sin sobrescribir DB existente. |
| API-01 | Defectos reproducidos / P0 | Reparar proyecciones de evidencia, clip, metadatos de evento y stream-url. BUG-01/02. | `events.py`, `cameras.py`, `test_evidence_endpoints.py`, contratos Android. | No prevista | Filas devueltas respetan columnas seleccionadas; fotos/clips reales de fixture obtienen URL firmada, ausencia legítima se distingue, protección/revisión persisten al listar, stream-url no produce KeyError. Negativos de tenant y expiración de URL, regresión sin media. |
| QA-02 | Parcial / P0 | Fixtures aisladas y pruebas que no dependan de variables reales ni mocks permisivos. QA-01. | `backend/tests`, `backend/app/tests`, dependencias de desarrollo/CI por definir. | Solo fixture local | `pytest` ejecuta 41 casos existentes con configuración explícita y sin producción; no oculta fallos de API ni usa fail-closed DB ausente como evidencia de aislamiento. Mock/fake estricto o integración local para select y permisos; diferenciar unit/integration/live. No desactivar assertions. |
| OPS-01 | Pendiente / P0 | Obtener entorno reproducible Android e integración backend sin producción. | Gradle wrapper/checksum existentes, SDK/JDK, Compose override de prueba por definir, README. | Bootstrap de prueba por definir; no remoto | Resolver distribución oficial sin bajar verificación, SDK y toolchains compatibles; ejecutar JVM y build APK con resultado real. Tests instrumentados requieren dispositivo. Supabase/Auth/Storage de prueba aislados o emuladores compatibles, sin reutilizar credenciales productivas. Registrar límites no cubiertos. |

## B. FASE 1 — Alcance propuesto en auditoría (estado actualizado al final)

| ID / prioridad | Existe / falta | Trabajo propuesto y dependencias | Archivos a evaluar | Migración prevista | Pruebas y criterio de salida |
| --- | --- | --- | --- | --- | --- |
| VIS-01 P0 | Existe motor motion; falta aislamiento | Diseñar frontera del vision-worker a partir de MotionDetectorManager; una captura por cámara, compatibilidad con motion actual. Depende GATE-00 y P0 autorizados/cerrados. | `motion_detector.py`, `main.py`, `connectivity_checker.py`, `docker-compose.yml`; módulo/servicio nuevo por definir tras revisión. | Ninguna para prototipo aislado | API sigue ofreciendo funciones previas; arranque/parada repetidos no duplican workers. Comparación de regresión motion; kill/restart recupera sin duplicar eventos. Flags y rollback restauran camino anterior, sin migración destructiva. |
| VIS-02 P0 | Parcial y riesgoso | Captura con open/read timeout, reconexión/backoff, backpressure, cancelación y cierre ordenado. Depende VIS-01/AUTH-04. | `motion_detector.py:run`, `connectivity_checker.py`, adaptador compartido por definir. | No | Streams sintéticos: desconexión/read=false con isOpened=true, reconexión, frame lento/corrupto y stop durante bloqueo. Cola acotada demostrada, join en plazo pactado, memoria estable, counters de drops y edad de frame. |
| VIS-03 P0 | Falta | Contrato versionado detección/evento y aislamiento de tenant derivado de cámara. Depende AUTH-01/02 y DB-01. | `events.py`, `Models.kt`; esquema formal por definir, sin inventar rutas ahora. | Evaluar extensión de camera_events, revisión previa obligatoria | schema_version, camera_id, organization_id validada, UTC, model_version, class, confidence, bbox normalizada, track_id temporal, rule_id y evidencia opcional. Pruebas de validación, idempotencia, replay, out-of-order, tenant y cámaras sin org; preservar consumidores de motion_detected. |
| VIS-04 P0 | Solo frame_interval y logs | Separar FPS captura/evidencia/inferencia y observabilidad por cámara. Depende VIS-01/02. | `motion_detector.py`, `clip_recorder.py`; configuración/telemetría por definir. | Evaluar reutilización camera_motion_configs; no asumir esquema | FPS efectivo, p50/p95, CPU/RSS, colas/drops, reconexiones y persistencia medidos con video permitido. Configuración por cámara y límites pactados; no usar FPS de microbenchmark como capacidad de inferencia. |
| VIS-05 P0 | Baseline solo sintético | Fixtures de video permitido, reproducibilidad y presupuesto 1 cámara. Depende QA-02 y entorno aislado. | Tests/video fixtures por definir, documentación de procedencia y benchmark. | No | Video sin datos personales y licencia verificable, metadata de duración/resolución/FPS, errores inyectados, alarmas/MB por hora observados. HLS y RTSP de prueba accesibles solo localmente. Pasar a 2/4 solo si presupuesto lo permite. |

**Salida FASE 1 propuesta:** P0 acordados cerrados con evidencia, pipeline sin modelo IA probado con fuente sintética, contrato revisado, límites/telemetría y rollback demostrados. Entregar informe/commits y detenerse para revisión antes de migraciones o integración de modelos. Esta sección no aprueba el diseño final.

## C. FASE 2 — Objetos y tracking (pendiente)

| ID / prioridad | Estado | Dependencias y alcance | Datos / rutas previstas | Aceptación |
| --- | --- | --- | --- | --- |
| MODEL-01 P1 | Falta | Tras FASE 1, evaluar Ultralytics YOLO y alternativas; ByteTrack o tracker compatible. No instalar ni descargar pesos en auditoría. | Expediente de licencias/procedencia/mantenimiento/vulnerabilidades y matriz de compatibilidad por definir. Sin migración inicial. | Revisar por separado código, pesos y datasets, uso comercial y redistribución; fuentes/checksums verificables, dependencias fijadas, alternativa si licencia no satisface. Aprobación antes de integración. |
| DET-01 P1 | Falta | Detección de clases configurables, confianza y cajas sobre VIS-03. Depende MODEL-01. | Worker/contrato de VIS-01/03; flags por cámara; posibles extensiones aditivas revisadas. | Casos positivos/negativos por clase y escenarios, threshold documentado, no detecciones “infalibles”, rollback al motion anterior. Métricas de precisión/recall en set permitido, FPS/latencia medidos, manejo de fallo/carga de modelo. |
| TRACK-01 P1 | Falta | IDs temporales por cámara, trayectorias y conteos. Depende DET-01 y tracker auditado. | Estado temporal en worker, eventos versionados; retención por definir, no identidad persistente. | Oclusión/entrada/salida/reconexión no producen conteos no explicados; medir ID switches y error de conteo. Sin identificación personal ni seguimiento entre cámaras. Benchmarks 1 y luego 2/4 bajo presupuesto. |

## D. FASE 3 — Reglas y evidencias (pendiente)

| ID / prioridad | Estado y evidencia | Dependencias / archivos existentes a reutilizar | SQL y aceptación |
| --- | --- | --- | --- |
| RULE-01 P1 | Polígonos/máscaras existen; falta regla semántica | TRACK-01; `zone_store.py`, `main.py`, `LiveStreamScreen.kt`, 004. | Extender solo si contrato aprobado; no otra tabla de polígonos. Reglas por cámara/org/horario; pruebas dentro/fuera/borde, zonas inválidas y aislamiento, UTC/horario nocturno. Validar polígonos degenerados/autointersección según política. |
| RULE-02 P1 | Líneas, intrusión, permanencia/conteos faltan | RULE-01; tracker y contrato versionado. | Nuevos tipos/config solo tras revisión. Cruce con dirección, permanencia con interrupciones, deduplicación y cooldown probados; medidas de falsos positivos y límites explícitos. Objeto abandonado como evento probable, sujeto a revisión. |
| MEDIA-01 P1 | Fotos/clips existentes, API defectuosa y memoria no acotada por bytes | API-01, VIS-02/04; `evidence_uploader.py`, `clip_recorder.py`, 005/006. | Reutilizar buckets/rutas y campos existentes. Pre/postevento con timestamps y tamaño acotado, subida fallida no crea éxito falso, URLs firmadas con expiración y control tenant/path. Codec compatible Android verificado con reproducción real local. No duplicar buckets ni cambiar retención sin revisión. |
| RET-01 P1 | Retención/protección existentes, scheduler falta y métricas estimadas | `retention_manager.py`, `storage.py`, 008; AUTH-01/02. | Evaluar sincronización/protección atómica antes de habilitar auto-cleanup. Dry-run sin borrados, protegido nunca se elimina en carrera, Storage failure no limpia path y contadores reflejan resultado. Pruebas con metadatos paginados; auto scheduler solo con política aprobada y rollback seguro. |
| REVIEW-01 P1 | Revisión manual existe pero silencia fallos | `events.py:review_event_alert`, pantallas eventos/dashboard, BUG-04. | Evaluar reviewed_by/historial como extensión, no duplicar review_status. Respuesta de error ante persistencia fallida, actor/UTC y autorización comprobables. Acciones ambiguas deben decir “posible” y requerir revisión; no emitir juicios de delito. |

## E. FASES 4–6 — Trabajo condicionado

| ID / fase / prioridad | Estado y alcance | Dependencias | Aceptación y límites |
| --- | --- | --- | --- |
| POSE-01 / 4 / P2 | Falta MediaPipe pose/manos/gestos. | P0/P1 cerrados, licencia/modelos/datasets auditados. | Landmarks normalizados→píxel, oclusiones y visualización opt-in probados. Dibujar esqueletos/líneas no demuestra clasificación de acciones. Sin biometría persistente. |
| ACTION-01 / 4 / P2 | Falta clasificación temporal, caídas potenciales y acciones. Evaluar MMAction2/alternativas. | POSE-01 y revisión comercial/compatibilidad, datasets permitidos. | Secuencias temporales, incertidumbre y revisión humana, alertas sensibles apagadas por defecto, falsos positivos/negativos y límites documentados. No concluir agresión/delito a partir de un frame. |
| UI-01 / 5 / P1 | Existen dashboard/stream/eventos; faltan overlays IA, timeline y búsqueda semántica de eventos. | Contratos/reglas/media estables, Android compilable y permisos coherentes. | Overlays activables, timestamp/edad/estado inferencia, filtros por cámara/tenant, revisión humana y accesibilidad. Pruebas de pantalla y errores backend; sin mostrar secretos RTSP. |
| MULTI-01 / 5 / P3 | Falta aislamiento y planificación multicámara por carga. | VIS-04/05 y modelo/reglas medidos en 1 cámara. | Substream para inferencia/original para evidencia cuando disponible; evaluar 2/4 sin rebasar recursos. Kill/fallo/cámara lenta no degrada otras sin control. Healthchecks y cuotas verificables, no prometer FPS no medidos. |
| HARD-01 / 6 / P0–P1 | Cobertura actual parcial, no hardening de release. | Pases previos completos; integración aislada. | Autenticación/RLS/grants/URLs firmadas/retención/clip con roles reales, carga, cortes de red, RTSP inválido y fallo de modelo. Runner falla ante error inesperado. Backups/restauración y rollback demostrados, sin tocar datos reales. |
| PERF-01 / 6 / P3 | ONNX/aceleración no evaluada. | Baselines comparables y licencias aprobadas. | Benchmark misma fuente/resolución/hardware, precisión equivalente, CPU/GPU/RAM/latencia reales; cambio solo si mejora objetivo acordado y tiene rollback. |
| SUPPLY-01 / 6 / P1 | Sin lockfile/SBOM/CI/licencias verificadas. | Dependencias/modelos seleccionados. | SBOM y versiones/checksums, escáner y revisión de licencias/pesos, CI reproducible con secretos aislados, no deshabilitar firmas/TLS. Runbooks y checklist de release, sin publicación automática sin autorización. |

## F. Orden propuesto y decisiones para revisión

1. Aprobar o ajustar esta auditoría y el backlog (GATE-00). No se inicia implementación mientras se espera.
2. Acordar correcciones P0 de autorización/gateway/API/SQL y validación; pueden requerir una iteración de saneamiento separada antes del pipeline de FASE 1. La auditoría no las autoriza por sí misma.
3. Elegir una única ruta canónica de migraciones y estrategia de drift, sin asumir que la copia de Docker o Supabase coincide con Git. No usar producción para resolverlo.
4. Acordar comportamiento para cámaras personales sin organization_id y permisos de lector/conductor/administrador de flota, tanto en evidencias como configuración y borrado.
5. Proporcionar entorno de integración de prueba sin cámaras personales ni datos reales y fuente de video permitida; resolver SDK/JDK/Gradle. La carencia no invalida los hallazgos estáticos ni las pruebas unitarias, pero limita la validación end-to-end.
6. Solo después, ejecutar historias autorizadas de FASE 1 con límites/flags y demostrar criterios de salida. FASES 2–6 siguen pendientes de sus revisiones, licencias y mediciones.

No se estiman fechas ni rendimiento de IA sin modelo/hardware/dataset definidos. Esta sección refleja el orden propuesto en FASE 0; el avance autorizado se registra a continuación.


## G. Estado al entregar FASE 1 — 2026-10-26 (histórico; ver H)

El usuario autorizó «continua con la fase 1». Se implementó infraestructura optativa y aislada, preservando el camino legado. Evidencia y runbook: [PHASE_1_VISION_INFRASTRUCTURE.md](PHASE_1_VISION_INFRASTRUCTURE.md). Código: `f58e4ad` y `bd76506`. No hay modelos, nuevas migraciones ni despliegue productivo.

| Historia | Estado actual / aceptación restante |
| --- | --- |
| GATE-00 | Autorización recibida para FASE 1; no autoriza FASE 2, merge ni producción. |
| API-01 | Proyecciones y falsos éxitos de revisión corregidos; regresiones estrictas aprobadas. Expiración real Storage/HLS no validada. |
| AUTH-01/02 | Corregidos scopes de grant y separación lectura/mutación en API; positivos/negativos aprobados. Pendiente atomicidad SQL y matriz integral de flota/owner/Storage. |
| AUTH-03 | Pendiente: gateway/playlist/segmentos. Demo nueva sin red ni enlace al gateway productivo. |
| AUTH-04 | Nueva fuente con CIDRs/puertos explícitos, DNS fijado, credenciales rechazadas y errores sin URLs. Pendientes política de egress contra redirects nativos y camino legado. |
| DB-01/02 | Pendientes, sin cambios SQL. La auditoría histórica no se declara resuelta. |
| QA-02 | 86 pruebas aprobadas con fixtures offline versionadas: 41 existentes y 45 nuevas; los errores de producción no se prueban mediante credenciales reales. |
| OPS-01 | Backend/worker construidos y validados en contenedor no root sin red, healthcheck/SIGTERM aprobados. Android e integración Auth/Storage siguen pendientes. |
| VIS-01 | Servicio separado implementado y optativo; startup idempotente por instancia. Pendiente lease/control plane con motor legado; no hay restauración automática de cámaras desde DB. |
| VIS-02 | Captura en subproceso, mailbox fijo, colas acotadas, backoff, watchdog y cierre kill-safe probados con video/streams/fallos. |
| VIS-03 | Contrato v1, schema JSON, scope completo, UTC, cajas y evidencia validados. Pendiente persistencia/idempotencia durable y derivación del scope desde control plane autorizado. |
| VIS-04 | FPS independientes, métricas/health, CPU/RSS, latencias y buffers limitados implementados. No se presume inferencia ni presupuesto multicámara medido. |
| VIS-05 | Video geométrico original, decode real, RTSP local con interrupción/reconexión y demo Docker aprobados. Sin datos personales ni modelos; falta validación de escenario de cámara real autorizado. |

**La salida global de FASE 1 sigue pendiente de cerrar los P0 y revisar integración.** El siguiente incremento debe resolver esos pendientes; no introducir FASE 2 todavía. Los servicios de prueba se detuvieron y la rama de trabajo se conserva para revisión.


## H. Bloqueos corregidos e inicio autorizado de FASE 2

El usuario autorizó «resuelve los bloqueos e inicia la fase 2». Evidencia detallada: [SECURITY_GATE_CLOSURE.md](SECURITY_GATE_CLOSURE.md), [PHASE_2_OBJECTS_AND_TRACKING.md](PHASE_2_OBJECTS_AND_TRACKING.md) y [MODEL_SELECTION_REVIEW.md](MODEL_SELECTION_REVIEW.md).

| Historia | Estado comprobado / pendiente |
| --- | --- |
| DB-01/02 | 010 aditiva y down, directorio canónico único, grants mínimos, runner con assertions y prueba de concurrencia real: aprobados en PostgreSQL desechable. No aplicado en Supabase real. |
| AUTH-01/02 | RPC concede acceso atómicamente, valida actor/cámara/destinatario, bloquea cambios concurrentes; grants pierden acceso tras cambio de org en API/RLS. Owner/admin mutan; grant solo lee. Matriz Storage y configuración owner-only preservada, sin declaración de validación administrada completa. |
| AUTH-03 | Callback autenticado, publicación separada, JWT cámara/scope/exp, proxy por cada recurso HLS, puerto HLS nativo privado y bearer Media3. Smoke MPEG-TS real aprobado. LowLatency/fMP4 no habilitado; Android no compilado. |
| AUTH-04 | Política común CIDR/puertos, DNS fijado, denegación por defecto, URLs/FCM saneados en respuestas/logs. **Egress de native decoder en redes reales sigue como gate de despliegue**, no garantizado por validar el primer destino. |
| VIS-01 | Lease común API/probe/worker, cierre legado y parent-death SIGKILL: pruebas de procesos y Docker root/no-root aprobadas. Solo por host/volumen; multihost requiere otro diseño. |
| VIS-03 | Registro servidor verifica source/owner/org y vigila cambios/fallo de DB; eventos v1 validados y replay rechazado. Eventos reales no van a stdout; persistencia durable/consumo autorizado siguen pendientes de integración. |
| MODEL-01 | Auditoría comparativa realizada antes de integrar. YOLOX_s/OpenCV Zoo Apache-2.0 fijado por commit/hash, licencia/NOTICE en imagen; descarga/hash e inferencia CPU real comprobadas. Ultralytics/ByteTrack no incorporados. |
| DET-01 | Adaptador CPU optativo, clases/confianza/cajas/NMS y límites implementados. Inferencia real sobre geometría negativa comprobada; faltan dataset permitido positivo, precisión/recall/falsos positivos y aceptación de escenarios. |
| TRACK-01 | Tracker IoU temporal propio, trayectorias/conteos de tracklets y límites probados. No ByteTrack ni identidad persistente. Faltan métricas de oclusión, ID switches y conteos sobre secuencias etiquetadas. |
| VIS-04/05 | Benchmark con modelo real 1/2/4 y memoria acotada registrado; cola de grabación drenada por consumidor independiente. No garantiza FPS objetivo multicámara ni calidad semántica. |
| OPS-01 | Backend/Docker y modelo aislado verificados, dependencias sin conflictos. Android tests siguen NO EJECUTADOS por launcher Gradle; no se cambiaron pines/checksums para ocultarlo. |

FASE 2 está iniciada como prototipo de laboratorio; **no cerrada como funcionalidad productiva**. No pasar a FASE 3/acciones/alertas antes de revisar precisión, egreso remoto y los pendientes de integración. No se migraron datos reales ni se hizo merge.

## I. Fase 3 autorizada — primer incremento de reglas

Usuario autoriza validar y continuar fase 3. Implementado motor opt-in por scope con geometría, reglas temporales, horarios, cooldown y deduplicación en memoria. Véase [informe de fase 3](PHASE_3_RULES_AND_EVIDENCE.md).

Pendiente P1: persistencia idempotente de eventos/reglas, API/UI de configuración, conexión segura a evidencias pre/postevento reutilizando clips/retención, pruebas con secuencias permitidas/etiquetadas, métricas bajo carga y reducción de falsos positivos/jitter. Pendientes anteriores Android, egress nativo RTSP e integración Supabase real siguen abiertos. Fase 3 iniciada, no aceptada como completa. Fase 4 no iniciada.

## J. Cierre funcional de fase 3 (2026-10-27)

El incremento I queda sustituido por la integración completa de reglas/eventos/evidencias/API/UI descrita en [PHASE_3_RULES_AND_EVIDENCE.md](PHASE_3_RULES_AND_EVIDENCE.md). Migración reversible 011, configuración con revisión/ACL/RLS, ingestión idempotente con cooldown durable, scopes verificados al guardar/adjuntar/firmar, consumidor y evidencia acotados sobre el carril existente, revisión/protección/retención reutilizadas. Filtros de confianza, observaciones y margen de línea. Sin identidades persistentes ni alertas sensibles automáticas.

Validación: 129 pruebas backend; ocho unitarias Android y APK debug compilado; PostgreSQL desechable + recorrido API/regla/evento/JPEG/MP4/revisión/protección/retención con Auth/Storage locales explícitos. Benchmarks de motor sintético documentados. El despliegue/migración real, integración Supabase administrado, egress nativo RTSP, calidad en vídeos anotados y validación visual en dispositivo siguen como puertas de release. El resultado Android/Docker final figura en el informe. Fase 4 no iniciada.

## K. Fase 4 autorizada e iniciada (2026-10-27)

Primer incremento: revisión fijada de MediaPipe/MMAction2, contratos de landmarks transitorios de cuerpo/manos sin puntos faciales de pose, render OpenCV y señal geométrica temporal posible_hands_raised únicamente de laboratorio/desactivada por defecto. [Informe](PHASE_4_POSES_HANDS_ACTIONS.md). 138 pruebas backend aprobadas; demo con coordenadas sintéticas, sin inferencia real. No cambian captura, API, DB, app ni dependencias de producción.

Pendiente P2: licencias/procedencia de pesos, runtime aislado compatible, extractor real, calidad/asociación temporal y secuencias anotadas; caídas/acciones no implementadas. Los gates P0/P1 de release anteriores no se consideran cerrados por esta demo. Fase 4 iniciada, no completa; fase 5 no iniciada.


## L. Cierre experimental de fase 4 (2026-10-27)

El estado pendiente del incremento K queda sustituido por [PHASE_4_COMPLETION.md](PHASE_4_COMPLETION.md). MediaPipe Tasks CPU aislado con 24 dependencias y bundles fijados por hash, extractor real cuerpo/manos sin puntos faciales de pose, esqueletos, manos levantadas/palma/puño y posible caída temporales con revisión humana. MMAction2 evaluado, no seleccionado. Asociación conservadora por persona/track/scope/frame, flags desactivados, métricas/timeout/backoff/recuperación y límite de memoria. Ninguna señal sensible llega a RPC/FCM/evidencias automáticas. Sin migraciones ni cambios Android/API.

Validación: 154 tests backend, modelos reales positivos de cuerpo/manos, blanco negativo, muerte/timeout y recuperación, benchmark de pose+manos 1/2/4, dos smoke tests del worker (pose solo y combinado con YOLOX), diez secuencias geométricas con un falso positivo semántico explícito. No es precisión/recall natural. Runtime legacy descartado por CVE de Protobuf; entorno final sin él.

Pendiente para release: vídeos autorizados/anotados de gestos/caídas, calidad y asociación con oclusiones/múltiples sujetos, capacidad integral en hardware destino (512 MiB insuficiente), model cards/derechos completos de datasets y gates P0/P1 anteriores. Fase 4 completada como implementación experimental verificable, no aceptación productiva. Fase 5 no iniciada; esperar autorización.

## M. Fase 5 autorizada — búsqueda y resumen paginado (2026-10-27)

Usuario autoriza iniciar fase 5. Primer incremento en [PHASE_5_DASHBOARD_AND_MULTICAMERA.md](PHASE_5_DASHBOARD_AND_MULTICAMERA.md): GET /events con filtros tipo/revisión/periodo, keyset por UTC/UUID, acceso efectivo por solicitud, límite acotado y resumen explícito de página. App Android reutiliza historial/revisión/protección, añade filtros/inicio/siguiente y evita mezclar respuestas/URLs de consultas anteriores. Sin migraciones, dependencias ni activación de análisis.

Backend 165 pruebas aprobadas. Evidencia Android se registra en el informe. Pendientes de fase 5: salud de inferencia autorizada/fresca en app, overlays sincronizados optativos, selección multicámara y estadísticas globales, aislamiento/admisión CPU/RAM y pruebas integrales de carga, substream/original y validación en dispositivo. La implementación de laboratorio de fase 4 no implica aptitud productiva ni cierra gates P0/P1. Fase 5 iniciada, no completada; fase 6 no iniciada.

## N. Cierre funcional de fase 5 (2026-10-27)

El usuario autoriza terminar fase 5. El incremento M queda ampliado por [PHASE_5_COMPLETION.md](PHASE_5_COMPLETION.md): estado de inferencia con scope vigente/TTL, previews privados del frame exacto y overlays optativos en Android, estadísticas de ventana autorizada y selector de cámaras. Fleet aísla procesos por cámara, fija afinidad CPU, admite presupuestos RAM/CPU, observa recursos/health y reinicia grupos propios con backoff. Substream optativo del operador con registro aprobado; evidencia original contemporánea o sin media si no se puede alinear, sin prometer PTS de sensor.

Validado: 172 tests backend, 12 Android y APK compilado; modelos reales CPU con captura sintética 1/2/4, JPEG/MP4 concurrentes con eventos inyectados y sustitutos RPC/Storage locales, muerte/recuperación de una cámara y salud de otra; dos vídeos locales original/substream; contenedor con fuente actual, UID65534/read-only/network none. Objetivo 3 FPS no alcanzado: ~0.57–0.92 FPS efectivos, picos RSS ~576 MiB por grupo; no activar acciones sensibles bajo esos resultados. Datos y límites explícitos en el informe. Sin migraciones/push/merge/producción.

Fase 5 completada como implementación funcional controlada. Gates de release pendientes: nuevo build de imagen (falló por disco), dispositivo/instrumentación, Supabase/PostgREST e índices, equipos RTSP/PTS/egress reales, capacidad sostenida y precisión/condiciones de modelos de fases anteriores. No se reinterpretan como aprobados por esta demo. Fase 6 no iniciada; esperar instrucción.

## O. Fase 6 autorizada — hardening inicial (2026-10-28)

[Informe](PHASE_6_HARDENING_AND_RELEASE.md), [checklist](RELEASE_CHECKLIST.md). Nuevos tests de rechazo anónimo/bearer y privacidad de archivos de dashboard; inventario Python CycloneDX, revisión PyPI, locks CI/tooling y workflow readonly con acciones oficiales por SHA. Hallazgo real pip25.0.1 corregido a26.2 con wheel/licencia/hash revisados; locks retenidos hasta revisión limpia. Runner SQL copia solo fixtures/migraciones, sin checkout/secretos montados.

Validación: 183 backend en venv limpio desde 69 wheels con hashes; 70 distribuciones sin avisos ni errores en snapshot PyPI (no escaneo nativo completo); PostgreSQL desechable/RLS/concurrencia/media/retención/rollback PASS; runtime pose idempotente verificado. Timeout inicial de reconexión registrado, caso aislado y repetición completa pasan; no se declara causa demostrada ni se oculta el fallo.

Pendiente: CI remoto, escaneos OS/nativo/Android y SBOM completo, imagen release por falta de disco, staging administrado, equipo/dispositivo, soak/red/PTS/precisión, backup/restore y aceptación final. ONNX Runtime/GPU solo evaluación posterior al baseline y auditoría; no instalado. Fase 6 iniciada, no terminada ni release aprobado. Sin migraciones/datos reales/push/merge/despliegue.
