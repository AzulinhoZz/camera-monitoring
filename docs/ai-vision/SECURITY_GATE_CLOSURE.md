# Bloqueos de FASE 1 — correcciones y pruebas antes de FASE 2

Ámbito: rama `feat/ai-vision-platform`, desarrollo aislado. El usuario autorizó resolver los bloqueos e iniciar FASE 2. **Ninguna migración, clave nueva ni despliegue se aplicó en producción.** Las condiciones de activación real se distinguen de las correcciones comprobadas.

## Inventario previo y decisiones

| Bloqueo | Corrección | Evidencia / límite |
| --- | --- | --- |
| DB-01: helpers sin EXECUTE y 009 duplicada | Migración aditiva 010; directorio canónico `backend/migrations`; copia bajo app es ahora un forwarding psql, no otra implementación. Docker copia migraciones canónicas. | PostgreSQL real con privilegios mínimos; no se modificó 009 canónica ni duplicaron tablas de 006/007/008/009. Drift del proyecto remoto no inspeccionado. |
| DB-02: runner SQL ocultaba errores | ON_ERROR_STOP on, assertions/SQLSTATE y datos sintéticos, sin GRANT ALL ON ALL FUNCTIONS. Caso de unidad cruzada alcanza y verifica su trigger. | Runner falla ante error inesperado; rollback y reaplicación probados. |
| AUTH-01/02: carrera al otorgar acceso y grants obsoletos | RPC service-only deriva rol/org del actor validado por API y bloquea perfiles/cámara durante concesión. Grants dejan de autorizar si cambia organización. | Prueba real de transacciones concurrentes: cambio de org bloqueado hasta commit. API/RLS alineados para lectura de grants; configuración y retención siguen owner-only. |
| AUTH-03: callback confiaba en ip/action y no protegía cada recurso HLS | Callback Basic autenticado; publicación con clave distinta; JWT de lectura ligado a cámara/owner/org/path, emisor/audiencia y expiración. Proxy FastAPI autoriza cada playlist/segmento; HLS nativo deja de publicarse. | MediaMTX real + publisher sintético: playlist/variant/segmento permiten credencial válida y deniegan anónimo/token inválido. Pruebas de expiración, revocación y cambio de scope. |
| VIS-01: motores podían capturar simultáneamente | Lease flock compartido por API, probes y vision-worker; espera de cierre legado. Decoder Linux muere si el supervisor recibe SIGKILL. | Unit tests de colisión/reinicio/SIGKILL y prueba Docker root↔no-root sobre volumen común. Solo exclusión por host/volumen, no multihost. |
| Scope y SSRF | Registro servidor verifica owner/org y sustituye fuente RTSP por la de DB; cambios/fallo de registro detienen servicio. Política CIDR/puerto compartida para API/legado/probes, denegación por defecto y DNS fijado. | Pruebas de scope; CIDRs/puertos obligatorios para cámaras reales. **Egress contra conexiones/redirects nativos sigue siendo condición de infraestructura para activar RTSP remoto**, no se presenta como firewall implementado. |

Las correcciones de código permiten iniciar FASE 2 **en la demo sin red y fixtures permitidas**. No equivalen al cierre de toda la validación de despliegue, Android, Storage administrado ni escenarios de cámara real.

## 1. Migraciones y reversión

- Up: `backend/migrations/010_security_helpers_and_atomic_grants.sql`.
- Down: `backend/migrations/rollback/010_security_helpers_and_atomic_grants.sql`.
- `backend/app/migrations/009_roles_and_organizations.sql` conserva entrada compatible para psql vía `\ir ../../migrations/009_roles_and_organizations.sql`. Para SQL Editor se usa el archivo canónico, **no** este forwarding.
- 010 concede EXECUTE solo de los helpers necesarios a authenticated/service_role; anon/PUBLIC no reciben las funciones nuevas. La RPC `grant_camera_access_for_actor` solo puede ejecutarla service_role; actor_id viene del usuario autenticado, nunca del cuerpo HTTP.
- La RPC bloquea perfiles en orden de ID y cámara, comprueba rol/admin y organizaciones, y hace upsert en una transacción. No usa dos SELECT de autorización seguidos de una escritura desprotegida en API. Si 010 falta, la ruta falla cerrada con 503; no vuelve al upsert inseguro.
- El helper SQL y `permissions.py` niegan grants que ya no pertenezcan a la organización de la cámara. Ser lector no permite editar/borrar cámara ni crear eventos manuales. Los permisos de zonas/movimiento/protección/retención mantienen su restricción previa por propietario; no se amplían silenciosamente.
- Down no borra datos ni cámaras; restaura el estado de privilegios anterior, que tenía un defecto conocido. **No es una reparación por sí misma**: requiere mantenimiento y revisión de aplicación antes de usarla fuera del fixture.

