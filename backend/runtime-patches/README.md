# Backports de seguridad CPython

Sólo `poplib.py` y `http/client.py` del paquete Wolfi `python-3.13-base=3.13.18_git20261030-r0`.
Procedencia, hashes originales/resultantes y sustituciones exactas en [review.json](review.json).
Deltas upstream PSF-2.0 revisados: b234a2b67539f787e191d2ef19a7cbdce32874e7 (CVE-2025-15367),
2eb2af805c156ca52b316bb4ced5e0ab3971d0ae y9f52b443c002cccfb54bda0706a9276b6b4a109d (CVE-2026-103995).
Los `.patch` muestran deltas con contexto0; el instalador aplica las sustituciones de review.json,
verifica ambos hashes y sintaxis de todos los módulos antes de escribir. Otra versión del proveedor
requiere nueva revisión, no patch con fuzz ni descarga automática. El código conserva licencia PSF.

El proveedor incluye bytecode con hash sin comprobación (`flags=1`). Es necesario retirar sólo
los `.pyc` de estos dos módulos, incluso cuando el fuente ya tenga el hash resultante: `-B` no
impide leer un cache antiguo. No se elimina ningún otro módulo ni biblioteca nativa.

La imagen ejecuta51 casos de regresión sin red al construir y guarda recibos/fuentes de los
backports en `/licenses/`. El escáner por versión puede conservar los dos matches; no se ignoran,
no se modifica el número de versión del paquete OS y no se declara aceptación de producción.
