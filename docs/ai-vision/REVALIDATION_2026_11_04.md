# Revalidación de seguridad y preparación de teléfono/staging

Fecha: 4 de noviembre de 2026 (Ciudad de México). Rama: `feat/ai-vision-platform`. Solicitud autorizada: renovar el escaneo y preparar una prueba completa de dispositivo y staging. El usuario confirmó explícitamente que el proyecto configurado es staging y autorizó únicamente usuarios/datos sintéticos propios. No se interpreta como autorización para producción, migraciones ni eliminación de datos anteriores.

## 1. Estado comprobado

**Revalidación local terminada; aceptación global NO_GO.** El análisis actual tiene base oficial válida del 4 de noviembre. La integración administrada no pudo comenzar: el proxy rechaza CONNECT con HTTP403 antes de llegar a Supabase. No se crearon usuarios, filas ni objetos; no hay fixtures pendientes de limpieza. La prueba en teléfono no fue ejecutada: no se ha aportado un dispositivo utilizable desde este runtime.

[Manifiesto](REVALIDATION_2026_11_04_MANIFEST.json), [veredicto NO_GO](REVALIDATION_2026_11_04_RESULT.json), [recibos de esta ejecución](revalidation-2026-11-04/). Los reportes y manifiestos de octubre se conservan como históricos.

## 2. Alcance y preparación

Existe: APK debug, 19 pruebas unitarias Android, pruebas backend, inventarios ligados a APK/imagen y matriz de aceptación externa. Parcial: prueba de instrumentación anterior solo verificaba packageName. Falta: dispositivo QA accesible e integración real Auth/RLS/Storage/API. Riesgos: acceso a datos anteriores, envío de credenciales a un target incorrecto, confundir compilación con UI probada o una base caducada con ausencia de avisos.

Se prepararon dos casos instrumentados sobre navegación sin sesión y un preflight HTTPS de staging de solo lectura. No se requieren nuevas dependencias ni migraciones. El código runtime de la imagen y del APK no cambia; no es necesario atribuir un nuevo artefacto de producción a cambios de herramientas/pruebas.

## 3. Seguridad actualizada y delta

Se ejecutó `backend/scripts/scan_release_image.py` sobre el mismo archive de candidata y con los scanners fijados/revisados existentes. Se mantuvieron verificación de integridad, TLS y edad máxima de base de72h; no se añadieron ignores/excludes. La primera advertencia de DB antigua fue seguida por actualización exitosa; el recibo final acredita DB válida construida `2026-11-04T06:20:59Z`.

| Medida | Octubre | 4 de noviembre |
| --- | ---: | ---: |
| Coincidencias del escáner | 200 | **225** |
| Identificadores de vulnerabilidad distintos | 108 | 126 |
| High | 77 | **86** |
| Medium | 66 | 80 |
| Low | 10 | 12 |
| Negligible | 47 | 47 |

El delta compara multiconjuntos de ID de advisory y PURL (o nombre/versión) del paquete:26 coincidencias añadidas y1 retirada, neto+25. No es una regresión de código demostrada: la imagen analizada no cambió. Según metadatos del escáner,24 matches tienen estado `fixed`,133 `wont-fix`,47 `not-fixed` y21 estado vacío; `fixed` identifica candidatos a revisión, no componentes ya corregidos en nuestra imagen. [Delta](revalidation-2026-11-04/native-delta.json), [candidatos](revalidation-2026-11-04/native-remediation-candidates.json), [hallazgos completos](revalidation-2026-11-04/image-findings.json).

Imagen: `sha256:f9b3d4375525918a45c91a536a5521e3547771830b77d73b534015f5e3231491`. Archive SHA256: `d35fae9a0b6de2437a4b31a06f3dbbdbc511a49e0ca7095cd22feed9c6b3fe31`. Se escaneó ese artefacto preservado; no se afirma un build nuevo. [Recibo](revalidation-2026-11-04/image-scan.json).

Android: nuevo `scan_android_dependencies.py` con la misma base válida y APK/inventario/BOM ligados por hashes: **0 coincidencias Maven**. [Recibo](revalidation-2026-11-04/android-scan.json). Excluye certificación de `.so`, dispositivo y runtime del servidor. No hay afirmación de seguridad total.

