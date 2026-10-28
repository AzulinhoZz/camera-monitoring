# Checklist de release AI 2.0

2026-10-28, America/Mexico_City. Estado global: **NO APROBADO**.
Marcar solo con evidencia vinculada al SHA/artefacto exacto; histórico no equivale a nueva ejecución. Ninguna fila autoriza despliegue por sí sola.

| Gate | Estado comprobado | Criterio de aceptación / evidencia pendiente |
| --- | --- | --- |
| Regresión backend | PASS controlado: 183 tests, fase 6 inicial | Repetir para SHA candidato y registrar intermitencia de reconexión. |
| Auth/tenant/roles/RLS | PASS fixtures API + PostgreSQL aislado | Probar Auth/Storage y drift en proyecto de staging autorizado; mantener denegación tras transferencias. |
| Clip/media/retención/rollback | PASS local, sustitutos Auth/Storage | Storage administrado, URLs 1800 s/expiración real, revocación y casos de retención/protección. |
| JWT streaming | PASS unitario de expiración/revocación/path | Gateway y dispositivos reales; no incluir bearer en URLs/logs. |
| Dependencias Python | Snapshot PyPI revisado, locks CI/tooling y BOM de componentes | Repetir advisories; auditor independiente, bytes de imagen, licencias completas y SBOM de runtime productivo. |
| OS/nativo/Android/modelos | PENDIENTE | Escáner/versions/providers, modelos/cards/datasets/uso comercial y notices. |
| CI | Versionada, SHAs oficiales/Node24 y checks locales | Primera ejecución GitHub y protección de rama/checks requeridos; ningún push realizado aquí. |
| Imagen de entrega | BLOQUEADA por disco en build fase 5 | Build reproducible, base/deps fijadas revisadas, digest, scan, no root/read-only/health/SIGTERM; no sustituir por smoke de fuente copiada. |
| Aislamiento/carga | PASS controlado 1/2/4, límites y recuperación | Soak y capacidad en hardware destino. 0.57–0.92 FPS medidos no satisfacen acciones sensibles de 2 FPS efectivos. |
| RTSP/red/substream | PENDIENTE equipos/egress | Interrupciones/redirects/SSRF, límites nativos, DNS, fuentes autorizadas y alineación física/PTS; fallo sin evidencia incorrecta. |
| Exactitud/acciones | NO CERTIFICADA | Dataset autorizado/anotado, métricas por escenario y umbrales acordados; conservar posible/pending y revisión humana. |
| UI/dispositivo | APK y 12 unitarias, evidencia fase 5 | Instrumentación/visual, aspect/TTL/pérdida red/roles y review en dispositivo; no inferir validación visual del build. |
| Backup/restore | PENDIENTE | Backup cifrado de DB/config/Storage y restore aislado probado, RPO/RTO acordados, inventarios y recuperación de ACL/retención. |
| Secretos/operación | Sin credenciales en pruebas; runbooks existentes | Inventario/rotación autorizada, métricas/alertas técnicas sin datos sensibles, ownership/rollback/drenaje verificados. |
| Aprobación release | NO SOLICITADA | Todos los gates resueltos o excepción concreta revisada con riesgo, SHA/digest y destino; autorización explícita. |

No habilitar alertas sensibles por defecto. No ejecutar down sobre datos reales como sustituto de un plan de recuperación. Mantener separados staging/producción, fuentes sintéticas y cámaras de usuarios.
