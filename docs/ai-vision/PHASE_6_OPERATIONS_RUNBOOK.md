# Operación y recuperación AI 2.0 — fase 6

2026-10-28, America/Mexico_City. **Runbook de preparación; no autorización de despliegue.** Estado de aceptación vigente: `PHASE_6_ACCEPTANCE_RESULT.json`. Detener el procedimiento ante NO_GO. No hay objetivo RPO/RTO ni responsable de operación acordados todavía.

## Preparación y evidencia de candidata

1. Verificar rama, SHA de aplicación, digest de imagen, hashes de locks/pesos, SBOM y reporte de vulnerabilidades. Usar el artefacto de `PHASE_6_CURRENT_ARTIFACT.json`; el experimento `PHASE_6_BASE_REMEDIATION_TRIAL.json` fue rechazado y no es una candidata aprobada.
2. Ejecutar `python backend/scripts/check_release_readiness.py --manifest docs/ai-vision/PHASE_6_ACCEPTANCE_MANIFEST.json`. Código 1 significa bloquear. No editar estados a PASS para evitar un fallo ni usar flags de scanner que oculten severidades/wont-fix.
3. Separar staging y producción por proyecto y destino de Storage, no solo por nombre de variable. El proyecto configurado responde a lectura; esa respuesta no acredita aislamiento. Confirmar autorización antes de crear usuarios, cámaras, objetos o migraciones sintéticos.
4. Proporcionar secretos mediante configuración del servidor, nunca app, argumentos CLI, URL de reproducción, reportes o checkout. Config de fuentes RTSP y registro de substream solo en servidor, con permisos mínimos. Modelos se validan por tamaño/hash antes de un parser nativo.
5. Mantener acciones sensibles/pose experimentales desactivadas. Revisar egress real del decoder, CIDR/puertos/redirecciones, presupuesto por cámara y propiedad del lease antes de añadir fuentes remotas. Las demos network none no prueban confinamiento RTSP en una red real.

## Prueba aislada reproducible

Desde raíz del repositorio, con Python3.12 Linux x86_64 y venv preparado desde los locks con hashes:

```sh
SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q backend
SUPABASE_URL= SUPABASE_SECRET_KEY= FIREBASE_CREDENTIALS_PATH= GOOGLE_APPLICATION_CREDENTIALS= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python backend/scripts/validate_database_security.py
python backend/scripts/prepare_release_wheels.py --output /tmp/camera-vision-wheels
```

Los dos primeros comandos son fixtures locales; el runner SQL crea sus contenedores network none, copia SQL sintético y elimina únicamente esos contenedores. El backup cifrado generado tiene clave solo RAM: tras terminar no es un backup reutilizable ni sustituye un servicio de custodia. No pasar DSN reales al fixture.

`validate_release_image.py --help` describe el smoke de una imagen fijada y el modelo revisado; no confundirlo con precisión natural. `validate_vision_rtsp.py` y `validate_gateway_security.py` usan fuentes/usuarios propios de prueba y puertos efímeros. Las instrucciones exactas y resultados ejecutados están en `PHASE_6_PUBLISHED_VALIDATION.md` y `PHASE_6_REMEDIATION_STATUS.md`.

## Salud, degradación y parada

| Señal | Comprobación | Acción conservadora |
| --- | --- | --- |
| API sin health | Consultar endpoint `/health` sin imprimir headers/tokens; separar DB no configurada de API caída | Retener tráfico y revertir candidata de código tras drenaje; no ampliar permisos para recuperar servicio |
| Inferencia sin salud o health antiguo | Health JSON y timestamp; worker <15s, fleet umbral del compose; revisar recursos y reinicios propios | Mantener estado unavailable/stale en dashboard; detener worker afectado si persiste; no presentar overlays antiguos |
| Reconexiones/errores de decoder | Contadores por cámara sin URL/contraseña; integridad de origen y egress | Backoff y proceso aislado; no probar fuentes externas arbitrarias ni sustituir por frame de otra cámara |
| FPS efectivo insuficiente | Comparar inferencia consumida y tiempo real, drops, CPU/RSS contra criterio del escenario | Reducir admisión o desactivar análisis de esa cámara; no activar acciones sensibles con baseline 0.57–0.92 FPS |
| Scope transferido/token inválido | Recalcular autorización efectiva; rechazo de API/media/HLS | Denegar, invalidar preview y revisar grants; no reutilizar firma/cache de otro usuario |
| Modelo corrupto/timeout | Verificación hash/peso, deadline, recuperación y observación de proceso propio | Rechazar modelo y mantener cámara sin inferencia; no descargar sustitutos automáticamente |
| Vulnerabilidad nativa | Reporte completo y advisory del proveedor por versión/source package | Bloquear release, abrir remediación y repetir scan con DB válida; sin excepciones automáticas |

En una demo creada por el operador, parar solo los servicios propios con SIGTERM y sus periodos de gracia (vision-worker 15s, vision-fleet 20s). Identificar contenedor/servicio antes de la parada. Verificar fin del decoder, health stopped y drenaje de clips en curso. No usar `docker compose down -v`, pruning global ni borrar volumen de leases para forzar propiedad. Mantener captura/evidencias existentes y no cambiar retención como recuperación de rendimiento.

## Recuperación operativa a ensayar en staging autorizado

- Antes de cualquier cambio de esquema, inventariar revisiones 001–011 y configuración/exportación de reglas, roles, grants, políticas y objetos Storage. Capturar un punto consistente de DB y media; un dump DB no contiene bytes de Storage. No incluir credenciales de origen en inventarios compartidos.
- Cifrar el backup con herramienta/versión revisada y clave independiente del archivo; verificar hash/inventario. Acordar custodio, almacenamiento del material de recuperación, acceso mínimo, rotación, auditoría y ejercicio periódico. Estos acuerdos están pendientes; no se genera ni publica una clave operativa aquí.
- Restaurar primero en proyecto/cluster nuevo aislado; aplicar roles antes de DB y restaurar objetos Storage con permisos/buckets configurados. Comparar conteos/hashes de filas y objetos, políticas, grants, revisión/protección/retención, permisos positivos y negativos por organización, y JWT/URLs firmadas/expiración reales.
- Medir RPO respecto al último dato consistente recuperado y RTO hasta servicio verificable. No confundir los segundos de ejecución del fixture con RTO de negocio. Acordar umbrales y responsables antes de declarar PASS.
- Confirmar revocación/caducidad de credenciales de prueba y retirar únicamente sus usuarios/objetos/cámaras con inventario previo. No eliminar buckets compartidos, filas anteriores al ensayo ni backups existentes.

## Rollback y cierre

Rollback funcional primero: desactivar persistencia/analítica por los controles existentes, detener/drenar workers propios y restaurar imagen/config anterior conocida. Respetar compatibilidad API/app y fallback unavailable. Mantener DB, clips y evidencias.

Rollback de migración es independiente: `backend/migrations/rollback/011_vision_rules_and_events.sql` elimina configuración/metadata de visión; requiere exportación previa, mantenimiento y autorización concreta. No ejecutar down en producción como sustituto de backup ni revertir 010 para desactivar visión. Los ensayos de rollback/reapply existentes preservan eventos legacy, pero no son autorización para ejecutarlos sobre datos reales.

Cierre exige recibos enlazados a SHA/artefacto exacto, scan válido y sin hallazgos sin resolver o decisión explícita de riesgo, pruebas administradas/dispositivo/calidad/capacidad, backup operativo y aprobación del operador. Ningún comando de este runbook despliega ni concede esa aprobación.