La consulta PyPI también se renovó: **70 paquetes,0 errores,1 paquete afectado**. `pyasn10.6.4` tiene cuatro avisos: GHSA-2qm8-x737-gmw5 (CVE-2026-119196), GHSA-fm9c-5rcf-2q5p (CVE-2026-119194), GHSA-mm57-4v3p-rchx (CVE-2026-119197) y GHSA-9m75-vc3g-4x39 (CVE-2026-119195). Los avisos indican corrección en0.6.5. [Recibo PyPI](revalidation-2026-11-04/python-review.json). **No se instaló esa actualización ni se afirma que los avisos estén resueltos.** Siguiente remediación concreta: revisar wheel/licencia/procedencia/parche, actualizar locks/hashes y reconstruir/probar/escanear otra candidata. La biblioteca afectada no demuestra por sí sola una ruta explotable desde nuestra API; no se ejecutaron reproducciones de agotamiento de recursos.

## 4. Cambios realizados

- `android/app/src/androidTest/java/com/cameramonitoring/app/SignedOutNavigationSmokeTest.kt`: dos casos instrumentados, welcome→login con campos obligatorios y rechazo local de credenciales vacías; welcome→registro. Usa navegación/composables reales. Requiere instalación QA sin sesión; falla si encuentra sesión, no la borra ni hace login/registro remoto. No arranca MainActivity/FCM; no cubre notificaciones, permisos ni streams.
- `backend/scripts/staging_preflight.py`: compara referencia explícita de proyecto con URL HTTPS sin credenciales/ruta/query/fragmento; únicamente GET de Auth settings y contratos PostgREST con `limit=0`. No sigue redirects para no reenviar credenciales. Reporta errores sin body ni detalles del proveedor; no crea fixtures ni ejecuta migraciones. Su éxito significa `PASS_PREFLIGHT_ONLY`, no aceptación Auth/RLS/Storage.
- `backend/tests/test_staging_preflight.py`: cuatro controles offline sobre target incorrecto, errores sin secretos, solo lecturas sin filas y rechazo de redirects.
- Este informe, recibos y nuevo manifiesto; no se sobrescriben reportes históricos.

## 5. Pruebas y comandos reales

| Comando desde raíz | Resultado |
| --- | --- |
| `SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q backend --junitxml=...` | **243 PASS**,5 warnings,11.87s. [JUnit](revalidation-2026-11-04/backend-tests.xml). |
| `python /workspace/.camera-tools/android/build_project.py :app:testDebugUnitTest --rerun` | BUILD SUCCESSFUL; **19 pruebas aprobadas**, cero fallos. Tarea de tests forzada; no se presenta caché como nueva ejecución. |
| `python /workspace/.camera-tools/android/build_project.py :app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest` | BUILD SUCCESSFUL. App y APK de instrumentación compilados; los2 casos nuevos compilan. [Identidad](revalidation-2026-11-04/android-validation.json). |
| `.venv/bin/python backend/scripts/scan_release_image.py --archive /workspace/.camera-tools/product/candidate.tar --cache /workspace/.camera-tools/scanners --output /workspace/.camera-tools/revalidation-20261104/image-scan` | exit1, **FINDINGS225**, DB válida; resultado de seguridad adverso, no error de ejecución del escáner. |
| `.venv/bin/python backend/scripts/scan_android_dependencies.py --sbom docs/ai-vision/product-evidence/android.cdx.json --inventory docs/ai-vision/product-evidence/android-inventory.json --apk /workspace/.camera-tools/android/project/app/build/outputs/apk/debug/app-debug.apk --cache /workspace/.camera-tools/scanners --output /workspace/.camera-tools/revalidation-20261104/android-scan` | exit0, **PASS_MAVEN_SNAPSHOT**,0 matches. |
| `.venv/bin/python backend/scripts/staging_preflight.py --expected-project-ref dsjfaizezwlnrtnfooyj --output /workspace/.camera-tools/revalidation-20261104/staging-preflight.json` | exit1, **BLOCKED**, transporte falla en primera lectura. Diagnóstico de la ruta: proxy CONNECT403. Ninguna escritura. |
| `ANDROID_USER_HOME=/workspace/.camera-tools/android/user-home /workspace/.camera-tools/android/sdk/platform-tools/adb devices` | No pudo enumerar: intenta crear `/home/agent/.android`, filesystem de solo lectura. No se sobrescribió HOME. No se expone bus USB ni `/dev/kvm`. |
| `.venv/bin/python backend/scripts/release_inventory.py --output /workspace/.camera-tools/revalidation-20261104/python-inventory --pypi` | exit1:70 paquetes,0 errores,1 afectado por4 avisos; lock limpio no emitido. |
| `connectedDebugAndroidTest` | **NO EJECUTADA**: falta un dispositivo accesible. Compilar los APK no acredita que estos casos hayan pasado. |
| Integración administrada Auth/RLS/Storage/API, expiración y revocación | **NO EJECUTADA**: conectividad bloqueada antes de crear fixtures. |
| CI remoto de este incremento, SQL disposable/restore, soak y vídeos naturales | **NO EJECUTADA** en esta revalidación. La evidencia de octubre se conserva como histórica y no se atribuye a una nueva ejecución. |

