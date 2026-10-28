> **Informe histórico del primer incremento.** El cierre y la evidencia vigente están en [PHASE_4_COMPLETION.md](PHASE_4_COMPLETION.md). Las limitaciones de este informe describen el inicio, no el estado final.

# Fase 4 — inicio: poses, manos y señales temporales de laboratorio

Fecha: 2026-10-27 (America/Mexico_City). Rama `feat/ai-vision-platform`.
Estado: **fase 4 iniciada, no completada**. El usuario autoriza iniciarla; no se despliegan modelos, alertas sensibles ni fase 5.

## Inventario antes de cambios

| Componente | Estado comprobado | Alcance de esta iteración |
|---|---|---|
| Worker / detecciones / reglas | Existen, fases 1–3 | No se modifican captura, inferencia ni contratos de producción |
| Eventos / clips / revisión / retención | Existen y validados en fixture | No se añaden tipos a ingestión, media ni alertas de producción |
| Poses / manos | Faltaban | Contrato transitorio de landmarks de cuerpo y manos, todavía sin extractor real |
| Esqueletos / efectos | Faltaban | Implementación propia de lm_px, esqueleto y línea decorativa OpenCV |
| Gestos temporales | Faltaban | Posibles manos levantadas a partir de landmarks suministrados, solo laboratorio |
| Caídas / acciones / MMAction2 | Faltan | Auditoría inicial; no detector ni checkpoint implementado |
| P0/P1 operativos | Siguen gates de release | Vídeos anotados, dispositivo, Supabase administrado y egress nativo RTSP; no activar P2 sobre cámaras reales antes de resolverlos |

No hacen falta migraciones ni nuevos permisos en esta iteración. No se alteran requirements, Docker, API, Android o activación por cámara. El trabajo se limita a auditoría, contratos, visualización y pruebas sintéticas; no sortea los pendientes P0/P1 declarados en fase 3 para activar un servicio P2 real.

## Auditoría de componentes

Véanse [revisión de MediaPipe/MMAction2](PHASE_4_COMPONENT_REVIEW.md) y [snapshot de metadatos/hashes](PHASE_4_COMPONENT_REVIEW.json). Licencias de código verificadas, pesos y runtime sin aprobar. MediaPipe0.10.21 exige NumPy<2; 0.10.32 es candidato para entorno aislado. Ambos frameworks declaran contrib OpenCV y MMAction2 requiere stack PyTorch/MMCV/MMEngine a cotejar. No se instalan en el backend actual ni se integran pesos sin licencia/procedencia/compatibilidad verificadas.

## Contratos y privacidad

`backend/app/vision/landmarks.py` y `LANDMARK_FRAME_EXPERIMENTAL_V1.schema.json`:

- Scope completo camera/owner/organization, timestamp UTC, secuencia, sesión y model_version.
- Pose body: exactamente 22 puntos con índices 11–32; se excluyen los 11 índices faciales del mapa de pose. Mano: exactamente 21 puntos, índices propios 0–20. No confundir índices de mano con los de cara.
- Máximo cuatro cuerpos y ocho manos por paquete; IDs locales entre 0–199, sin significado de identidad. Unicidad kind/ID, coordenadas finitas acotadas y topología exacta.
- Coordenadas fuera de imagen admitidas en el contrato para no falsear salidas de un extractor futuro, pero se omiten del dibujo/análisis. visibility/presence ausentes son **desconocidas**, no uno por defecto.
- Puntos/IDs no se guardan en DB, evidencias ni logs. No hay reidentificación ni seguimiento entre cámaras.

Antes de un extractor real deberá existir asociación temporal fiable: el orden de poses de un modelo no es por sí solo un ID estable de persona. Ocultación/cambios de orden deben invalidar continuidad; el laboratorio usa IDs sintéticos constantes y no valida ese problema de percepción.

## Dibujo y señal geométrica

`pose_rendering.py`: lm_px convierte normalizados a píxeles válidos y respeta extremos. draw_skeleton valida scope, frame BGR uint8 y dimensiones <=1280×720; dibuja únicamente puntos con presencia/visibilidad conocidas suficientes. Devuelve copia sin alterar el frame original. No dibuja conexiones faciales. draw_energy_line añade brillo decorativo optativo: no clasifica acciones ni aporta evidencia de una caída.

