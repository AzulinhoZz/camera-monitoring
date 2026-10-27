# Fase 3 — reglas y evidencias

Estado: iniciada, implementación incremental del motor; fase completa **pendiente**.
Fecha de referencia del trabajo: 2026-10-26 (America/Mexico_City).
Rama: `feat/ai-vision-platform`. Sin despliegue ni cambios en main.

## Inventario antes de implementar

| Área | Estado comprobado | Evidencia / decisión |
|---|---|---|
| Objetos/tracking | Existe prototipo CPU y tracks IoU temporales | `backend/app/vision/pipeline.py`, `tracking.py`; calidad semántica y vídeos anotados pendientes |
| Zonas | Existe para movimiento | `backend/app/zone_store.py`, procesamiento en `backend/app/motion_detector.py`; no sustituir por reglas nuevas |
| Horarios | Existe evaluador de movimiento | `backend/app/schedule_evaluator.py`, migración 007; conservar semántica antigua; nuevo motor valida zona IANA explícitamente |
| Eventos/revisión | Existe API autenticada | `backend/app/events.py`; lectura, revisión humana, evidencia y clip |
| Evidencias/clips | Existe infraestructura | `evidence_uploader.py`, `clip_recorder.py`, migraciones 006/008: bucket privado, pre/postevento, protección y retención |
| Reglas sobre objetos | Faltaba | Nuevo motor sin escritura externa |
| Persistencia/configuración API/UI | Falta integración de reglas | No usar el fallback local de ZoneStore como persistencia fiable de nuevas reglas |
| Riesgos | Siguen abiertos | Android sin toolchain validado, confinamiento de egress RTSP, calidad del tracker y prueba con vídeos permitidos |

Revisión del plan maestro completa. La suite de regresión valida código en fixtures; no certifica rendimiento semántico ni conexiones reales a Supabase. La autorización del usuario permite iniciar esta fase; no implica cerrar esos pendientes ni desplegar.

## Alcance implementado

`backend/app/vision/rules.py`: contratos inmutables, coordenadas finitas normalizadas, polígonos simples de 3–32 vértices, líneas finitas y dirección positiva/negativa según producto cruzado. Se usa el centro de la caja. El borde del polígono se considera dentro. La entrada inicial en una zona cuenta como intrusión; no representa una conclusión legal.

Reglas explícitamente desactivadas por defecto: intrusión, permanencia, cruce de línea, umbral de objetos visibles y **posible objeto abandonado**. Esta última significa solamente centro estacionario durante un intervalo: no identifica al propietario ni demuestra abandono. No permite clase person. Todos los resultados requieren revisión humana.

Horarios IANA, días 0=lunes hasta 6=domingo; ventanas nocturnas atribuyen las horas posteriores a medianoche al día de inicio. Cooldown compartido por regla/cámara para limitar volumen, no por persona. Conteo emite al pasar de debajo del umbral a alcanzarlo; no mide personas únicas. Permanencia/estacionariedad emite una vez por episodio; salir, perder observación o moverse reinicia según tipo. Huecos mayores de 2 segundos reinician estado temporal. Frames vacíos eliminan los tracks ausentes inmediatamente.

Deduplicación por sesión/tiempo: timestamps deben aumentar estrictamente dentro de la sesión. ID de evento determinista por sesión, regla, instante y track. Reiniciar worker reinicia estado y cooldown: no ofrece exactamente-una-vez durable. La línea conserva el último lado no nulo para atravesar puntos sobre la línea; no hay filtro de histéresis contra jitter. Cooldown limita, pero no elimina, falsos positivos.

Límites: 32 reglas por cámara, 100 detecciones por frame, estado solo de tracks visibles y un cooldown por regla; máximo 4 cámaras del worker existente. No añade modelos, paquetes ni pesos. No crea identidades persistentes.

`config.py`: reglas en configuración confiable del operador, mismo camera/owner/organization obligatorio; requieren vision_enabled. `pipeline.py`: agrega `rule_events` a lote interno de laboratorio sin cambiar DetectionEvent v1. Configuración sin reglas conserva comportamiento anterior. No se añaden posiciones a logs de RTSP; el CLI sigue prohibiendo emit-detections para RTSP.

## Evidencias, API y UI: siguiente integración pendiente

No se conectan todavía los eventos nuevos a Supabase, FCM, uploader ni clip recorder. Tampoco se inicia una segunda captura. El carril recording existente del CLI drena frames; aún no proporciona evidencias de reglas. No se promete clip/snapshot cuando evidence es null.

Reutilizar `camera_events` y sus rutas de revisión, buckets motion-evidence/motion-clips y protección/retención. Antes de activar escritura será necesario contrato durable e idempotente, autorización del scope actual antes de escribir, validación de prefijos de objetos y coordinación de buffers pre/post sin colas/hilos sin límite. Migración reversible para configuración/metadata solamente si el diseño revisado lo necesita; **ninguna migración nueva en esta iteración**. La UI Android requiere build reproducible y controles de permisos para configurar reglas antes de habilitar edición.

## Validación y reproducción

Desde raíz: `.venv/bin/python -m pytest -q backend --disable-warnings --junitxml=/tmp/camera-phase3-tests.xml`.

Pruebas sintéticas sin datos personales ni red: scope cruzado, timestamps, sesión, duplicados, límites, geometría, horario nocturno, cooldown, reentrada, permanencia, movimiento de objeto, dirección de línea/segmento finito, umbral y adaptación del pipeline. Las regresiones existentes cubren movimiento, clips, retención, API y aislamiento con fixtures. Resultado final registrado al pie tras ejecución.

No se repiten benchmarks de inferencia porque no cambian modelo ni captura. No se han medido latencia/CPU del motor bajo carga, precisión de reglas, falsos positivos ni cambios de ID en vídeo real. Android, migraciones remotas y revisión visual UI: **NO EJECUTADA** en esta iteración. Sin acceso a cámaras/servicios de producción.

## Rollback

Retirar rules de la configuración desactiva su procesamiento; ninguna configuración existente las incluye. Revertir commit de motor restaura el lote previo sin regla. No hay datos nuevos ni rollback SQL que ejecutar. No iniciar fase 4 antes de resolver los pendientes P0/P1 y nueva autorización.

Resultado: **114 passed, 5 warnings in 12.91s**, sin fallos. Las 102 pruebas anteriores permanecen; 12 casos nuevos. Advertencias existentes de TestClient/on_event. `git diff --check` sin errores. JUnit temporal: `/tmp/camera-phase3-tests.xml` (no versionado).
