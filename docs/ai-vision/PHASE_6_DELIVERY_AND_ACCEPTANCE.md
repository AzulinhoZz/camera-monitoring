# Fase 6 — entrega técnica candidata y aceptación

2026-10-28, America/Mexico_City. Rama `feat/ai-vision-platform`. **Entrega técnica local realizada; aceptación global NO_GO. La fase 6 no puede certificarse íntegramente cerrada ni autoriza producción.** No se modifica main, no hay push, merge, migraciones productivas ni despliegue. El informe inicial conserva su evidencia histórica.

## Cambios y reproducción

- Imagen linux/amd64 con base Python por digest, 65 paquetes runtime fijados por hash, pip 26.2 y usuario 65534. Se descargan 66 wheels revisados con `python backend/scripts/prepare_release_wheels.py --help`; Compose usa el contexto `wheels` (`VISION_WHEELHOUSE`). Docker instala sin red. Build offline real completado; no se demuestra reproducibilidad bit a bit de un segundo build.
- `build_runtime_lock.py` calcula cierre de dependencias/extra markers desde el snapshot revisado; separa pytest del runtime. `validate_release_image.py` prueba la imagen construida, no una copia de fuentes.
- `scan_release_image.py` usa Syft 1.55.0/Grype 0.121.0 revisados y verificados por SHA. CI readonly incorpora lock/build/smoke, SQL/restore y gate nativo que falla cerrado. `check_release_readiness.py --manifest docs/ai-vision/PHASE_6_ACCEPTANCE_MANIFEST.json` retorna 1/NO_GO con bloqueos reales; nunca despliega.
- Backup AES-GCM-256 de fixture DB y JPEG/MP4, restore en DB nueva del mismo cluster desechable, comparación de filas/RLS/grants (excluye solo nombre del catálogo), revisión/protección y acceso de dueño/extraño. Ciphertext alterado rechazado. Clave solo RAM y descartada: no es un backup operativo reutilizable; globals incluidos, roles no restaurados en cluster nuevo.
- Inventario Android desde grafo Gradle offline y hashes APK/.so; no cambia resolución. ONNX Runtime CPU evaluado fuera del entorno productivo; se conserva OpenCV.

## Evidencia real

| Validación | Comando / resultado |
| --- | --- |
| Backend | `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest backend -q` — 188 PASS, 5 warnings, 13.34 s; log/XML en `/tmp/camera-phase6/delivery-final-tests.*`. |
| Android | Gradle offline `:app:testDebugUnitTest --rerun :app:assembleDebug` — BUILD SUCCESSFUL, 12 unitarias; sin dispositivo. Init script `android/gradle/release-inventory.gradle`: 286 filas, 143 artefactos distintos. |
| SQL | `backend/scripts/validate_database_security.py` — PASS migraciones/idempotencia/RLS/concurrencia/media/retención/rollback 010/011 y restore cifrado. `/tmp/camera-phase6/restore-validation-final.log`. |
| Imagen real | `validate_release_image.py` — PASS HTTP uvicorn/health, anónimo denegado, DB sin configurar denegada, inferencia YOLOX CPU y SIGTERM. UID65534, read-only, network none, caps vacías, recursos acotados. 113 frames recibidos, 75 recording/8 inference consumidos, 0 capture drops en ejecución final. |
| RTSP | `validate_vision_rtsp.py` — PASS publicación, decodificación, interrupción y recuperación; 2 conexiones/1 reconexión/17 frames. Fixture consume colas al final: 9 drops recording y 2 inference; no prueba captura sin pérdidas. |
| Gateway | `validate_gateway_security.py` — PASS MediaMTX real, publicación autenticada, proxy HLS playlist/variant/segment y rechazo anónimo/token inválido. Auth/usuarios sintéticos. |
| Imagen SBOM | Syft sobre Docker archive real — 2991 componentes (2829 archivos, 153 bibliotecas, 8 aplicaciones, 1 OS). `PHASE_6_IMAGE_SBOM.cdx.json`. |
| Vulnerabilidades nativas | Grype ejecutado: BLOQUEADO al obtener `https://grype.anchore.io/databases/v6/latest.json` (403 Forbidden). No significa cero CVEs. Android/Maven/nativos tampoco certificados. |
| CI remoto | NO EJECUTADA: `gh auth status` falla con GH_TOKEN inválido. Workflow versionado y validado localmente; no se publican credenciales. |

