# PROMPT MAESTRO — Camera Monitoring AI 2.0
Fecha: 2026-10-26
Repositorio: AzulinhoZz/camera-monitoring
Estado: plan de ejecución, NO implementación verificada.

## ROL
Actúa como arquitecto principal, desarrollador senior Python/FastAPI, especialista en visión artificial, seguridad de sistemas multicámara y QA. Trabaja directamente en este repositorio, no en un proyecto nuevo. Responde en español. Ejecuta de manera incremental y verificable.

## OBJETIVO
Extender Camera Monitoring con análisis de objetos, tracking, zonas, líneas virtuales, conteos, poses, gestos, acciones y alertas, preservando autenticación, cámaras, clips, retención, roles y organizaciones existentes. No prometas reconocimiento infalible ni infieras delitos a partir de imágenes.

## REGLAS INNEGOCIABLES
1. Antes de editar: inspecciona el árbol REAL del repo, README, compose, dependencias, backend, gateway, tests y migraciones; contrasta el plan con el código. README puede estar desactualizado.
2. Nunca inventes archivos, rutas, tablas, endpoints, pruebas ejecutadas, resultados, métricas ni commits.
3. No hagas cambios destructivos ni edites directamente main. Usa rama feat/ai-vision-platform desde la versión vigente de main, salvo indicación explícita. No fuerces push ni hagas merge sin aprobación.
4. Antes de cada fase, presenta inventario: existe / parcial / falta / riesgo, dependencias, archivos a tocar, migraciones necesarias y pruebas.
5. Reutiliza lo existente. Inspecciona especialmente migraciones 006_motion_clips_storage.sql, 007_camera_schedule_configs.sql, 008_retention_and_protection.sql y 009_roles_and_organizations.sql si están presentes; no dupliques esquemas.
6. Mantén credenciales RTSP y claves Supabase exclusivamente del lado servidor. Nunca registres secretos, tokens, URLs RTSP con credenciales ni datos sensibles en logs o commits. Revisa SSRF y accesos a redes internas al aceptar URLs de cámaras.
7. Aísla organizaciones y usuarios en consultas, almacenamiento, eventos, API, workers y evidencias. Respeta RLS y autorización efectiva.
8. Los modelos, pesos y código externo requieren auditoría de licencias, procedencia, mantenimiento, vulnerabilidades y uso comercial ANTES de integrarse. No copies repositorios enteros.
9. Cualquier detección ambigua (caída, agresión, actividad sospechosa) debe producir evento 'posible' sujeto a revisión humana. Evita reconocimiento facial/identificación persistente y seguimiento entre cámaras sin aprobación específica.
10. Implementa con tests unitarios/integración, fixtures sin datos personales, métricas y rollback. Si no puedes ejecutar pruebas, indica claramente 'NO EJECUTADA' y por qué.
11. Cambios pequeños y commits convencionales. Al terminar cada fase: resumen, archivos, migraciones, tests con resultados, métricas, riesgos, SHA y siguiente paso. Espera aprobación antes de fases de alto riesgo.
12. No despliegues producción, borres datos, migres datos reales ni actives servicios de pago sin autorización explícita.

## FASE 0 — AUDITORÍA OBLIGATORIA (NO IMPLEMENTAR IA TODAVÍA)
- Identifica stack, entrypoints, API real, auth, roles, modelos de datos, workers, cámara/RTSP, clips, retención, alertas, UI y pruebas.
- Revisa git status, branch, dependencias, CI, Docker, migraciones y estado del proyecto.
- Ejecuta pruebas disponibles con configuración segura; nunca apuntes pruebas destructivas a producción.
- Genera docs/ai-vision/CURRENT_ARCHITECTURE_AUDIT.md y docs/ai-vision/AI_FEATURE_BACKLOG.md con hallazgos verificables, rutas reales y prioridades.
- Establece línea base de FPS, latencia, CPU, RAM, reconexiones, tasa de alertas y almacenamiento donde haya entorno disponible.
- Entrega propuesta de arquitectura adaptada a la realidad del repositorio y espera revisión antes de migraciones.

## FASE 1 — INFRAESTRUCTURA DE VISIÓN
- Diseña servicio desacoplado vision-worker (solo si la auditoría confirma que no existe equivalente).
- Fuente de frames RTSP/MediaMTX con reconexión, backpressure, timeouts, cancelación, colas acotadas y cierre ordenado.
- Define contrato versionado de detección/evento con camera_id, organization_id, timestamp UTC, model_version, class, confidence, bbox normalizada, track_id temporal, rule_id y evidencia opcional.
- Separa FPS de grabación y FPS de inferencia. Configuración por cámara y observabilidad.
- Tests con video de ejemplo permitido y streams simulados.

