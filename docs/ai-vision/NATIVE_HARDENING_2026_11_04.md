# Hardening nativo contrastado — 4 de noviembre de 2026

## 1. Estado comprobado

**NO_GO**. Cambio de runtime implementado y probado en `feat/ai-vision-platform`, sin merge, despliegue ni cambios a producción. Fechas de esta entrega en zona del usuario (4 de noviembre); los recibos llevan UTC y algunos corresponden al 5 de noviembre. [Aceptación ejecutada](native-hardening-2026-11-04/acceptance-result.json) y [manifest](NATIVE_HARDENING_ACCEPTANCE_MANIFEST.json).

La imagen local final del código `8539b10d5a2c0cc79ed1c1b30674d1adbd59adce` es `sha256:15e2c0b40177c275b1ef1141071dcebfc95f5ae5f9d62e93c5230621ea37f6ce`. Su archivo de434897408 bytes tiene SHA256 `cf2935ea38d0bd8f5203967b49f3c8fc5130ae9a74b165d4172a713d8f79eae8`. [Identidad](native-hardening-2026-11-04/artifact.json), [SBOM](native-hardening-2026-11-04/image.cdx.json), [scan](native-hardening-2026-11-04/image-scan.json) y [hallazgos completos](native-hardening-2026-11-04/image-findings.json). La imagen independiente de CI tiene su propia identidad; no se demuestra reproducibilidad bit a bit.

## 2. Alcance

Resolver vulnerabilidades nativas disponibles, renovar validación nube y preparar integración sintética en staging autorizado. No agregar funciones, eliminar grabación/FFmpeg, modificar migraciones, activar pose experimental ni tocar datos existentes. Precisión natural, dispositivo y producción no quedan certificados por estas pruebas.

## 3. Cambios y riesgos

Se sustituye Debian/CPython3.12 por base pública Wolfi fijada a `cgr.dev/chainguard/wolfi-base@sha256:771146c2dfc880902a185f060c3db5571473c46b267edd98c3119c83068dfb61`, instalando Python3.13.18 del proveedor. Se conservan las65 versiones Python de runtime;14 wheels cambian de ABI CP312 a CP313 con hash y procedencia revisados. Se conserva tzdata2026f. [Revisión de plataforma y alternativas](NATIVE_PLATFORM_REVIEW.json), [paquetes OS](OS_PACKAGES_REVIEW.json), [revisión Python](RELEASE_PYTHON_REVIEW.json).

Se preparan16 archivos APK fijados por SHA y versión. El índice completo congelado y firmado upstream se conserva porque la autenticación depende del repositorio, no de firmas individuales de cada archivo APK. La comprobación inicial aislada `apk verify` indicó UNTRUSTED y no se utilizó para aprobar nada: la instalación correcta, con índice firmado y keyring del proveedor ya incluido en la base fijada, pasó con `--no-network`, versiones exactas y sin `--allow-untrusted`. [Recibo](native-hardening-2026-11-04/offline-os-validation.json), [log](native-hardening-2026-11-04/offline-os-validation.log). Índice público de7425489 bytes, SHA256 `72f4e7ad6d9560bf2ed730318192b333c2c5579468ee913ca72f74e59c986eff`. No se agregaron claves propias ni se sustituyeron bibliotecas `.so` manualmente.

Alternativas evaluadas: Debian3.13 con APT3.0.4 corregido dejó216 matches y pasó251 pruebas/smoke, pero no se adoptó. La imagen Python predeterminada de Chainguard trae3.15.2 sin wheel compatible de PyYAML6.0.3: [comprobación ABI](native-hardening-2026-11-04/python315-alternative.json). El paquete OpenCV C++ del proveedor no proporciona el contrato Python/FFmpeg requerido. Se mantuvo la distribución OpenCV revisada, con vídeo y grabación funcionales.

Se separó la verificación de integridad YOLOX a un módulo estándar compartido para permitir descargar el modelo desde un host sin OpenCV instalado; hash/tamaño del modelo no cambian. Se reforzó el fixture del timeout de pose: handshake válido y comprobación de que el hijo llegó a arrancar. QA permite ejecutar sólo su fixture temporal; `/tmp` de producción sigue `noexec`.

Riesgo: cambio de distribución y ABI; sólo LinuxAMD64 verificado. Pose experimental conserva su entorno Python3.12 separado. Rollback requiere restaurar Dockerfile, locks, revisión, CI y contextos de la plataforma anterior juntos; conserva sus vulnerabilidades conocidas. No hay migración de datos que revertir.

