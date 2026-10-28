# Fase 4 — cierre de implementación y validación controlada

Fecha del informe: 2026-10-27 (America/Mexico_City). Rama `feat/ai-vision-platform`. El usuario autorizó completar fase 4. **Implementación experimental terminada; no certificada para producción. Fase 5 no iniciada.** Este documento sustituye el estado pendiente del primer incremento; sus informes se conservan como historial.

## Inventario y alcance

Antes de completar: existían captura aislada, objetos/tracking, reglas/evidencias y revisión API/Android de fases 1–3; fase 4 solo tenía contratos, dibujo y manos levantadas con coordenadas suministradas. Faltaban extractor real, runtime compatible, procedencia de pesos, asociación, gestos de mano, secuencias de caída y medición con modelos. Riesgos: dependencias nativas incompatibles, licencias de pesos, memoria, continuidad de sujetos y falsos positivos. No se necesitaban migraciones, nuevos endpoints, permisos ni cambios Android/Docker.

Ahora existen extractor CPU de cuerpo/manos, esqueletos y efecto decorativo, candidatos temporales `possible_hands_raised`, `possible_open_palm`, `possible_closed_fist` y `possible_fall`; integración explícita por cámara, aislamiento, métricas y recuperación. No son inferencias de intención ni clasificación temporal entrenada. Las señales están separadas de RuleEvent, de la RPC, de FCM y de evidencia automática. El dashboard corresponde a fase 5, no se añade silenciosamente.

## Selección, licencias y dependencias

La evaluación de MediaPipe y MMAction2 está en [PHASE_4_COMPONENT_REVIEW.md](PHASE_4_COMPONENT_REVIEW.md). MMAction2 v1.2.0, commit `4d6c93474730cad2f25e51109adcf96824efc7a3`, código Apache-2.0: evaluado, no incorporado. No se aprueba un checkpoint ni dataset de acciones; compatibilidad PyTorch/MMCV/MMEngine y derechos de pesos requieren evaluación independiente. El plan exige evaluarlo, no instalar ambos motores.

Se selecciona **MediaPipe Tasks 0.10.32** (commit `8317ba78778738ba90a521e7e4580a2ba0129c81`), Apache-2.0, en un venv separado Linux x86_64 / Python 3.12. El backend conserva sus dependencias y OpenCV headless; el hijo usa contrib OpenCV 5.0.0.93, NumPy 2.5.4 y Pydantic 2.14.1. `requirements-pose.lock` fija 24 wheels con SHA256; instalador explícito `--only-binary --require-hashes`, `pip check`, rechazo de paquetes extra. [PHASE_4_RUNTIME_REVIEW.json](PHASE_4_RUNTIME_REVIEW.json) conserva versiones, hashes, licencias declaradas y snapshot de advisories PyPI sin avisos para esas versiones. **No es un análisis exhaustivo del código nativo.**

Se rechazó el runtime Solutions 0.10.21: su restricción Protobuf <5 conduce a 4.25.9 con CVE-2026-0994 / GHSA-7gcm-g887-7qv7 sin versión corregida admisible. No se deja instalado en el entorno final. El wheel 0.10.21 se usa únicamente como archivo ZIP de procedencia de cuatro TFLite, nunca como runtime ni código importado en la solución final.

[PHASE_4_BUNDLED_MODELS_REVIEW.json](PHASE_4_BUNDLED_MODELS_REVIEW.json) registra hashes, tamaños, licencia distribuida Apache-2.0 y código fuente fijado. `build_pose_tasks.py` extrae exclusivamente pose detection/full y palm detection/hand full del wheel oficial verificado. Añade metadatos de normalización de los grafos oficiales fijados: pose detector [-1,1], los otros [0,1]. Usa los helpers de 0.10.32; comprueba que todos los buffers de tensores conservan exactamente sus bytes. No entrena ni modifica pesos. Bundles ZIP deterministas:

| Artefacto derivado | Bytes | SHA256 |
| --- | ---: | --- |
| pose_full.task | 9398078 | c1492ead320c87471d9ae324ee00d1e057636522e991d339ff8f07e90982d4aa |
| hand_full.task | 7819594 | e5fe265a93d7f530428a4b22f230598c3655de527c12deed889514bc890d0508 |

El worker verifica ambos hashes antes de cargar modelos; nunca descarga implícitamente. Licencias íntegras en `licenses/`. Las model cards externas de ai.google.dev/GCS/Kaggle no fueron accesibles (403); la revisión verifica distribución/procedencia, no resuelve todas las condiciones de datasets de entrenamiento ni certifica aptitud comercial del escenario. Revisar esos extremos antes de distribuir/desplegar. No se incorporan modelos, imágenes ni wheels al repositorio.

