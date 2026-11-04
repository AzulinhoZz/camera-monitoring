# Remediación pyasn1 0.6.5 — validación en la nube

Fecha: 4 de noviembre de 2026 (Ciudad de México). Rama:`feat/ai-vision-platform`. Alcance autorizado: revisar/actualizar pyasn1, reconstruir imagen y repetir pruebas/escaneos; usuario eligió validación exclusivamente en la nube. Se conserva el plan maestro y no se inicia otra fase ni se declara aceptación de producción.

## 1. Estado comprobado

**Actualización aplicada y validada; producción continúa NO_GO.** pyasn1 0.6.4→0.6.5 elimina las cuatro coincidencias del paquete en el escaneo de la nueva imagen. PyPI:70 distribuciones,0 afectadas,0 errores. Backend:247 pruebas aprobadas. Nueva imagen construida y smoke de API/inferencia/aislamiento/cierre ordenado PASS. Hallazgos restantes:221, incluidos82 High. Staging sigue bloqueado antes de alcanzar el servicio; no hubo escrituras.

Los recibos están en [pyasn1-remediation-2026-11-04](pyasn1-remediation-2026-11-04/). [Manifiesto actual](PYASN1_REMEDIATION_ACCEPTANCE_MANIFEST.json) y [veredicto](PYASN1_REMEDIATION_ACCEPTANCE_RESULT.json). La revalidación anterior de225 matches permanece histórica en `REVALIDATION_2026_11_04.md`; no se atribuye a esta candidata.

## 2. Inventario, objetivo y alcance

Existía: pyasn1 0.6.4 fijado por hash en locks CI/runtime, preparación de66 wheels revisados y cuatro avisos con corrección publicada en0.6.5. Parcial: `prepare_release_wheels.py` consultaba exclusivamente la revisión histórica de fase6, por lo que cambiar solo el lock correctamente habría fallado por desacuerdo. Faltaba: revisión del artefacto corregido, sincronización de locks/manifiesto, pruebas del decodificador y nueva identidad/SBOM/scan.

Se actualizó una sola distribución y su manifiesto de preparación; se preservaron las otras versiones/hashes y las65 distribuciones runtime. Sin dependencias nuevas, migraciones, cambios en API, Android, modelos, configuración de cámaras o flags de alertas. Las pruebas de teléfono siguen pendientes conforme a la preferencia explícita de validación en la nube.

## 3. Revisión antes de integrar y riesgos

Artefacto oficial: `pyasn1-0.6.5-py3-none-any.whl`, obtenido por TLS desde la URL `files.pythonhosted.org` publicada en el JSON de versión de PyPI. Tamaño y SHA256 comprobados antes de instalar: `4017b0fce125096b8573b39c989fdb1a4b19cf761e683398184550fea0e66587`.

Licencia del wheel revisada:BSD-2-Clause, permite redistribución conservando avisos; copia incluida en `backend/licenses/pyasn1-0.6.5-BSD-2-Clause.txt`, que se incorpora a la imagen. [Revisión de procedencia/licencia/hash](PYASN1_0_6_5_REVIEW.json). No se ejecutó el wheel antes de revisar estos puntos.

Comparación contra el wheel0.6.4 previamente fijado: solo cambian `pyasn1/__init__.py` y `pyasn1/codec/ber/decoder.py`. Se inspeccionaron ensamblado BIT STRING con bytearray, joins de fragmentos OCTET STRING/ANY, conjunto acotado de tipos de tags e `int.from_bytes` para REAL. [Diff revisado](pyasn1-remediation-2026-11-04/ber-decoder.diff). Se utiliza la corrección upstream; no se copia un decoder propio a la aplicación.

Avisos retirados:GHSA-2qm8-x737-gmw5/CVE-2026-119196, GHSA-fm9c-5rcf-2q5p/CVE-2026-119194, GHSA-mm57-4v3p-rchx/CVE-2026-119197 y GHSA-9m75-vc3g-4x39/CVE-2026-119195. Los avisos señalan0.6.5 como corregida. No se afirma que se haya demostrado una ruta explotable desde la API ni se ejecutaron payloads grandes de agotamiento de recursos.