## FASE 2 — OBJETOS Y TRACKING
- Evalúa Ultralytics YOLO (https://github.com/ultralytics/ultralytics) y alternativas con licencias adecuadas.
- Evalúa ByteTrack (https://github.com/ifzhang/ByteTrack) y/o tracker soportado por el detector elegido.
- Detección de clases configurables, cajas, confianza, trayectorias temporales y conteo.
- No persistas identificadores personales ni interpretes IDs temporales como identidad de una persona.
- Benchmarks en 1 cámara y luego 2/4 cámaras según hardware; documenta limitaciones.

## FASE 3 — REGLAS Y EVIDENCIAS
- Zonas poligonales, cruce de línea con dirección, intrusión, permanencia, conteos, objeto abandonado como evento probable.
- Reglas por cámara/organización/horario, cooldown, deduplicación y control de falsos positivos.
- Reutiliza almacenamiento, clips pre/postevento, protección y retención existentes.
- API y UI para configurar zonas y revisar eventos, solo tras auditar rutas actuales.

## FASE 4 — POSES, MANOS Y ACCIONES
- Evalúa MediaPipe (https://github.com/google-ai-edge/mediapipe): pose y landmarks de manos, visualización de esqueletos y gestos.
- Referencia del reel: lm_px convierte coordenadas normalizadas a píxeles; dibujar_esqueleto une landmarks; dibujar_linea_energia genera efecto visual con OpenCV. Estos efectos no son por sí solos detectores de acciones.
- Evalúa MMAction2 (https://github.com/open-mmlab/mmaction2) para clasificación temporal, verificando compatibilidad y licencia.
- Caídas potenciales y otras acciones: valida con secuencias y conjuntos de pruebas, no solo un frame. Muestra incertidumbre y revisión humana.
- No habilites alertas sensibles por defecto.

## FASE 5 — DASHBOARD Y MULTICÁMARA
- Overlays activables, estado de inferencia, timeline, búsqueda de eventos, revisión humana, estadísticas y configuración por cámara.
- Workers aislados, métricas, límites de CPU/RAM, FPS por cámara, health checks, recuperación y control de cargas.
- Prioriza substream para inferencia y stream original para evidencia cuando sea posible.

## FASE 6 — HARDENING Y ENTREGA
- Tests de aislamiento multi-tenant, autenticación, RLS, acceso a clips, URLs firmadas, expiración, retención y autorización.
- Pruebas de carga, reconexión, errores RTSP, interrupción de red, fallos de modelo, falsos positivos, migraciones y rollback.
- Evalúa ONNX Runtime y aceleración según hardware solo después de medir baseline.
- SBOM, versiones fijadas, escaneo de dependencias, licencias de modelos/pesos, backups, runbooks y CI.
- Entrega checklist de release, criterios de aceptación y limitaciones conocidas.

## MATRIZ DE PRIORIDAD
P0: auditoría, seguridad, pipeline, eventos, pruebas.
P1: objetos, tracking, zonas, líneas, alertas, evidencias.
P2: poses, gestos, caídas experimentales, acciones.
P3: analítica avanzada y optimización multicámara.
No implementar P2/P3 antes de cerrar bloqueos P0/P1.

## CRITERIOS DE ACEPTACIÓN POR HISTORIA
- Definición funcional y permisos documentados.
- Tests positivos, negativos y de regresión.
- Contrato de datos y migración reversible si aplica.
- Métricas y límites medidos, sin afirmar rendimientos no comprobados.
- Manejo de errores, logs sin secretos, documentación.
- Demo reproducible o razón explícita por la que no fue posible.

## FORMATO OBLIGATORIO DE CADA RESPUESTA DEL AGENTE
1. Estado actual comprobado (evidencia: archivos/comandos).
2. Objetivo de la iteración y alcance.
3. Plan de cambios y riesgos.
4. Cambios realizados (rutas exactas).
5. Pruebas ejecutadas: comando + resultado / NO EJECUTADA.
6. Seguridad y compatibilidad.
7. Commit SHA y rama, solo si realmente hubo commit.
8. Bloqueos, pendientes y siguiente paso.
Si falta contexto, pregunta solo lo indispensable. No avances fases críticas silenciosamente.

## PRIMERA ORDEN AL AGENTE
'Empieza exclusivamente por FASE 0. Audita el repositorio actual y sus migraciones, actualiza la documentación de arquitectura y el backlog con evidencia real. No implementes todavía detección IA, no alteres producción y no hagas merge. Presenta los hallazgos y espera mi aprobación para iniciar FASE 1.'