## 4. Archivos y reproducción

Código: `backend/Dockerfile`, `backend/os-packages/APKINDEX.tar.gz`, `backend/scripts/prepare_os_packages.py`, `prepare_release_wheels.py`, `run_cloud_backend_checks.py`, `download_vision_model.py`, `build_runtime_lock.py`, `release_inventory.py`; `backend/app/vision/model_artifact.py` y `detection.py`; locks, CI y Compose actualizados en47f505a. Pruebas nuevas en `backend/tests/test_os_package_sources.py`, `test_model_download_bootstrap.py`; fixture en `backend/app/tests/test_pose_process.py`.

[Instalador completo ejecutado](native-hardening-2026-11-04/install_cloud.sh): prepara70 wheels para CI y16 APK, construye sin red, verifica/descarga el modelo, ejecuta smoke y regresión aislada. El helper copia únicamente fuente versionada; excluye `.env`, cargas y datos ignorados, y elimina sus propios contenedores/imágenes QA. README contiene los comandos de preparación/build y comprobación.

El skill [cloud-environment-onboarding:setup](skill://plugin_connector_1p_ed5feb9070a08191b08c81c47947bc16/setup/SKILL.md) se usó para guardar instalador e instrucciones probados. Guardado confirmado, `requires_publish=true`; no se cambiaron secretos ni política de red y esto no aplica configuración al runtime. Según la herramienta, para activarlo hay que revisar/guardar los cambios en ajustes del entorno y publicarlo. No se ha publicado desde esta tarea ni se ha probado restauración en una tarea nueva. El instalador exige la fuente revisada: no hace checkout ni sobrescribe `main` si faltan los archivos de esta rama.

## 5. Pruebas ejecutadas

| Comando / prueba | Resultado real |
| --- | --- |
| Instalador completo `bash install_cloud.sh` | PASS; build offline, modelo íntegro, smoke y253 backend; [recibo](native-hardening-2026-11-04/bootstrap-validation.json). |
| `run_cloud_backend_checks.py --image camera-monitoring-cloud:dev ...` |253 PASS,5 warnings, sin red, UID65534, read-only; [JUnit](native-hardening-2026-11-04/backend-tests.xml). |
| CI código8539b10, regresión backend |253 PASS; [JUnit](native-hardening-2026-11-04/ci-backend-tests.xml). |
| `validate_release_image.py --image camera-monitoring-native:review ...` | PASS imagen final: API real/YOLOX/grabación/noexec/caps vacías/NoNewPrivs/SIGTERM; [recibo](native-hardening-2026-11-04/image-smoke.json). |
| CI PostgreSQL desechable | PASS aislamiento/RLS/migraciones/rollback y backup cifrado/restauración en clúster independiente; Auth/Storage sustituidos localmente; [log](native-hardening-2026-11-04/ci-database.txt). |
| CI Android |19 unitarias PASS; job SUCCESS; Maven0 matches. Fallo esperado de endpoint release inseguro es prueba negativa del harness. Sin instrumentación/dispositivo; [resumen](native-hardening-2026-11-04/ci-summary.json). |
| Inventario/advisories Python CI |70 distribuciones,0 afectadas,0 errores de consulta; [revisión](native-hardening-2026-11-04/python-review.json). No cubre bibliotecas nativas. |
| `scan_release_image.py --archive .../release-final.tar ...` | FINDINGS37; exit1 esperado, DB reciente válida, sin ignores. |
| `check_release_readiness.py --manifest docs/ai-vision/NATIVE_HARDENING_ACCEPTANCE_MANIFEST.json` | NO_GO, exit1 esperado. |

CI real [41941333561](https://github.com/AzulinhoZz/camera-monitoring/actions/runs/41941333561): workflow FAILURE únicamente por `Full image inventory and vulnerability gate`; Android SUCCESS y resto de pasos backend PASS. [Metadatos](native-hardening-2026-11-04/remote-ci.json). No se convierte el pipeline rojo en aceptación.

[Carga sintética](native-hardening-2026-11-04/cloud-capacity.json):30s por escala,1/2/4 cámaras, cuota4CPU/3GiB, pose OFF y3FPS configurados. Una cámara2.446FPS/264.30MiB; dos2.394–2.415FPS/530.03MiB; cuatro2.347–2.379FPS/1058.70MiB sumados de grupos. Todas superaron el objetivo provisional2FPS. Existen descartes de inferencia registrados; no es garantía de cero pérdidas. Se ejecutó en imagen trial `68461560…` con el mismo perfil de runtime anterior al refactor estándar final; no se atribuye esta medición independiente a la imagen final. Sin vídeos naturales, hardware destino, RTSP real, pose, soak prolongado ni métricas de precisión. No comparar causalmente con benchmarks históricos de otras cuotas/duración.

## 6. Seguridad y compatibilidad

[Delta completo](native-hardening-2026-11-04/native-delta.json):221→37 matches;82→23 High,13 Medium y1 Low actuales. Reducción neta184 matches, no184 vulnerabilidades distintas demostradas como corregidas. Cambia distribución/proveedor/inventario: salen los paquetes Debian, Python cambia de identidad y se agrega un match SQLite por CPE. No hay filtros, ignores ni VEX para ocultarlo.

Restan34 matches de FFmpeg8.1.1 integrado en OpenCV (22High),2 de Python3.13 (Medium CVE-2025-15367 en poplib y Low CVE-2026-103995 en http.client), y1High `CVE-2026-119586` en `sqlite-libs3.54.1-r0`. Este último describe inyección mediante la salida de `.recover` del CLI al encadenarla con sqlite3. En la imagen final no existe CLI sqlite3 ni símbolo `sqlite3_recover_init` exportado: [sondeo limitado](native-hardening-2026-11-04/sqlite-applicability.json). Aplicabilidad **en investigación**, posible falso positivo por componente; no basta este sondeo para suprimirlo ni certificar SQLite libre de vulnerabilidades.

Se revisó fuente de FFmpeg9.0.2 del espejo oficial: tag firmado verificado por GitHub, objeto `ce8f11b9fac4cd7ccfb41ca7c01bc17f5cda8cc3`, commit `946fcce07b6dcd0331c8cc609192aeff5e1924f8`; archivo SHA256 `c8a74e6eff0d38850403ee8eff3a95721984b45a3cd25f92b8905886571fc1be`. **No compilado ni integrado**. Requiere build compatible de OpenCV, revisión de opciones/licencias LGPL/GPL/no libre y prueba funcional. Último wheel revisado conserva FFmpeg8.1.1. No se declara imposible corregirlo ni terminado este trabajo; tampoco se sustituye una `.so` sin reconstruir/revisar el conjunto.

## 7. Commits y rama

`feat/ai-vision-platform`: `47f505a45433841baf224c074b61cd1603e28943` plataforma/locks/CI/revisión; `0ef6c51ae8b9249d413b3d13dd12e1e5ab694699` bootstrap modelo sin dependencias instaladas; `8539b10d5a2c0cc79ed1c1b30674d1adbd59adce` espacios sin cambio de AST. Fuente final comprobada por CI; documentación se confirma en commit posterior. Main no modificado.

## 8. Bloqueos y siguiente paso

Staging fue autorizado para fixtures sintéticos propios. Preflight volvió a fallar antes de la primera escritura, incluso tras reinicio de entorno: transporte bloqueado por CONNECT403 en el proxy, no rechazo de Supabase ni prueba de clave inválida. [Último preflight](native-hardening-2026-11-04/staging-preflight.json); [diagnóstico CONNECT403 anterior](pyasn1-remediation-2026-11-04/staging-network-diagnostic.json). No se crearon usuarios/objetos/filas: Auth/RLS/Storage/API administrados **NO EJECUTADOS** y no hay fixtures que limpiar. No se enviaron secretos por rutas alternativas para eludir el bloqueo. El borrador ya guardado no corrige por sí solo la política efectiva del runtime.

Prioridades pendientes: reconstrucción compatible y revisada OpenCV/FFmpeg o wheel mantenido corregido; resolver en la plataforma la conectividad HTTPS al staging configurado; entonces ejecutar integración con cuentas propias y cleanup de sus IDs; obtener hardware objetivo y vídeos autorizados/anotados para calibración/test separados y soak. Usuario eligió validación nube sin Android físico: instrumentación no ejecutada. Custodia/rotación/RPO/RTO, Storage administrado, licencias de uso de modelos/datasets y aprobación operativa siguen abiertos. La [matriz](PRODUCT_VALIDATION_MATRIX.md) conserva los criterios externos. No cerrar fase7 ni aprobar producción.
