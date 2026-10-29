# Fase 6 — validación del entorno publicado

2026-10-28, America/Mexico_City. **La configuración publicada funciona. Aceptación de release NO_GO por hallazgos nativos y validaciones externas pendientes.** Esta actualización sustituye los bloqueos anteriores de conectividad/propagación de secretos como diagnóstico actual; conserva la evidencia histórica.

## Accesos y reconstrucción

SUPABASE_URL y SUPABASE_SECRET_KEY están disponibles. Se validó que el destino HTTPS coincide con el proyecto configurado antes de enviar el apikey exclusivamente a ese host. GET `/auth/v1/settings` devuelve HTTP200. No se imprimieron credenciales ni se consultaron datos de usuarios ni se escribieron filas/Storage. Acceso válido no acredita que el proyecto sea staging: se solicitó confirmación específica antes de fixtures administrados.

GitHub API funciona. Se publicó únicamente `feat/ai-vision-platform` por push normal (sin force); main no se modifica. Primer workflow real: [40797509430](https://github.com/AzulinhoZz/camera-monitoring/actions/runs/40797509430), commit `f6746ad039d6276dca6449539e62a117e9f599c1`. Checkout, herramientas, instalación por hashes, regresión, cierre runtime, imagen+smoke, SQL/RLS/rollback/restore e inventario Python PASS. Gate completo nativo FINDINGS, workflow FAILURE, comportamiento esperado de seguridad. No hay despliegue, publicación de imagen ni servicios productivos afectados.

La nueva instancia perdió los archivos temporales /tmp y el venv apuntaba a una ruta ausente. Se recreó el venv Python3.12 usando locks tooling/CI con hashes, se verificaron los 66 wheels de runtime y se reconstruyó la imagen offline. `BUILDX_CONFIG` se dirige a /tmp porque HOME/.docker/buildx es de solo lectura. No se cambia HOME ni se sobrescriben credenciales Docker.

[Artefacto actual](PHASE_6_CURRENT_ARTIFACT.json): `sha256:fa9f4b309378f501664711203184f416c134e86c3ac6aa0c0bfe20206bd653c9`, tar 479566848 bytes en `/tmp/camera-phase6/candidate.tar`. No se afirma reproducción bit a bit del artefacto histórico. Los archivos históricos siguen describiendo la candidata anterior; el manifest de aceptación apunta ahora a esta reconstrucción.

## Validación actual

- `SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q backend --junitxml=/tmp/camera-phase6/published-final-tests.xml`: **190 PASS**, cinco warnings, 13.71 s. Secretos vacíos para las pruebas de regresión. Android no se repitió; conserva sus doce pruebas históricas, sin dispositivo.
- `prepare_release_wheels.py`: **66 wheels** verificados por hash/tamaño y origen revisado. Build Docker offline linux/amd64 PASS.
- `validate_release_image.py` sobre imagen real: PASS HTTP uvicorn, health, acceso anónimo denegado, DB sin configurar denegada, inferencia YOLOX CPU y SIGTERM. UID65534, read-only, network none; 105 frames, 70 recording/7 inference consumidos, cero capture drops en esta ejecución. Fixture sintético, no certificación de precisión.
- `release_inventory.py --pypi`: **70 paquetes, cero avisos y cero errores de consulta**. No sustituye al escaneo nativo.
- Syft/Grype revisados se descargaron y verificaron otra vez. SBOM de imagen y reporte completos versionados. La primera respuesta latest antigua se descartó; el actualizador oficial obtuvo DB v6.1.10, construida `2026-10-28T06:23:30Z`, checksum oficial y status valid=true. Se conserva límite 72h. [Recibo DB](PHASE_6_GRYPE_DB_STATUS.json).
- Primer scan local falló porque acquire truncaba un ejecutable Grype en uso. Se corrigió el reemplazo con archivo temporal y rename atómico, sin cambiar checksum/versiones. Regresión comprueba que un lector abierto conserva el inode antiguo y el nuevo binario tiene contenido/modo correctos. Repetición local completa y primer workflow remoto coinciden: **200 matches**.

## Hallazgos y siguiente remediación

[Reporte íntegro](PHASE_6_NATIVE_FINDINGS.json), [triage por componente](PHASE_6_NATIVE_TRIAGE.json): **200 coincidencias sobre 108 identificadores**, 77 High, 66 Medium, 10 Low, 47 Negligible. Son coincidencias de scanner pendientes de contraste con advisories/condiciones de explotación, no 200 CVEs únicos confirmados explotables. Estados de corrección informados: 20 fixed, 112 wont-fix, 47 not-fixed, 21 sin estado.

FFmpeg 8.1.1 está embebido en las bibliotecas del wheel OpenCV (`opencv_python_headless.libs`), no en un apt independiente. Incluye 34 matches; hay correcciones informadas en 8.1.2/8.1.3 y 9.x. Actualizar apt no sustituye esos bytes. Se consultó PyPI: la versión actual 5.0.0.93 de opencv-python-headless sigue siendo la última publicada y no declara advisories Python; esto no elimina los hallazgos FFmpeg. No se inventa un wheel corregido ni se reemplazan manualmente .so de distinta ABI.

Otros matches afectan Python/binario y bibliotecas Debian (glibc, util-linux, ncurses, GCC, zlib, systemd, SQLite, entre otras); la mayoría no anuncia fix para la distribución detectada. Siguiente trabajo técnico: verificar cada advisory y backport con su proveedor, seleccionar y auditar una base/runtime o build OpenCV compatible que incluya correcciones, actualizar los locks/revisión correspondientes y repetir regresión+RTSP+native smoke+escaneo. No se filtran wont-fix, CPEs ni severidades para conseguir verde. No se elimina captura/decodificación ni se migra Python sin validar compatibilidad de wheels/modelos.

## Gates que siguen abiertos

CI ya puede ejecutarse; no está verde por hallazgos de seguridad. La repetición del commit que corrige el runner terminó: [40797915828](https://github.com/AzulinhoZz/camera-monitoring/actions/runs/40797915828), SHA `eefe3ba5d66f1ad998434086bc138caccd90d517`, funcional PASS y seguridad FINDINGS (200), workflow FAILURE. [Recibo](PHASE_6_REMOTE_CI.json). No se afirma CI verde. Managed staging requiere confirmación del proyecto, Android requiere dispositivo, carga/precisión requiere hardware y vídeos autorizados/anotados. Backup operativo aún requiere Storage real, custodia de claves y RPO/RTO; revisión completa de modelos/datasets/licencias sigue pendiente. Los roles y restore entre clústeres de la prueba anterior conservan su evidencia local; no se reinterpretan como pruebas administradas.

No se solicita aprobación de despliegue mientras estos gates fallen. Ninguna credencial se agrega a Git; no se cambia main, no hay merge ni despliegue.
