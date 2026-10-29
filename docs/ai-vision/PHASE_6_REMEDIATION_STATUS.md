# Fase 6 — remediación y estado de cierre

2026-10-28, America/Mexico_City. **No se puede certificar el cierre completo ni la aceptación productiva: NO_GO.** Esta es la entrega verificable del incremento autorizado, sin reinterpretar hallazgos ni requisitos pendientes como aprobados.

## Inventario de la iteración

Existe: captura/inferencia/roles/media y módulos de fases previas, locks/SBOM, ensayos de backup/restore, CI remoto y candidata funcional. Parcial: auditoría de dependencias nativas y operación administrada. Falta: resolución de hallazgos nativos, staging confirmado, dispositivo, dataset/hardware representativo, recuperación operativa y aprobación final. Riesgo principal: librerías nativas procesan medios; sandbox, hash de modelo y pruebas sintéticas no eliminan sus vulnerabilidades.

Archivos de código tocados: `backend/scripts/scan_release_image.py` y `backend/tests/test_release_delivery.py`. No hay migración nueva ni modificación del runtime de aplicación, Dockerfile o dependencias aprobadas. Cambios de documentación y recibos de evaluación enumerados debajo.

## Trabajo realizado y resultado

1. Releído íntegramente `MASTER_PROMPT_AI_2_0.md` y contrastado con código, Compose, dependencias, migraciones, CI, pruebas y runbooks existentes. Se conserva main y no se mezclan fases nuevas.
2. Evaluada la última base oficial Python3.12 slim/Trixie por digest, mismo cierre de 65 dependencias y build offline: **200 matches, cero retirados/cero añadidos** frente a candidata. Rechazada como remediación, no se cambia Dockerfile por una mejora no demostrada. [Recibo](PHASE_6_BASE_REMEDIATION_TRIAL.json).
3. Evaluada variante oficial Python3.12.16 slim/Bookworm por digest, fuente Docker oficial por commit/hash, mismos wheels: build y smoke real PASS, pero **305 matches frente a 200**. Rechazada. [Recibo](PHASE_6_BOOKWORM_REMEDIATION_TRIAL.json). No se mezclan sus resultados con la identidad de la candidata retenida.
4. Descargado y parseado el tracker oficial Debian completo (87,085,315 bytes; SHA en recibo). Source package obtenido de upstreams del SBOM, no adivinado por nombre del binario: **159/159 matches Debian con estado open para Trixie, cero consultas sin correspondencia**. Minor/nodsa/postponed no se convierten en corrección. [Triage](PHASE_6_DEBIAN_ADVISORY_TRIAGE.json). Los otros 41 matches pertenecen a FFmpeg y Python binarios.
5. Refuerzo del gate: no basta exit0 y `matches=[]`. Se exige `descriptor.db.status.valid=true`, ausencia de error y timestamp con zona, no mayor de 72h ni futuro >1h. Un reporte incompleto/antiguo/inválido continúa BLOCKED. Pruebas negativas de base ausente, inválida, con error, antigua o futura; caso válido vacío positivo.
6. Runbook consolidado: [operación y recuperación](PHASE_6_OPERATIONS_RUNBOOK.md), parada/drenaje, señales/fallos, egress, aislamiento, custodia y restauración DB/Storage, RPO/RTO pendientes y rollback sin borrar evidencias. No se inventa una política operativa aprobada.

## Pruebas ejecutadas