## Arquitectura, seguridad y semántica

- `pose_backend.py`: proceso nativo CPU, un cuerpo/dos manos; recibe frames acotados por mmap/socket privado, sin red de aplicación, claves ni URL heredadas. Parent-death SIGKILL y timeouts externos. El proceso no constituye un sandbox de syscalls: sigue requiriendo egress/contenedor de despliegue adecuado.
- `pose_process.py`: un hijo por cámara, una petición en vuelo, mensajes <=64 KiB, frames <=1280×720, memoria compartida fija, timeout/startup acotados, terminate/kill/wait, backoff y cierre de recursos propios. Respuesta validada por owner/org/camera, sesión, secuencia, UTC y versión. No almacena puntos ni identidades.
- Contratos experimentales **1.1**: dimensiones y `quality_basis`. Pose exporta solo índices 11–32, con presencia/visibilidad reales; nunca índices faciales. Manos con 21 puntos y calidad desconocida (`None`, detector_presence_only), sin inventar confianza perfecta. El renderer solo dibuja manos sin scores con opt-in explícito.
- `actions.py`: requiere una sola persona detectada y un solo cuerpo, mismo scope/sesión/frame/UTC, intersección corporal suficiente y track temporal de objetos. Ambigüedad, oclusión, huecos >0.75 s, cambios de track/modelo/sesión o resultado obsoleto invalidan continuidad. El orden de salida de MediaPipe no se convierte en identidad. No hay seguimiento entre cámaras.
- Palma/puño: geometría 2D ajustada por aspecto, >=3 muestras durante >=0.6 s; solo una mano asociada y continuidad de muñeca. Caída: postura erguida estable, descenso rápido de caderas, torso horizontal y postura baja sostenida >=1 s con puntos fiables. Cooldown 30 s. Todo es `possible`, `pending`, base temporal_geometry. `input_quality` es calidad de entrada, no probabilidad de acción; puede ser desconocida.
- Flags `pose_enabled`, `hand_gestures_enabled`, `fall_candidates_enabled` son false por defecto. Gestos/caídas requieren pose + objetos explícitos y >=2 FPS configurados; esto no garantiza FPS observado. No se habilitan alertas sensibles. Los candidatos solo se exportan con el diagnóstico local `--emit-detections`, prohibido para RTSP; no se incorporan a la persistencia existente.
- `__main__.py` preserva autorización de scope para RTSP, ofrece evidencia de reglas antes de la inferencia de pose y mantiene el consumidor independiente de grabación. Añade salud/latencia/RSS/contadores del hijo. No se usan Supabase, FCM, cámaras reales ni migraciones en estas pruebas.

## Pruebas reproducibles y resultados reales

Desde la raíz, con el venv backend preparado:

```sh
.venv/bin/python -m pytest -q backend --disable-warnings --junitxml=/tmp/camera-phase4-completion/tests.xml
.venv/bin/python backend/scripts/setup_pose_runtime.py --output /tmp/camera-phase4-completion/runtime-tasks
.venv/bin/python backend/scripts/download_pose_fixture.py --kind body --output /tmp/camera-phase4-completion/astronaut.png
.venv/bin/python backend/scripts/download_pose_fixture.py --kind hand --output /tmp/camera-phase4-completion/tfjs-pinned-hands.jpg
PYTHONPATH=backend .venv/bin/python backend/scripts/validate_pose_runtime.py --python /tmp/camera-phase4-completion/runtime-tasks/bin/python --fixture /tmp/camera-phase4-completion/astronaut.png --hand-fixture /tmp/camera-phase4-completion/tfjs-pinned-hands.jpg --output /tmp/camera-phase4-completion/validated-final
CAMERA_LEASE_DIRECTORY=/tmp/camera-phase4-completion/capture-leases PYTHONPATH=backend .venv/bin/python -m app.vision --config backend/vision-pose.example.json --pose-runtime-python /tmp/camera-phase4-completion/runtime-tasks/bin/python --duration 6 --health-file /tmp/camera-phase4-completion/worker-health-final.json
```