`gestures.py`: HandsRaisedLab está desactivado por defecto y requiere llamada explícita de laboratorio. Para possible_hands_raised exige:

1. Hombros, muñecas y caderas visibles/presentes >=0.6 y dentro de imagen.
2. Caderas por debajo de hombros con separación mínima de 0.1 de altura de imagen, y ambas muñecas al menos 0.05 por encima de su hombro.
3. Al menos tres observaciones durante >=1 segundo, sin huecos >1 segundo. Ausencia/baja calidad/geometría negativa elimina continuidad.
4. Un resultado por episodio, cooldown de 30 segundos por ID local dentro de sesión. Máximo cuatro candidatos visibles y 200 cooldowns; nueva sesión reinicia todo. Cambiar modelo requiere nueva sesión; secuencias/tiempos duplicados o hacia atrás y scope ajeno se rechazan.

La señal incluye model_version, input_quality (mínimo de presencia/visibilidad de entrada, **no** probabilidad de acierto), basis temporal_geometry y pending. No atribuye rendición, amenaza, delito ni necesidad de intervención. Las limitaciones de perspectiva y asociación hacen que siga siendo una heurística sin exactitud real demostrada.

`GESTURE_SIGNAL_EXPERIMENTAL_V1.schema.json` es contrato experimental separado: no se acepta como RuleEvent de fase 3 ni por la RPC de ingestión. No existe flag de producción/RTSP para activar este laboratorio, endpoint, nueva tabla o envío FCM.

## Pruebas y demo reproducible

- `.venv/bin/python -m pytest -q backend --disable-warnings --junitxml=/tmp/camera-phase4/tests.xml`: **138 passed**, cinco advertencias legacy. Las 129 anteriores permanecen, nueve casos nuevos (incluye parametrización). Tests positivos/negativos de cuerpo/manos, exclusión facial, NaN, calidad desconocida, límites, scope, UTC, no mutación, efectos, opt-in, señal temporal, pausa, cooldown, sesión, repetición y cambio de modelo.
- `.venv/bin/python backend/scripts/demo_pose_lab.py --output /tmp/camera-phase4/demo`: genera skeleton.png, energy.png, gesture_signal.json y summary.json exclusivamente desde coordenadas creadas en código. Cero cámaras, modelos, personas o servicios reales. Un resultado provisional en la secuencia de tres frames; desactivado emite cero.
- `PHASE_4_LAB_RESULT.json`: 100 medidas después de warmup del dibujo a 640×360, con tiempos realmente observados. Solo render, **no** latencia de MediaPipe, MMAction2 o detección de acciones. Imagen de demo inspeccionada para verificar el render y la etiqueta sintética.

NO EJECUTADA: inferencia MediaPipe/MMAction2 (no instalados y pesos no aprobados), precisión con vídeos reales, acciones/caídas, carga con modelos, UI/dispositivo y Supabase administrado. No se repiten migraciones ni Android porque no cambian esos módulos; la evidencia anterior de fase 3 sigue siendo histórica.

## Rollback y siguiente incremento

Los módulos de laboratorio no están conectados al entrypoint ni al pipeline de producción. Para retirar el experimento, dejar de ejecutar el script y revertir el commit de esos módulos/tests; sin datos que migrar, secretos que rotar ni SQL de rollback. No hay descargas implícitas en runtime.

Pendiente: seleccionar y auditar pesos concretos, construir adaptador en entorno aislado con hashes, conservar/extraer únicamente cuerpo/manos, resolver calidad de manos y asociación temporal, medir CPU/RAM/latencia y validar secuencias permitidas/anotadas. Solo entonces evaluar gestos adicionales y potenciales caídas usando secuencias y revisión humana. Alertas sensibles permanecen desactivadas y no se inicia fase 5.

## Cierre de la iteración

Commit del laboratorio y sus nueve casos nuevos: `1397da3`, rama `feat/ai-vision-platform`. JUnit final: 138 tests, cero fallos, errores y skips; 12.27 s. `git diff --check` correcto. No se ha hecho push ni merge. La fase 4 continúa pendiente del adaptador/modelos y evaluación real descritos arriba.