| Comando / destino | Resultado real |
| --- | --- |
| `SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q backend --junitxml=/tmp/camera-phase6/remediation/tests.xml` | **195 PASS**, cinco warnings, 17.66s; `PHASE_6_BACKEND_TESTS.xml`. |
| `docker build --platform linux/amd64 --network none --build-context wheels=... -f .../Dockerfile ...` y `scan_release_image.py` sobre nueva base Trixie | Build/SBOM PASS, seguridad FINDINGS 200; no adoptada. |
| Mismo proceso sobre Bookworm y `validate_release_image.py` | Build y smoke PASS (uvicorn, anónimo denegado, inferencia, SIGTERM, UID65534/read-only/network none), seguridad FINDINGS 305; no adoptada. |
| Workflow remoto [40802151569](https://github.com/AzulinhoZz/camera-monitoring/actions/runs/40802151569), SHA `a205a22c0ab91796c0e506772b2d90d5ed5127e9` | Regresión/build/smoke/SQL/RLS/rollback/restore/inventario PASS; gate nativo FINDINGS200; workflow FAILURE. `PHASE_6_REMOTE_CI.json`. |
| `check_release_readiness.py --manifest docs/ai-vision/PHASE_6_ACCEPTANCE_MANIFEST.json` | Código1, NO_GO. No es fallo de ejecución inesperado ni aprobación de release. |
| Dispositivo, staging con escrituras, dataset natural/hardware destino | **NO EJECUTADAS**: recursos/autorización específicos no disponibles; Supabase previamente solo lectura HTTP200. |

Los fallos de seguridad esperados no se silencian con `|| true`. Las ejecuciones anteriores de RTSP, gateway, ONNX CPU, multicámara y restore entre clústeres siguen acreditadas por sus recibos; no se afirman como nuevas ejecuciones de esta iteración. No se usa el número de pruebas de backend como prueba visual Android o exactitud.

## Entregables del plan y límites

| Requisito de fase 6 | Evidencia / estado |
| --- | --- |
| Auth, multi-tenant, RLS, media, expiración y retención | Suites backend y SQL controladas PASS; Supabase administrado aún pendiente |
| Carga/reconexión/RTSP/modelo/falsos positivos/rollback | Pruebas y benchmarks controlados de fases3–6; límites naturales/hardware y falsos positivos documentados, sin certificación |
| ONNX Runtime/aceleración tras baseline | Evaluación CPU realizada, comparación documentada, runtime sin cambio; GPU NO EJECUTADA por ausencia de hardware |
| SBOM y versiones fijadas | Python/imagen/Android/modelos y locks versionados; no confundir inventario con ausencia de vulnerabilidades |
| Escaneo y licencias | Escaneo ejecutado, FINDINGS; licencias/procedencia revisadas, condiciones/model cards/datasets y distribución pendientes |
| Backups, runbooks y CI | Restore sintético cifrado entre clústeres y roles PASS, runbook entregado, CI remoto ejecutado; operación administrada y CI verde pendientes |
| Checklist, aceptación y limitaciones | Manifest, resultado NO_GO, checklist, recibos y este estado de cierre; aprobación no solicitada mientras fallen gates |

## Lo necesario para el cierre completo

- Remediar o contrastar con evidencia de proveedor los matches restantes; una excepción requiere decisión concreta del responsable, no una supresión automática. La última base oficial y Bookworm ya fueron probadas y no ofrecen mejora. FFmpeg vive dentro del último wheel OpenCV publicado: actualizar apt no cambia esos bytes; sustituir .so a mano no valida ABI. Cualquier build nativo propio exige procedencia/licencias, toolchain fijada, política de mantenimiento y repetición integral antes de adoptarlo.
- Confirmar que el proyecto Supabase configurado es staging aislado antes de crear/eliminar fixtures. La configuración segura del secreto no prueba esa condición y no autoriza escrituras productivas.
- Proporcionar dispositivo/runner Android, vídeos anotados autorizados y hardware objetivo para pruebas de calidad/capacidad/egress. No se generan métricas de aceptación a partir de figuras geométricas.
- Acordar custodia/rotación de claves y RPO/RTO; ensayar recuperación de Storage administrado/DB nueva y conservar recibo. Completar la evidencia faltante de uso/licencias de modelos/datasets.

No hay una corrección segura demostrada que convierta estos requisitos en PASS en el entorno actual. La fase no se marca completa para satisfacer una etiqueta. Candidata retenida e identidad en `PHASE_6_CURRENT_ARTIFACT.json`; todo cambio ha quedado en la rama de trabajo, sin merge, force-push, despliegue, servicios de pago ni modificación de datos reales.