Prueba segura reproducible desde la raíz:

```bash
.venv/bin/python backend/scripts/validate_database_security.py
```

Este script crea su propio PostgreSQL 15.19 con `--network none`, sin puertos, nombre único y checkout readonly; no admite DSN. Aplica fixture y 001–010, comprueba preservación 3 perfiles/12 cámaras/12 eventos, aislamiento, escalación denegada, unidad cruzada, privilegios mínimos, concesión y revocación por cambio de org. Revierte 010, verifica que conserva cámaras, reaplica y repite assertions. Dos sesiones adicionales demuestran bloqueo real del cambio de org mientras la concesión mantiene sus locks. El contenedor se elimina al terminar. **Jamás ejecutar setup_test_db.sql contra una base existente.**

Resultado: todos esos checks pasaron. No se probó el proyecto Supabase real ni se necesita su clave para ejecutar el fixture.

## 2. Streams protegidos de extremo a extremo en el servidor

### Credenciales y permisos

`streaming.py` emite JWT de 60 s con camera_id, owner_id, organization_id (nullable), path canónico completo `cam_<camera_id>`, sub, iat, exp, issuer y audience. El token se entrega como `stream_token`, separado de la URL; no se incrusta en query strings. El callback/proxy vuelve a consultar scope/permisos: token correcto no conserva acceso si se revoca el grant o se mueve la cámara.

Secretos independientes, de al menos 32 caracteres aleatorios URL-safe, exclusivamente de servidor:

- `STREAM_TOKEN_SECRET`: firma de tokens de lectura.
- `MEDIAMTX_GATEWAY_SECRET`: Basic de MediaMTX hacia callback (`gateway` como usuario).
- `MEDIAMTX_PUBLISH_SECRET`: publicación RTSP con usuario `publisher`, solo para paths de cámaras existentes.
- `MEDIAMTX_HLS_SECRET`: enlace privado del proxy a HLS nativo/CDN.

Se documentan nombres vacíos en `.env.example`, sin valores reales. Configurarlos mediante archivo/gestor de secretos seguro, nunca en chat, logs ni Git. El transporte interno HTTP requiere red confiable; en redes no confiables, TLS también entre servicios. Los tests generan valores efímeros en memoria y no imprimen credenciales ni comandos que las contienen.

### Por qué un proxy HLS

La prueba inicial de callback expuso una diferencia importante: la sesión HLS nativa puede autorizar recursos mediante capacidad de sesión en URL/cookie, sin repetir el bearer del producto en cada segmento. Esa sesión no sustituye la revocación/permisos por petición requerida aquí. No se presenta como una CVE del servidor.

`stream_proxy.py` expone `/streams/{camera_id}/{filename}` y verifica JWT, scope y permiso **en cada petición**, incluidos segmentos. Consulta al HLS nativo con la credencial privada CDN, sin reenviar tokens del usuario ni publicar cookies/capacidades de sesión. El puerto 8888 deja de estar publicado en Compose. RTSP 8554 conserva auth del callback; API/RTSP publicados solo en loopback en la configuración de desarrollo.

Protecciones adicionales: nombres/extensiones acotados, rechazo de traversal y playlists con destinos remotos, query HLS permitida de forma explícita, sin redirects, timeout 10 s, máximo 16 MiB por recurso, Cache-Control privado/no-store. La URL interna es configuración del servidor; no se toma de la petición. No es rate limiting ni protección de carga completa; eso permanece en hardening.

El perfil elige explícitamente **HLS MPEG-TS**, comprobado con MediaMTX 1.21.3 fijado por digest. Un ensayo opcional lowLatency/fMP4 recibió 404 al pedir un segmento: no se afirma soporte LL-HLS en esta entrega ni se oculta ese resultado. La configuración entregada usa el transporte verificado y Android Media3 lo soporta; reproducción Android no compilada/probada aquí.

```bash
.venv/bin/python backend/scripts/validate_gateway_security.py
```

Resultado real: PASS de publicación autenticada, playlist/variant/segmento por proxy y denegación anónima/token inválido. El runner usa usuarios/cámara en memoria y video negro sintético, no Supabase/usuarios reales. Crea y detiene únicamente sus procesos/contenedor. La fixture abierta de la prueba RTSP de fallos se separó en `backend/app/tests/fixtures/mediamtx-open.yml`, limitada a publicación loopback de pruebas; no es configuración de despliegue.