Riesgo de compatibilidad: corrección de comportamiento del decoder ASN.1, usado transitivamente por dependencias de autenticación Google/Firebase. Se verificaron restricciones transitivas con `pip check`, pruebas funcionales y smoke real; no se envió FCM ni se contactaron servicios Google con credenciales reales. Esa integración externa no se presume probada.

## 4. Cambios realizados

- `backend/requirements-ci.lock` y `backend/requirements-runtime.lock`: sustitución exclusiva del pin/hash de pyasn1. `pyasn1-modules` y resto de pins se conservan.
- `docs/ai-vision/RELEASE_PYTHON_REVIEW.json`: snapshot actual de70 distribuciones instaladas, con URLs/hashes de wheels. La revisión histórica de fase6 permanece intacta.
- `backend/scripts/prepare_release_wheels.py`: usa la revisión actual para los wheels del lock; conserva validación de hash/tamaño/host y rechazo de lock/review discordantes. Tooling pip conserva su revisión fijada anterior.
- `backend/licenses/pyasn1-0.6.5-BSD-2-Clause.txt` y `docs/ai-vision/PYASN1_0_6_5_REVIEW.json`: avisos y auditoría del artefacto.
- `backend/tests/test_pyasn1_remediation.py`: cuatro casos acotados de OCTET STRING anidado (longitud definida e indefinida), fragmento BIT STRING no alineado y padding inválido. No usa umbrales de tiempo ni una carga de denegación de servicio.

## 5. Verificación ejecutada

| Comando / comprobación | Resultado |
| --- | --- |
| Instalar con `pip install --no-index --find-links=... --only-binary=:all: --require-hashes -r .../install.lock` | pyasn1 0.6.5 instalado desde wheel revisado; sin resolución remota de otras versiones. |
| `.venv/bin/python -m pip check` | PASS, sin requisitos incompatibles. |
| `build_runtime_lock.py --output .../runtime.lock` y `cmp` con lock versionado | PASS, cierre65 distribuciones, sin paquetes exclusivos de test. |
| `prepare_release_wheels.py --output /workspace/.camera-tools/release-wheels` | PASS,66 wheels verificados. El wheel anterior puede conservarse en caché, pero el nuevo lock solo acepta0.6.5 y su hash. |
| `SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q backend --junitxml=...` | **247 PASS**,5 warnings de deprecación,11.98s. [JUnit](pyasn1-remediation-2026-11-04/backend-tests.xml). |
| Muestra pequeña del mismo OCTET STRING anidado en procesos separados0.6.4/0.6.5 | Antes devuelve bytes de los TLV internos; después el valor lógico `AB`. Wheels verificados, entorno sin credenciales. [Antes/después](pyasn1-remediation-2026-11-04/decoder-before-after.json). No es benchmark de CPU. |
| `release_inventory.py --pypi --output .../python-inventory` | **70 paquetes,0 afectados,0 errores**; snapshot, no certificación absoluta. [Recibo](pyasn1-remediation-2026-11-04/python-review.json). |
| `docker buildx build --platform linux/amd64 --network none --build-context wheels=... -t camera-monitoring-pyasn1:review --load backend` | PASS; dependencias instaladas sin red, solo wheels con hashes y base oficial fijada por digest. |
| `validate_release_image.py --image camera-monitoring-pyasn1:review --model .../yolox_s.onnx --output .../smoke` | PASS: API uvicorn, autorización negativa, inferencia YOLOX, SIGTERM; UID65534, read-only, red none, CapEff0/NoNewPrivs1 y ejecución nativa en tmpfs denegada. [Smoke](pyasn1-remediation-2026-11-04/image-smoke.json). |
| `scan_release_image.py --archive .../candidate.tar --cache .../scanners --output .../scan` | exit1 por **FINDINGS221**, no por fallo de ejecución. DB oficial válida del4 de noviembre, sin ignores/excludes. |
| `staging_preflight.py --expected-project-ref dsjfaizezwlnrtnfooyj --output .../staging-preflight.json` | exit1, BLOCKED en primera lectura; diagnóstico adicional confirma CONNECT403 del proxy. No usuarios/filas/objetos creados. [Preflight](pyasn1-remediation-2026-11-04/staging-preflight.json), [diagnóstico](pyasn1-remediation-2026-11-04/staging-network-diagnostic.json). |

### Artefacto y delta nativo

