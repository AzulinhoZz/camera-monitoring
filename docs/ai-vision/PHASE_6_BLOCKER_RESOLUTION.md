# Resolución de bloqueos de fase 6

2026-10-28, America/Mexico_City. **NO_GO global**. Se resuelven limitaciones técnicas locales; no se convierten dependencias externas en aprobaciones ficticias.

## Resuelto y probado

El ensayo de restore ahora crea un segundo contenedor PostgreSQL independiente, network none, memoria 384 MiB, CPU 1 y tmpfs 256 MiB, con la imagen previamente fijada. Restaura `pg_dumpall --globals-only` (omite únicamente `CREATE ROLE postgres;`, rol bootstrap existente), compara atributos de roles no internos (excluye solo OID, identificador local de cada clúster), restaura `pg_dump -Fc` y compara filas, RLS y grants. Verifica dueño/extraño, revisión/protección, JPEG y diez frames MP4. Cifrado AES-GCM, rechazo de alteración y clave solo RAM siguen vigentes. Ambos contenedores propios se eliminan al terminar, incluido error. No acepta DSN ni targets de operador.

La prueba usa datos generados y archivos locales. No prueba Supabase Storage, custodia de claves ni recuperación operativa; no establece RPO/RTO aceptables. El recibo actualizado está en `PHASE_6_RESTORE.json`; el informe de entrega anterior conserva los resultados de su ejecución histórica.

## Vía offline preparada para Grype

`scan_release_image.py` acepta `--db-archive` y `--db-sha256` juntos. Verifica formato de digest, tamaño máximo 1 GiB y hash de todos los bytes antes de importar con el Grype revisado; luego desactiva actualización online y mantiene el límite de edad 72 h. El checksum debe proceder de metadatos oficiales obtenidos por un canal de confianza. Calcular un digest local de una descarga desconocida no autentica su origen.

Ejemplo, con rutas y digest oficiales reales que debe aportar el operador:

```sh
.venv/bin/python backend/scripts/scan_release_image.py \
  --archive /tmp/camera-phase6/camera-monitoring-phase6.tar \
  --cache /tmp/camera-phase6/final-scan-tools \
  --output /tmp/camera-phase6/offline-image-scan \
  --db-archive /ruta/oficial/vulnerability-db.tar.zst \
  --db-sha256 DIGEST_SHA256_OFICIAL
```

Validación de integridad: caso positivo y rechazos de digest ausente/incorrecto pasan. Importación de una base real y escaneo offline completo: **NO EJECUTADOS**, no se dispone de esa base. No altera el resultado bloqueado del escaneo previo.

## Bloqueos externos comprobados de nuevo

| Gate | Evidencia actual | Recurso necesario |
| --- | --- | --- |
| Grype nativo | Tanto grype.anchore.io como toolbox-data.anchore.io y api.github.com devuelven `Tunnel connection failed: 403 Forbidden`, también tras permiso de red concedido para este turno | Habilitar acceso HTTPS oficial o aportar base oficial reciente con checksum de confianza |
| CI remoto | `gh auth status` falla; GH_TOKEN existe pero es inválido | Renovar credencial mediante secretos del entorno con acceso al repositorio; no pegar tokens en chat |
| Staging administrado | SUPABASE_URL y SUPABASE_SECRET_KEY ausentes | Referencia explícita de proyecto de staging autorizado y credencial por canal seguro; no asumir staging por URL histórica |
| Android dispositivo | Sin /dev/kvm ni adb ni dispositivo autorizado | Dispositivo conectado o emulador/runner con capacidades necesarias |
| Carga y precisión | Sin dataset anotado autorizado ni hardware destino | Vídeos/etiquetas con derechos de uso, escenarios, capacidad objetivo y hardware accesible |
| Backup operativo | Restore entre clústeres ya probado; Storage/custodia/RPO/RTO pendientes | Destino aislado autorizado, política de claves y objetivos operativos acordados |
| Licencias | Inventarios y revisiones existentes; falta evidencia completa de derechos/model cards/datasets | Documentación de procedencia/derechos faltante y revisión de condiciones del uso previsto |

No se usa un proyecto real para suplir staging. No se intenta extraer otras credenciales ni eludir el proxy. No se instala un emulador sin aceleración con el disco actual casi lleno como sustituto de una validación de dispositivo. El usuario recibió una solicitud de referencias de recursos externos y configuración segura de credenciales.

## Verificación

- `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q backend --junitxml=/tmp/camera-phase6/resolution-tests-final.xml`: **189 PASS**, cinco warnings, 13.21 s. Incluye integridad de base offline.
- `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python backend/scripts/validate_database_security.py`: **PASS** suite SQL, rollback, concurrencia y restore independiente, incluidos atributos de roles. Log `/tmp/camera-phase6/independent-restore-final-retry.log`; recibo `PHASE_6_RESTORE.json`.
- `check_release_readiness.py` conserva NO_GO mientras falte cualquiera de los gates. Ni un hash ni un manifest local constituyen aprobación de release.

Sin cambios a runtime de aplicación, main o datos productivos; sin push, merge ni despliegue. La identidad del artefacto anterior no cambia: solo scripts de validación, tests y documentación.

Durante la repetición endurecida se detectó una carrera de arranque: pg_isready por socket aceptaba el servidor temporal de inicialización antes de su cierre. Se cambió a comprobación TCP 127.0.0.1, como en el runner fuente. El fallo queda registrado en `/tmp/camera-phase6/independent-restore-final.log`; no se oculta con una aprobación automática.

La repetición final tras corregir la carrera pasó, incluidos atributos de roles, RLS/grants, media y aislamiento; ningún contenedor de pruebas quedó activo.

## Continuación tras configurar secretos (2026-10-28)

El usuario confirma configuración segura fuera del chat. Comprobación actual: `git ls-remote origin HEAD` PASS y `gh auth status` PASS. La lectura de una rama específica falló porque no se acreditó su existencia remota; no demuestra fallo de autenticación. No se mantiene el diagnóstico anterior de token inválido como estado actual. La API Actions sigue devolviendo Forbidden y el proxy niega CONNECT a la base Grype (403).

El borrador contiene el binding SUPABASE_SECRET_KEY para el host del proyecto conocido. El proceso actual aún no recibe SUPABASE_SECRET_KEY ni SUPABASE_URL. No se pide otro secreto ni se imprime su valor. Se guardó la variable URL y la lista de red ampliada con api.github.com, grype.anchore.io y toolbox-data.anchore.io, conservando los destinos explícitos y de presets existentes. No se cambiaron install_script/start_skill ni bindings de secretos. El guardado respondió `saved`, `requires_publish: true`; no aplica ni publica la configuración en la instancia actual por sí mismo.

La siguiente operación es aplicar/publicar esa configuración desde el entorno y volver a comprobar su propagación. Después se podrá ejecutar el scan y consultar Actions; las pruebas administradas siguen limitadas a un proyecto identificado explícitamente como staging. No hubo consultas ni escrituras a Supabase, push, workflow remoto o despliegue. Evidencia: `PHASE_6_ENVIRONMENT_CONTINUATION.json`. Las 189 pruebas del incremento anterior no se repiten para un cambio exclusivamente documental/configuración; no se presentan como ejecución nueva.