- Backend: **154 passed**, cinco avisos legacy, 13.46 s. Regresión de fases anteriores y casos nuevos: aislamiento, hash alterado antes de carga nativa, timeout/proceso muerto, memoria insuficiente, configuración, asociación, continuidad, caída positiva y negativos, gestos sin scores inventados.
- Instalador final: ejecutado, `pip check` correcto y bundles verificados. No cambia el venv backend.
- Validador nativo: **PASS**. Siete warmups positivos de cuerpo, dos manos con 21 puntos cada una; blanco negativo; recuperación tras muerte y timeout reales; rechazo cross-tenant. Secuencia de recorte de mano real repetido produce un candidato palma `pending` con calidad desconocida y asociación suministrada por el ensayo.
- Diez secuencias generadas: diez checks geométricos correctos, **un falso positivo semántico conocido** (acostarse rápido voluntariamente). No son diez vídeos ni una estimación de precisión. Puño/manos levantadas y caída se verifican con geometría controlada; no hay demostración de sensibilidad en acciones naturales.
- Integración combinada YOLOX + pose: salida 0 sobre vídeo local derivado del fixture NASA; 12 frames inferidos por ambos motores, 78 de grabación consumidos, cero descartes de grabación y cierre ordenado. La persona parcial de ese fixture no satisface la asociación corporal fiable: las 11 muestras no obsoletas quedan sin asociación y no producen señales. No se presenta como positivo end-to-end de caída. Diez descartes de inferencia bajo carga confirman backpressure; no garantiza 3 FPS integrales. Recibo de ambos smoke tests: [PHASE_4_WORKER_VALIDATION.json](PHASE_4_WORKER_VALIDATION.json).
- Worker pose sintético: salida 0, snapshots saludables durante ejecución, 14 frames inferidos, tres descartes de inferencia por arranque, un resultado obsoleto rechazado, **57 frames de grabación consumidos y cero descartes de grabación**, colas vacías/cierre ordenado. `healthy=false` final significa detenido, no fallo del smoke.

Fuentes permitidas y sus límites en [PHASE_4_FIXTURE_REVIEW.md](PHASE_4_FIXTURE_REVIEW.md). Datos medidos completos: [PHASE_4_RUNTIME_VALIDATION.json](PHASE_4_RUNTIME_VALIDATION.json). Artefactos gráficos locales bajo `/tmp/camera-phase4-completion/validated-final/`, sin versionar imágenes de personas.

| Cámaras/hijos | Latencia p50 lote secuencial ms | FPS por cámara | Suma RSS hijos MiB |
| --- | ---: | ---: | ---: |
| 1 | 50.25 | 19.86 | 351.69 |
| 2 | 104.59 | 9.26 | 705.76 |
| 4 | 270.31 | 3.88 | 1413.34 |

Seis lotes calientes por tamaño, CPU compartida; **solo pose+manos**, excluye captura, YOLOX, evidencias y DB. RSS sumada, no PSS; no es prueba de capacidad integral. La simultaneidad del smoke puede afectar la medida. El contenedor original de 512 MiB no queda cualificado: guard conservador exige 768 MiB por cámara de pose +256 MiB si hay objetos y rechaza cgroup conocido inferior. Ausencia de límite conocido no demuestra capacidad. Medir hardware destino y ajustar recursos/FPS antes de uso.

NO EJECUTADAS en este cierre: precisión/recall en vídeos naturales de caídas/gestos, integración Supabase administrado, cámaras de producción, UI/dispositivo de fase 5, MMAction2/checkpoints y escaneo nativo exhaustivo. No se repiten SQL/Android: sin cambios a esos módulos, evidencia histórica en fase 3. No se declaran resueltos gates P0/P1 de release por estas pruebas.

## Operación, rollback y cierre

El ejemplo activa solo extracción sobre fuente sintética; no gestos/caídas. Un despliegue real sigue requiriendo autorización, egress, recursos, model cards y validación anotada/humana. No se migra, despliega, hace push/merge ni modifica main. Para retirar el runtime desactivar los tres flags y quitar `--pose-runtime-python`; para revertir código, revertir los commits de este cierre en orden inverso. No hay datos nuevos que migrar.

El borrador del entorno añadió destinos opcionales ai.google.dev, storage.googleapis.com y www.kaggle.com para auditoría (conservando los anteriores). Guardar el borrador no aplica red: persisten 403 en esta sesión. La instalación reproducible implementada usa PyPI y el fixture fijado GitHub. La publicación del entorno requiere revisión/guardado en su configuración; no se realizó aquí y no garantiza restaurar commits locales.

Pendientes de aceptación operativa: vídeos autorizados/anotados, falsos positivos/negativos por escenario, asociación bajo oclusión/múltiples personas, hardware y presupuesto integral, condiciones completas de modelos/datasets y gates de release anteriores. **Fase 4 cerrada como implementación experimental verificable; no como detector de emergencias certificado. Esperar instrucción antes de fase 5.** Commit de implementación verificado: `d4fdb2b` en `feat/ai-vision-platform`. El commit de esta evidencia se entrega en el reporte de Git al finalizar.