## 6. Ejecución de dispositivo y staging cuando estén disponibles

### Teléfono/computadora de QA

Usar instalación dedicada y sin sesión, preferentemente emulador nuevo o dispositivo QA con el permiso de su operador. No sustituir una instalación que tenga datos reales; no ejecutar `pm clear`, uninstall, factory reset ni limpieza de preferencias como parte del smoke. Requisitos: JDK25, SDK35/build-tools36, adb operativo y dispositivo API≥26 autorizado por USB. No se necesitan claves Supabase para estos dos casos.

Desde una computadora de QA:

```bash
cd android
# Tener conectado únicamente el dispositivo QA autorizado.
adb devices
bash gradlew :app:connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.class=com.cameramonitoring.app.SignedOutNavigationSmokeTest
```

Conservar reportes JUnit de `app/build/outputs/androidTest-results/connected/` y HTML de `app/build/reports/androidTests/connected/`. Verificar que realmente se ejecutaron2 casos y el serial/versión esperados; cero tests, skips o compilación sola no es PASS. No subir screenshots/logcat con tokens/datos personales. Estos casos no prueban login real, clips, background, notificaciones, TLS o accesibilidad: continuar la [matriz completa](PRODUCT_VALIDATION_MATRIX.md).

### Staging confirmado por el usuario

El destino configurado coincide con el binding guardado de la clave y la política guardada indica red `unrestricted`; por tanto no se diagnosticó ausencia de clave ni se pidió volver a compartirla. Aun así, el runtime recibió CONNECT403. Se necesita restablecer esa ruta HTTPS en la configuración/runtime del entorno y repetir el preflight. Guardar un borrador no demuestra que el runtime ya tenga conectividad.

Tras `PASS_PREFLIGHT_ONLY`, ejecutar la prueba de integración de forma acotada: dos usuarios y organizaciones sintéticos identificados por un run ID único; cámaras/eventos y JPEG/MP4 generados propios; login/refresh, acceso propio/ajeno, revisión/protección, filtros, URL firmada, expiración y revocación. Probar RLS directamente con JWT de cada usuario, además de API; la clave de servicio no demuestra RLS. No enumerar ni modificar objetos anteriores. Registrar IDs creados en un manifiesto privado, limpiar exclusivamente esos IDs en un `finally`, comprobar ausencia al terminar y registrar cualquier limpieza incompleta. No crear buckets, migrar esquema, enviar FCM ni usar RTSP real para forzar el PASS. Si falta esquema/bucket, reportar drift antes de decidir un cambio.

Esta secuencia sigue **pendiente de ejecución**, no es un simulacro de integración ya aprobado.

## 7. Commits y configuración del entorno

Implementación de preparación: `4e1fa1b`, en `feat/ai-vision-platform`; documentación en commit separado. No main/merge/despliegue/migraciones remotas. El runtime de imagen/APK no cambia por el nuevo código de pruebas/preflight.

Se aplicó la habilidad [cloud-environment-onboarding:setup](skill://plugin_connector_1p_ed5feb9070a08191b08c81c47947bc16/setup/SKILL.md) para diagnosticar la conectividad. Se guardó únicamente `start_skill` actualizado con rutas, comandos verificados y bloqueos; no se cambiaron claves, bindings, política de red ni install_script. El tool respondió `saved`, `requires_publish:true`: es configuración pendiente de publicación por el producto, no una corrección de red ya aplicada. La habilidad no exigió una nueva autorización de staging: se utilizó la respuesta explícita del usuario.

## 8. Pendientes y decisión

**NO_GO.** El escaneo se renovó, se comprobó regresión y se preparó un smoke de navegación ejecutable. Falta revisar y corregir pyasn1 y los hallazgos nativos, restablecer la conexión del entorno a staging y ejecutar la matriz administrada/dispositivo; vídeos anotados/hardware destino, recuperación administrada y licencias/aprobación operativa siguen pendientes. No se declara completada una prueba end-to-end ni una mejora de precisión natural.
