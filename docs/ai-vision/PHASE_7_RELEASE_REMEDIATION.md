# Fase 7 autorizada — remediación y validación de release

2026-10-28, America/Mexico_City. Extensión autorizada por el usuario después de la fase6; el plan maestro original no incluía esta fase. **Iniciada, no completada. Aceptación productiva NO_GO.** No se modifican los criterios originales ni se aprueban excepciones por empezar una fase nueva.

## Inventario y alcance

Existe: API/app/visión, RLS y permisos, evidencias/retención, locks/SBOM, CI remoto, gate estricto con recibos y sandbox reforzado. Parcial: mitigación de exposición a fallos nativos y pruebas administradas. Falta: resolución de200 matches (77 High), staging confirmado, dispositivo, dataset/hardware, recuperación operativa y evidencia faltante de derechos/modelos. Dos bases oficiales alternativas ya probadas no reducen hallazgos. Se conservan candidata e informes históricos de fase6.

Orden de trabajo: corregir entradas explotables/controlables en aplicación; verificar correcciones nativas compatibles; validar staging y dispositivo/calidad/carga; completar operación y repetir gates. Sin nuevas funcionalidades de producto, servicios de pago, producción, merge ni cambios a main.

## Backlog verificable

| Historia | Trabajo | Criterio de aceptación |
| --- | --- | --- |
| R1 — Base64/cursor y límite JWT | Confirmar call paths y formatos ambiguos; corregir parsers propios y limitar entrada antes de crypto | Cursores emitidos conservan roundtrip/paginación/ACL; aliases/padding no canónico rechazados422; tokens normales/expiración/revocación preservados; token excesivo no llega al decoder |
| R2 — componentes nativos | Contrastar source/version/advisory, evaluar distribución/build compatible con hashes/licencias/toolchain revisados | Bibliotecas realmente corregidas y SBOM/scan ligados a nueva candidata; no cambiar .so a mano ni ocultar coincidencias |
| R3 — integración administrada | Staging explícitamente identificado/autorizado, Auth/Storage/PostgREST y drift | Fixtures sintéticos acotados por organización, negativos/expiración/revocación/cleanup propio; sin tocar datos anteriores |
| R4 — dispositivo y calidad/capacidad | Android real/runner, vídeos autorizados/anotados y hardware destino | UI/permisos/TTL/red, métricas por escenario y soak; no inferir exactitud de geometría sintética |
| R5 — recuperación/aceptación | Custodia de claves, Storage+DB, RPO/RTO y documentos de modelos/datasets | Restore aislado medido, permisos/media/protección iguales, CI verde y aprobación explícita tras gates |

## R1 — primer incremento

Antes de editar se verificó el código real: `event_timeline.decode_cursor` llama base64.b64decode con altchars y validate=True; aun así acepta bits de padding no canónicos. Reproducción local con cursor sintético: alias y original decodifican a los mismos bytes y ambos se aceptaban. Los valores después se normalizan UTC/UUID y el scope de cámara se filtra por solicitud; se corrige ambigüedad de representación, sin atribuir una escalación de permisos demostrada.

Se comprobó también `jwt.api_jws._decode_base64url_segment` de PyJWT2.15.1 instalado: ya restringe el alfabeto y compara la recodificación. La reproducción con firma de padding alterada fue rechazada con DecodeError. No se inventa un fallo adicional ni se copia el verificador JWT: se conserva PyJWT y se añade únicamente un límite de8192 caracteres/bytes antes de invocarlo.

Cambios:

- `backend/app/event_timeline.py`: formato URL-safe explícito, entrada string no vacía de hasta512 caracteres y roundtrip canónico antes de JSON. No cambia el formato de encode_cursor ni los filtros/permisos.
- `backend/app/streaming.py`: rechazo de token vacío/excesivo o tipo distinto de str/bytes antes de signing_key/jwt.decode. Los tokens que emite el servicio siguen funcionando; el límite no sustituye límites de body/header del servidor.
- `backend/app/tests/test_release_remediation.py`: alias de padding con bytes equivalentes, entradas mal formadas/alfabeto/tipos, token excesivo antes del decoder y protección de canonicalización ya existente en PyJWT.

Sin dependencias, modelos, migraciones, contratos de DB, cambios Android ni activación de alertas. Riesgo de compatibilidad: clientes que fabriquen cursores no canónicos reciben422; el cursor del servidor sigue siendo opaco y canónico. Tokens emitidos propios son muy inferiores al límite; no se cambia el validador de tokens Supabase externos.

