# Fase 6 — hardening y entrega: primer incremento

Fecha: 2026-10-28, America/Mexico_City. Rama `feat/ai-vision-platform`.
Usuario autoriza «inicia la fase 6». **Fase 6 iniciada, no cerrada. Release no aprobado.** No se despliega, hace push/merge, migra ni consulta producción.

## Inventario previo y alcance

| Área | Estado previo comprobado | Trabajo de este incremento |
| --- | --- | --- |
| Auth / multi-tenant / RLS | Tests API y PostgreSQL desechable; reglas/media y revisión existentes | Regresión completa, nuevas fronteras anónimo/token inválido, SQL/rollback reales aislados. |
| Streams / expiración / retención | Tokens de stream 60 s, media firmada 1800 s, tests de revocación/retención existentes | Mantener comportamiento; no afirmar expiración validada contra Storage administrado. |
| Dashboard privado | TTL y scope de fase 5; faltaba comprobar modo/propietario del archivo leído | Rechazar archivo con permisos ampliados o UID distinto. |
| Dependencias | API con rangos; pose con 24 ruedas fijadas; sin lock CI ni SBOM global | Inventario instalado, revisión PyPI, lock binario para CI y actualización revisada del instalador. |
| CI | No existía `.github/workflows` | Workflow con acciones oficiales fijadas por SHA, sin secretos de producción, permisos de lectura y evidencias. |
| Build / hardware / redes | Build nuevo bloqueado por disco; ~0.57–0.92 FPS en benchmark de fase 5 | Conservar gates abiertos, sin repetir ni reinterpretar esos resultados. |
| Entrega / backups / aceleración | Runbooks parciales por fase | Checklist y criterios de aceptación; evaluación comparativa pendiente, sin integrar ONNX Runtime/GPU. |

Se leyeron plan maestro completo, cierre de fase 5, módulos/auth/streaming/dashboard, requirements, README, Docker/Compose, gateway y migraciones 006–011. Se reutilizan permisos, clips, revisión, protección y retención. No hacen falta migraciones ni cambios Android/modelos en esta iteración. Riesgos: confundir inventario con auditoría exhaustiva, CI no ejecutada remotamente, dependencias nativas/OS fuera del escaneo y gates de producción pendientes.

## Cambios y hallazgos reales

### Instalador vulnerable y snapshot reproducible

La primera revisión de 70 distribuciones detectó avisos públicos para **pip 25.0.1**; se retuvo la generación del lock. Los IDs/aliases están en [PHASE_6_TOOLING_REVIEW.json](PHASE_6_TOOLING_REVIEW.json); registros PySEC/GHSA pueden duplicar un mismo CVE. No se cuenta cada alias como vulnerabilidad independiente.

Se revisó y fijó **pip 26.2**, licencia MIT, wheel universal oficial, tamaño/hash comparados con PyPI y licencia íntegra conservada. No tiene avisos en la consulta de esa versión. Se instaló desde el wheel verificado, sin índice ni dependencias, en los venv de backend y pose. No se actualizaron paquetes funcionales ni pins de modelos. Que exista una versión más nueva no invalida el snapshot revisado; repetir advisories antes de release.

- `backend/requirements-tooling.lock`: pip con SHA256, bootstrap separado del runtime.
- `backend/requirements-ci.lock`: 69 distribuciones instaladas de aplicación/pruebas, versiones exactas y un wheel compatible por paquete con hash publicado. **Solo Python 3.12 / Linux x86_64**. No es un lock para Android, GPU, otros SO o la imagen Docker actual.
- `setup_pose_runtime.py`: instala primero el tooling fijado antes de su lock aislado de pose. Ejecución idempotente aprobada en runtime existente, bundles verificados sin modificar sus hashes. Warnings de caches Matplotlib/fontconfig no escribibles en home: fallback temporal, sin fallo de verificación; no se cambió HOME ni TLS.
- Requirements generales conservan rangos y Docker aún los usa: **reproducibilidad completa de la imagen productiva sigue pendiente**, no se declara resuelta por un lock CI.

### SBOM y advisories

`backend/scripts/release_inventory.py` genera `python.cdx.json` con estructura CycloneDX 1.6 de bibliotecas instaladas: nombre/versión/purl y licencia declarada cuando hay metadata utilizable. No extrae variables, secretos, rutas privadas ni direct URLs. No ejecuta código de distribuciones inspeccionadas. Es un inventario Python de componentes, no un SBOM completo de toda la solución ni un grafo exhaustivo de dependencias.