[Identidad y hashes del artefacto](PHASE_6_ARTIFACT.json), [proveniencia](PHASE_6_BUILD_PROVENANCE.json), [smoke](PHASE_6_IMAGE_SMOKE.json), [restore](PHASE_6_RESTORE.json), [inventario Android](PHASE_6_ANDROID_INVENTORY.json). Logs y tar/gzip están en `/tmp/camera-phase6`, almacenamiento temporal del entorno. Imagen archivada, después retirada del daemon para recuperar espacio; solo recursos propios eliminados. `docker load -i /tmp/camera-phase6/camera-monitoring-phase6.tar.gz` permite revisión local. Archivo gzip 161696702 bytes; hash en recibo. No imagen publicada ni firmada.

## Evaluación ONNX Runtime

Versión 1.31.1, licencia MIT y wheel/hash/procedencia revisados antes de ejecutar; instalación aislada `--no-deps` en /tmp, sin cambio de requirements ni runtime de aplicación. CPU única, mismo YOLOX y pre/postproceso; dos warmups y diez muestras por engine/fixture. Dos fixtures permitidos (geometría negativa y fotografía pública NASA) produjeron 0/1 personas, con concordancia geométrica/confianza dentro de 0.01. No constituye precisión natural.

| Fixture | OpenCV p50/p95 ms | ONNX CPU p50/p95 ms |
| --- | --- | --- |
| Geometría | 567.66 / 964.95 | 226.67 / 267.24 |
| Imagen pública | 476.51 / 1343.67 | 192.10 / 222.00 |

RSS combinado 378912768 bytes, ambos engines en el mismo proceso: no comparación de memoria exclusiva. CPU provider solamente; GPU NO EJECUTADA por ausencia de hardware. Retener OpenCV hasta escaneo nativo, validación de dependencias completas, vídeos representativos y pipeline en destino. [Medición](PHASE_6_ONNX_EVALUATION.json).

## Bloqueos de aceptación y operación

1. DB oficial Grype accesible y reciente; escaneo completo del artefacto, Android/Maven/nativos, resolución de hallazgos y licencias/model cards/datasets.
2. Credencial GitHub válida para ejecución remota y branch protection; no basta YAML local.
3. Proyecto Supabase explícitamente autorizado como staging, Auth/Storage/PostgREST reales, dispositivo/emulador y cámaras/red/PTS/egress autorizadas. La URL histórica no se asume staging.
4. Dataset autorizado/anotado, calidad por escenario y soak/capacidad en hardware destino. El baseline anterior 0.57–0.92 FPS no satisface acciones sensibles de 2 FPS; permanecen experimentales y desactivadas.
5. Backup operativo con custodia/rotación de claves, restauración en cluster nuevo/Storage y RPO/RTO acordados; aceptación explícita del operador después de resolver gates.

Runbooks existentes siguen vigentes; no rotar credenciales ni restaurar/borrar datos reales como parte de este ensayo. La pregunta sobre recursos externos continúa sin respuesta. [Checklist](RELEASE_CHECKLIST.md) y [manifest](PHASE_6_ACCEPTANCE_MANIFEST.json) mantienen bloqueos; no se inventan excepciones ni autorización de despliegue.

## Revisión de configuración y commits

Compose combinado validado con `.env.example` y secretos ficticios (symlink temporal retirado), sin iniciar servicios. YAML revisado: nueve pasos, permisos contents:read y acciones fijadas por SHA; JSON y `git diff --check` válidos. Implementación y revisiones: commit `0ae8188`. Evidencia unitaria versionada: `PHASE_6_BACKEND_TESTS.xml` y `PHASE_6_ANDROID_TESTS.json`.

Actualización posterior: [resolución de bloqueos](PHASE_6_BLOCKER_RESOLUTION.md), restore entre clústeres e importación offline Grype preparada; aceptación global sigue NO_GO.

Actualización tras publicar entorno: [validación real y hallazgos nativos](PHASE_6_PUBLISHED_VALIDATION.md). Conectividad y secretos disponibles; Supabase solo lectura HTTP200, CI remoto ejecutado. Scan nativo FINDINGS (200 matches); NO_GO continúa.
