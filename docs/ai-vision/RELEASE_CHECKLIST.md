# Checklist de release AI 2.0

2026-10-28, America/Mexico_City. Estado global: **NO APROBADO**.
Marcar solo con evidencia vinculada al SHA/artefacto exacto; histórico no equivale a nueva ejecución. Ninguna fila autoriza despliegue por sí sola.

| Gate | Estado comprobado | Criterio de aceptación / evidencia pendiente |
| --- | --- | --- |
| Regresión backend | PASS controlado: 188 backend + 12 Android, entrega fase 6 | Evidencia en PHASE_6_DELIVERY_AND_ACCEPTANCE.md; histórico de intermitencia conservado. |
| Auth/tenant/roles/RLS | PASS fixtures API + PostgreSQL aislado | Probar Auth/Storage y drift en proyecto de staging autorizado; mantener denegación tras transferencias. |
| Clip/media/retención/rollback | PASS local, sustitutos Auth/Storage | Storage administrado, URLs 1800 s/expiración real, revocación y casos de retención/protección. |
| JWT streaming | PASS unitario de expiración/revocación/path | Gateway y dispositivos reales; no incluir bearer en URLs/logs. |
| Dependencias Python | Snapshot PyPI revisado, locks CI/tooling y BOM de componentes | Repetir advisories; auditor independiente, bytes de imagen, licencias completas y SBOM de runtime productivo. |
| OS/nativo/Android/modelos | SBOM generados; scan BLOQUEADO 403 | Escáner/versions/providers, modelos/cards/datasets/uso comercial y notices. |
| CI | Versionada, SHAs oficiales/Node24 y checks locales | Credencial GH_TOKEN inválida: ejecución remota/protección de rama pendientes; ningún push realizado aquí. |
| Imagen de entrega | PASS build offline y smoke imagen exacta | Base/deps por digest/hash, archivo e identidad en PHASE_6_ARTIFACT.json; no root/read-only/health/SIGTERM PASS. Scan nativo bloqueado; segundo build bit idéntico no demostrado. |
| Aislamiento/carga | PASS controlado 1/2/4, límites y recuperación | Soak y capacidad en hardware destino. 0.57–0.92 FPS medidos no satisfacen acciones sensibles de 2 FPS efectivos. |
| RTSP/red/substream | PENDIENTE equipos/egress | Interrupciones/redirects/SSRF, límites nativos, DNS, fuentes autorizadas y alineación física/PTS; fallo sin evidencia incorrecta. |
| Exactitud/acciones | NO CERTIFICADA | Dataset autorizado/anotado, métricas por escenario y umbrales acordados; conservar posible/pending y revisión humana. |
| UI/dispositivo | APK y 12 unitarias, evidencia fase 5 | Instrumentación/visual, aspect/TTL/pérdida red/roles y review en dispositivo; no inferir validación visual del build. |
| Backup/restore | PASS fixture cifrado aislado; operación PENDIENTE | Backup cifrado de DB/config/Storage y restore aislado probado, RPO/RTO acordados, inventarios y recuperación de ACL/retención. |
| Secretos/operación | Sin credenciales en pruebas; runbooks existentes | Inventario/rotación autorizada, métricas/alertas técnicas sin datos sensibles, ownership/rollback/drenaje verificados. |
| Aprobación release | NO SOLICITADA | Todos los gates resueltos o excepción concreta revisada con riesgo, SHA/digest y destino; autorización explícita. |

No habilitar alertas sensibles por defecto. No ejecutar down sobre datos reales como sustituto de un plan de recuperación. Mantener separados staging/producción, fuentes sintéticas y cámaras de usuarios.

Evidencia final local y límites: [entrega técnica](PHASE_6_DELIVERY_AND_ACCEPTANCE.md). Backup fixture no sustituye recuperación operativa; inventario no equivale a scan limpio. Resultado automatizado de gates: NO_GO.

Actualización posterior: [resolución de bloqueos](PHASE_6_BLOCKER_RESOLUTION.md), restore entre clústeres e importación offline Grype preparada; aceptación global sigue NO_GO.

Actualización tras publicar entorno: [validación real y hallazgos nativos](PHASE_6_PUBLISHED_VALIDATION.md). Conectividad y secretos disponibles; Supabase solo lectura HTTP200, CI remoto ejecutado. Scan nativo FINDINGS (200 matches); NO_GO continúa.

Estado vigente tras publicación: regresión backend 190 PASS; imagen reconstruida/smoke PASS; Python 70 sin avisos/errores. CI remoto EJECUTADO/FAILURE por escaneo nativo FINDINGS (200 matches/77 High), ya sin bloqueo de red. Supabase settings solo lectura HTTP200; staging sin confirmar. Identidad nueva en PHASE_6_CURRENT_ARTIFACT.json; gate de aceptación no cambia a PASS.

Estado de cierre y remediación vigente: [PHASE_6_REMEDIATION_STATUS.md](PHASE_6_REMEDIATION_STATUS.md). 195 backend PASS; dos bases evaluadas sin mejora (200/305 matches), candidata original conservada, CI remoto funcional PASS/seguridad FAIL. Runbook consolidado; NO_GO continúa.

Refuerzo posterior vigente: [controles y pruebas](PHASE_6_REINFORCEMENT.md).206 backend PASS; recibo de scan ligado a imagen/archive y sujeto a antigüedad, entorno de escáner restringido, cap-drop/no-new-privileges, MediaMTX rootless y tmpfs noexec.200 matches y NO_GO conservados. Configurar MEDIAMTX_UID/GID al propietario del config privado.

Candidata posterior de fase7: [plan/resultados](PHASE_7_RELEASE_REMEDIATION.md), [manifest](PHASE_7_ACCEPTANCE_MANIFEST.json), [NO_GO](PHASE_7_ACCEPTANCE_RESULT.json).220 backend/build/smoke/SQL/restore PASS; mitigación canónica de cursor y límite JWT sin cambio de dependencias; nativos200 sin resolución, gates externos pendientes. Las identidades de fase6 quedan históricas.