Verificación inicial: `SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q backend --junitxml=/tmp/camera-phase7-tests.xml`: **220 PASS**, cinco warnings,15.69s. Build/smoke/scan de nueva candidata y CI remoto se registran al terminar, no se presumen aprobados.

## Seguridad y operación

R1 mitiga entradas de aplicación relacionadas con avisos de Base64 de Python (CVE-2025-12781/CVE-2026-3446); no parchea CPython ni elimina matches del scanner. FFmpeg/Debian y el resto de avisos siguen requiriendo remediación. La API/worker mantienen sandbox, autorización vigente y privacidad. Para rollback de este incremento revertir sus cambios de código conservando DB/media; no ejecutar down ni borrar evidencias. Un rollback reintroduciría aceptación de alias de cursor y quitaría el límite JWT, y debe evaluarse por ese efecto.

Las escrituras en Supabase siguen pendientes de confirmar un staging aislado. Configurar una clave o autorizar esta fase no identifica ese proyecto como staging. Dispositivo/dataset/hardware y acuerdos operativos continúan pendientes; no se marcan PASS por pruebas sintéticas.

## Nueva candidata local

Implementación `07ab983f8e960522ee6766c0a72b5c03c3ed959b`. Build offline con los mismos65 pins runtime y66 wheels revisados PASS. [Identidad/proveniencia](PHASE_7_ARTIFACT.json), [smoke](PHASE_7_IMAGE_SMOKE.json), [SBOM](PHASE_7_IMAGE_SBOM.cdx.json), [scan](PHASE_7_IMAGE_SCAN.json), [delta nativo](PHASE_7_NATIVE_DELTA.json). La imagen de fase6 se conserva como histórica; no se atribuye su hash a este código.

Imagen `sha256:610ce8886bc3f1fad159304036c98bf9e0ed583d39acd27ea120d24fc6bef4a0`, archive `/tmp/camera-phase7/candidate.tar`, SHA256 `a8d8897d507be3043fde4dd165f7401bb12566094dbee4c41b01bb12599859e4`. No publicada en registry ni desplegada. El tar temporal no entra en Git.

Smoke real PASS: API uvicorn y autorización negativa, inferencia YOLOX CPU, SIGTERM, UID65534/read-only/network none/CapEff0/NoNewPrivs1 y ejecución nativa en tmpfs denegada. En esta ejecución:40 frames recibidos,26 recording/3 inference consumidos, capture_dropped0; un open_timeout inicial con reconexión y posterior salud/inferencia. Se registra la recuperación, sin atribuir una causa demostrada ni presentar esas muestras como benchmark de exactitud/FPS objetivo.

Escaneo con DB válida y recibo ligado a esta candidata: FINDINGS200 (77 High), sin matches añadidos ni retirados. El gate `check_release_readiness.py --manifest docs/ai-vision/PHASE_7_ACCEPTANCE_MANIFEST.json` conserva NO_GO. R1 queda validada localmente como mitigación de aplicación; R2–R5 pendientes. La fase7 no se declara completa.

## CI remoto del incremento

[Workflow40810141627](https://github.com/AzulinhoZz/camera-monitoring/actions/runs/40810141627), commit `07ab983f8e960522ee6766c0a72b5c03c3ed959b`:220 backend PASS, build/smoke e integración SQL/RLS/rollback/restore PASS; seguridad FINDINGS200, workflow FAILURE. [Recibo](PHASE_7_REMOTE_CI.json). Se conserva el fallo de seguridad; R1 no implica aceptación global ni cierre de R2.

## R6 — incremento de producto autorizado

La petición de implementar las recomendaciones añade revisión/priorización/búsqueda móvil, seguridad Android (incluido Guava High corregido), herramientas offline de calidad y recuperación y medición fleet. [Entrega verificable](PHASE_7_PRODUCT_DELIVERY.md), [operación](PRODUCT_OPERATIONS.md), [aceptación pendiente](PRODUCT_VALIDATION_MATRIX.md). Nuevos recibos en `product-evidence/` y `PRODUCT_ACCEPTANCE_MANIFEST.json`; no reemplazan la identidad de los artefactos históricos anteriores. Se conserva NO_GO por native200 y gates externos.