[Identidad/procedencia](pyasn1-remediation-2026-11-04/artifact.json): commit de código `6a49ec694f1e61bf8c231271b8c6daa4f143baa3`, imagen `sha256:496e636cfbe3c913b3a5a0531ce41e1b131f24b173fcb569d9434b317d198a5d`; archive SHA256 `d5845180ff97715862e8db98c318a7aa4ecfe7b8e89dba800fc2b01b89716b9c`,479,588,864bytes. El archive queda fuera de Git, sin publicación en registry ni despliegue.

[SBOM](pyasn1-remediation-2026-11-04/image.cdx.json) confirma pyasn1 exclusivamente0.6.5. [Scan](pyasn1-remediation-2026-11-04/image-scan.json), [hallazgos](pyasn1-remediation-2026-11-04/image-findings.json), [delta](pyasn1-remediation-2026-11-04/native-delta.json): comparación con la candidata previa usando la misma DB oficial; exactamente4 matches pyasn1 retirados,0 añadidos. Total225→221, High86→82; Medium80,Low12,Negligible47;122 IDs distintos restantes. No se atribuye la reducción a un cambio de base de avisos ni se ocultan otros componentes afectados.

### CI y verificaciones externas

Código enviado a `feat/ai-vision-platform` sin force push ni merge. [Ejecución41928690218](https://github.com/AzulinhoZz/camera-monitoring/actions/runs/41928690218), commit6a49ec6: resultado final y recibos en [CI](pyasn1-remediation-2026-11-04/remote-ci.json). **Resultado final: Android SUCCESS,19 unitarias y Maven0. Backend247 unitarias/build/smoke/SQL/RLS/rollback/restore/PyPI PASS; gate nativo FINDINGS221, job y workflow FAILURE.** [Resumen](pyasn1-remediation-2026-11-04/ci-summary.json), [log de DB](pyasn1-remediation-2026-11-04/ci-database.txt). CI tiene sus propias identidades de imagen/APK; no se sustituyen por hashes locales. Un workflow con native findings nunca se presenta como verde.

La instalación y ejecución en teléfono, integración administrada Auth/RLS/Storage/API, expiración/revocación remota y pruebas con cámaras/vídeos reales siguen **NO EJECUTADAS**. Las comprobaciones anteriores de carga sintética y restore local son históricas salvo repetición explícita en CI; no se presentan como nuevas pruebas de staging. Android no cambió en este parche; sus pruebas se registran separadamente en CI.

## 6. Seguridad y rollback

No cambios en main, datos reales, schema remoto, alertas sensibles ni servicios de pago. Supabase staging conserva autorización explícita del usuario para fixtures propios; el bloqueo de red impidió comenzar y no hay residuos que limpiar. No se pidió volver a compartir claves ni se alteraron TLS, destinos de secretos o reglas del proxy para sortear el bloqueo.

Rollback técnico del parche: revertir su commit y reconstruir con los locks/revisión anteriores; preserva DB/media. **Reintroduce cuatro avisos conocidos de pyasn1**, por lo que no equivale a una candidata aceptable. Conservar esta nueva imagen/identidad separadas de la anterior; no cambiar recibos históricos para hacer coincidir hashes. No restaurar DB ni eliminar evidencias por este cambio de dependencia.

## 7. Commits

`6a49ec6`: pin/hash de pyasn1, licencia, snapshot de revisión actual, preparación y pruebas. Incluye publicación de los commits locales anteriores de preflight/documentación al actualizar la rama remota. La documentación de este parche se entrega en commit separado; no altera los inputs de la imagen ya comprobada.

## 8. Bloqueos y siguiente paso

**NO_GO** por221 matches nativos restantes y gates externos sin cerrar. La corrección de pyasn1 sí queda comprobada en su alcance; no constituye corrección de Debian/FFmpeg/CPython ni aceptación global. Siguiente trabajo: revisar candidatos con fix disponible y artefactos compatibles, reconstruir/escanear cada remediación, y restablecer la ruta HTTPS del entorno a staging para ejecutar fixtures acotados y cleanup propio. Sin dispositivo por preferencia del usuario: no se reclasifica ese gate como PASS. Custodia de claves/Storage/RPO/RTO, hardware/dataset natural y licencias/aprobación operativa siguen pendientes.