Con `--pypi`, consulta por HTTPS al host fijo PyPI, identidad nombre/versión, límite de respuesta/timeout y cuatro consultas en vuelo. Registra avisos por versión y errores explícitos; errores o avisos dan salida no cero. `--lock` exige plataforma correcta, revisión sin errores/avisos y wheels con hash; no genera lock si el inventario está incompleto o afectado. Los tests cubren esa negativa y hashes. Sin `--pypi` declara **NOT EXECUTED**, no una aprobación de seguridad.

Resultados: [PHASE_6_PYTHON_SBOM.cdx.json](PHASE_6_PYTHON_SBOM.cdx.json), [PHASE_6_PYTHON_REVIEW.json](PHASE_6_PYTHON_REVIEW.json). Revisión corregida: **70 distribuciones, cero errores de consulta y cero paquetes con avisos en esa fuente**. Los hashes son de wheels publicados, **no verifican los bytes actualmente instalados**. Licencias son metadata, no dictamen legal. Falta escaneo independiente de OS/contenedor, bibliotecas nativas embebidas, Android/Gradle, modelos y advisories no recogidos por PyPI. La estructura del BOM se generó y leyó como JSON; no se afirma validación contra el esquema oficial completo.

### CI y PostgreSQL

`.github/workflows/vision-security.yml` se activa por pull_request, push a main/rama de trabajo o manualmente. No usa pull_request_target ni credenciales persistidas de checkout; `contents: read`, sin secretos reales, tiempo máximo de 15 min y artefactos siete días. Acciones oficiales v7 fijadas a commits inmutables observados mediante ls-remote, runtime Node24 y licencias MIT comprobadas: [PHASE_6_CI_ACTIONS_REVIEW.json](PHASE_6_CI_ACTIONS_REVIEW.json). No se afirma auditoría exhaustiva del JS transitivo.

Pasos: instalar tooling/69 wheels con --only-binary y --require-hashes, pip check, pytest offline, PostgreSQL desechable, inventario/advisories y publicación de artefactos incluso ante fallo. Artefactos limitados a JUnit e inventario, sin imagen/credenciales/config real. **Workflow analizado localmente, NO EJECUTADO en GitHub**: no se ha hecho push. El gate online puede fallar si PyPI no está disponible; no pasa silenciosamente ante consulta incompleta.

`validate_database_security.py` ya no monta el checkout completo en PostgreSQL. Transmite por stdin únicamente migraciones/rollback y tres SQL sintéticos a su contenedor propio sin red. Evita exponer archivos ignorados/secretos y depende menos de rutas del daemon Docker. Conserva imagen fijada, PGDATA tmpfs, nombre único, sin DSN externo y eliminación exclusiva del contenedor propio.

### Fronteras de acceso

`dashboard.py` comprueba además UID propietario y permisos del **archivo** antes de leer: debe ser privado, igual que su directorio. El escritor ya usa 0600. Archivos ampliados se rechazan y la API mantiene unavailable; no amplía acceso ni cambia TTL.

`test_release_boundaries.py` comprueba anónimo y bearer rechazado en reglas, telemetría/previews, eventos, estadísticas, JPEG y clips. No se alcanza lectura de datos y no se expone el diagnóstico privado del proveedor. No sustituye una integración Auth real. Se preservan tests anteriores de expiración JWT, scopes, transferencias, grants, RLS, media, retención y acciones posibles/revisión.

## Validaciones ejecutadas

```sh
.venv/bin/python backend/scripts/release_inventory.py --output /tmp/camera-phase6/reviewed --pypi --lock /tmp/camera-phase6/requirements-ci.lock
/tmp/camera-phase6/clean-venv/bin/python -m pip install --only-binary=:all: --require-hashes -r backend/requirements-ci.lock
/tmp/camera-phase6/clean-venv/bin/python -m pip check
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /tmp/camera-phase6/clean-venv/bin/python -m pytest -q backend --disable-warnings --junitxml=/tmp/camera-phase6/clean-tests.xml
DOCKER_CONFIG=/tmp/camera-phase5-completion/docker-config .venv/bin/python backend/scripts/validate_database_security.py
.venv/bin/python backend/scripts/setup_pose_runtime.py --output /tmp/camera-phase4-completion/runtime-tasks
```