Android incorpora los campos de token/expiración, envía Authorization en todas las solicitudes Media3 y renueva cada 40 s. Se elimina el fallback al HLS abierto y el prefijo de token FCM en logs. **Tests/build Android NO EJECUTADOS**: el wrapper volvió a fallar antes de ejecutar tests con UnknownHostException de services.gradle.org. Una comprobación HTTPS Python alcanzó la distribución fijada (200), por lo que el problema pendiente está en transporte/toolchain Java del cloud; no se cambiaron versión ni checksum para forzar éxito. SDK/JDK 25 tampoco quedaron preparados en esta iteración.

## 3. Captura, fuente y vida del proceso

`capture_lease.py` identifica la cámara mediante hash, adquiere flock no bloqueante y nunca elimina el inode del lock. El directorio debe compartirse entre todos los procesos de captura del host. Compose usa el mismo volumen nombrado y `CAMERA_LEASE_DIRECTORY=/run/camera-leases`. Solo los contenedores confiables acceden a ese volumen; no es una barrera de autorización para usuarios.

- La API no guarda un thread sin iniciar cuando encuentra un propietario externo; shutdown no intenta hacer join de un thread que nunca arrancó.
- Stop legado espera cierre con timeout y conserva exclusión si no termina. Relectura fallida libera/reabre captura; open/read tienen timeout.
- Probes no abren una segunda captura de una cámara activa o gestionada externamente. El checker conserva presets/horarios al iniciar un worker.
- `guarded_decoder` usa Linux parent-death SIGKILL y comprueba PID del padre antes de capturar. Se probó SIGKILL del supervisor, muerte del decoder y liberación del lease. Linux es el host soportado, no se finge portabilidad a Windows/macOS.
- `registry.py` consulta source/owner/org en DB para RTSP; `--resolve-scopes` es obligatorio en el CLI y revalida antes de cada snapshot de métricas. Cambio de scope/fuente o fallo de DB detiene el pipeline; no acepta los IDs del archivo como autoridad por sí mismos. No se ejecutó esa consulta contra Supabase real.
- Política de destinos reutilizada por alta/edición/legado/probes: sin `CAMERA_ALLOWED_CIDRS` no se acepta destino; puertos explícitos, loopback requiere opt-in. Se retiran userinfo/query de respuestas legadas y URLs de logs propios; nuevas URLs con credenciales siguen rechazadas. No se introduce soporte rtsps no verificado.

Prueba Docker root/no-root:

```bash
.venv/bin/python backend/scripts/validate_capture_coordination.py
```

PASS: root crea el inode, worker UID 65534 lo abre, root no captura mientras el worker es propietario, y vuelve a adquirir tras cierre. El runner usa volumen y contenedores únicos y los retira; no toca el volumen de despliegue. Flock **no coordina varios hosts**: mantener un único host de captura por cámara hasta diseñar lease distribuido.

## 4. Qué queda antes de activar cámaras reales

1. Revisar/aplicar 010 primero en un proyecto de prueba autorizado, comprobar drift/RLS de Supabase y tener backup/rollback; aquí solo se aplicó en contenedores desechables.
2. Configurar claves de servidor y los dominios/redes reales; comprobar TLS de exposición y **egress del decoder contra redirects/conexiones nativas**. La validación inicial de IP/DNS no garantiza por sí sola ese aislamiento. Las demos de FASE 2 conservan `network_mode: none`; no habilitar RTSP remoto solo cambiando a una red abierta.
3. Desplegar API y gateway/clientes compatibles juntos; procesos antiguos del onboarding no se actualizaron ni se presentan como reparados en caliente.
4. Completar Android y prueba Auth/Storage administrada en entorno aislado. La firma de URLs de evidencias/retención existentes no se declara certificada por el smoke HLS.
5. Validar exactitud, falsos positivos, oclusiones y conteos con video permitido/etiquetado antes de alertas. No hay identificación personal ni seguimiento entre cámaras.

El código y las pruebas cierran los bloqueos de RLS/grants, gateway por recurso y captura **en el ámbito comprobado**. Egress remoto, Android y despliegue real siguen como gates operativos explícitos; no se afirma preparación productiva completa.

Implementación de los gates: commit `9b56c62`; integración de objetos/tracking posterior: `f5af196`. No se presenta el estado de procesos antiguos del onboarding como validación de esos commits.