- Venv nuevo en `/tmp`: tooling verificado, **69 wheels fijados instalados con hashes**, pip check correcto. Sin reemplazar el backend ni sus modelos.
- Regresión final en ese entorno limpio: **183 passed**, cinco advertencias legacy, 12.38 s. Once casos nuevos respecto de 172 de fase 5 (seis rutas parametrizadas, permiso de archivo y cuatro casos del generador). Un primer recorrido obtuvo 182 pass y timeout de ocho segundos en reconexión de vídeo; ese caso pasó aislado (1.98 s) y la repetición completa con OMP/OpenBLAS=1 pasó. Se conserva el fallo inicial en `/tmp/camera-phase6/clean-tests.log`; no se ha demostrado su causa ni se ampliaron timeouts o descartaron pruebas. La configuración de CI limita esos pools a uno; seguir observando intermitencia bajo carga.
- PostgreSQL real desechable: matriz RLS/privilegios, configuración/revisión/idempotencia/cooldown/media, recorrido API → regla → evento → JPEG/MP4 → revisión/protección/retención, down/reapply 010/011 preservando datos esperados y bloqueo de cambio concurrente de organización: **PASS**. Auth y Storage son sustitutos locales explícitos en el recorrido. No certifica Supabase administrado ni restauración de backups reales.
- Pose: instalador actualizado idempotente, pip check y ambos bundles verificados. Inventario adicional del venv opcional se registra en el recibo de validación.
- YAML leído y controles estáticos de permisos/steps/SHAs; git diff --check. **NO EJECUTADOS**: GitHub Actions remoto, Android/dispositivo, build Docker nuevo, soak/RTSP externo y escáner nativo/OS. No cambian Android/pesos/aceleradores en esta iteración; las pruebas anteriores siguen siendo históricas.

## Entrega, backups y próximos incrementos

Checklist vigente: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Todo despliegue exige evidencia de cada gate y aprobación específica; esta iteración no aprueba producción.

Backups antes de cualquier migración autorizada: esquema/datos/roles/RLS/triggers, configuración de cámaras/reglas/revisión/protección/retención y objetos privados de ambos buckets. Un pg_dump sin objetos Storage no es backup completo. Cifrar archivos/configuración, acceso mínimo y almacenamiento fuera de Git; no copiar secretos al reporte. Ensayar restauración en entorno vacío aislado, comparar filas/metadatos/objetos, autorización entre organizaciones, clips, retención y URLs nuevas. Registrar RPO/RTO acordados por el operador, no inventar umbrales. Rollback probado de 010/011 no equivale a backup/restore completo.

Evaluación posterior de ONNX Runtime: baseline OpenCV/CPU ya medido en fase 5; comparar mismo ONNX/hash, imágenes permitidas/anotadas, pre/postproceso/NMS, un core por cámara, 1/2/4, captura/evidencia y métricas de exactitud/latencia/RSS/descartes. Auditar runtime/providers/pesos/driver/licencias/vulnerabilidades antes de instalar; no activar GPU ni modificar thresholds para aparentar mejora. Sin hardware/dataset adecuados, marcar no ejecutado. El objetivo de acciones sensibles requiere al menos 2 FPS **efectivos sostenidos**, además de validación semántica, no solo un número configurado.

Próximos incrementos: escaneo independiente OS/nativo/Android y SBOM completo, imagen reproducible/con disco suficiente y smoke de release, soak/red/RTSP y falsos positivos con datos autorizados, restores de backup, validación de dispositivo y checklist final. Gates administrados y de hardware de fases anteriores siguen abiertos.

Rollback de este incremento: revertir commits en orden inverso y retirar workflow si se requiere. El control de archivos privados puede rechazar snapshots mal configurados: corregir UID/modo a los esperados, no ampliar permisos para sortearlo. Venvs son de desarrollo; reconstruirlos desde locks revisados. Volver al instalador vulnerable no es rollback seguro: conservar bootstrap corregido si solo se revierte funcionalidad. Sin cambios SQL ni datos que migrar. Main intacta; sin push/merge/despliegue. Los SHA efectivos se reportan al crear los commits.

## Evidencia del cierre de este incremento

Recibo: [PHASE_6_INITIAL_VALIDATION.json](PHASE_6_INITIAL_VALIDATION.json); revisión de 25 distribuciones del runtime opcional: [PHASE_6_POSE_REVIEW.json](PHASE_6_POSE_REVIEW.json), cero errores/avisos en PyPI. Commits reales: `095e202` controles privados/tooling/fixture SQL y `43a33bc` locks/inventario/CI. Rama `feat/ai-vision-platform`. El commit documental se entrega en el reporte final; no se inventa aquí. La fase 6 sigue abierta según checklist, sin autorización de release.


## Entrega posterior

El estado inicial se amplía con [la entrega técnica candidata](PHASE_6_DELIVERY_AND_ACCEPTANCE.md). Build real, smoke, inventarios y restore local completados; aceptación global continúa NO_GO por los bloqueos documentados.
