> Actualización: selección final, pesos derivados y rechazo del runtime legacy en [PHASE_4_COMPLETION.md](PHASE_4_COMPLETION.md), `PHASE_4_RUNTIME_REVIEW.json` y `PHASE_4_BUNDLED_MODELS_REVIEW.json`. Esta evaluación inicial se conserva como historial.

# Fase 4 — revisión de componentes antes de integración

Fecha: 2026-10-27 (America/Mexico_City). Evaluación, no autorización de despliegue.
Fuentes/metadatos/hashes: [snapshot verificable](PHASE_4_COMPONENT_REVIEW.json).

## MediaPipe

Se revisaron metadatos oficiales de PyPI para 0.10.21, 0.10.32 y latest (1.2.0 en la consulta). Se selecciona **0.10.32 como candidato de evaluación futura**, sin instalarlo ni aprobar pesos. Tag v0.10.32 resuelto mediante git ls-remote a `8317ba78778738ba90a521e7e4580a2ba0129c81`. LICENSE obtenido desde ese commit y preservado en [copia de licencia](licenses/MediaPipe-0.10.32-LICENSE.txt); incluye Apache-2.0 y aviso permisivo Lucent para archivos UTF concretos que debe conservarse.

Wheel Linux x86_64 revisado sin ejecutarlo: `mediapipe-0.10.32-py3-none-manylinux_2_28_x86_64.whl`, 10,331,072 bytes, SHA256 `4b0941fbbbce41862f13cb1850c4878c13dbc62cd5e81e74880051b7a20ce3b6`; coincide con PyPI oficial. Se inspeccionaron licencia y listado del ZIP: no trae .task/.tflite/.onnx/.pth. No se deduce de ello una licencia para pesos externos.

0.10.21 exige numpy<2 y protobuf<5, además de JAX/JAXlib y otros componentes. Entorno actual comprobado: Python3.12.14, NumPy2.5.4 y OpenCV headless5.0.0. Una resolución podría forzar cambios/downgrades; no se ejecuta instalación en el backend. 0.10.32 declara NumPy sin ese límite y wheel py3 manylinux2_28, pero eso **no prueba** compatibilidad binaria/runtime. Depende de opencv-contrib-python, absl-py, sounddevice, flatbuffers y matplotlib. Dos distribuciones de OpenCV podrían proporcionar cv2: requiere entorno/contenedor separado y una única distribución elegida, no instalar contrib junto al headless actual.

La versión latest observada 1.2.0 tenía wheels subidos el mismo día de la revisión; no se adoptó automáticamente. El tag v1.2.0 no se resolvió en la consulta y LICENSE de ese tag devolvió 404; esto no demuestra un incidente de seguridad ni licencia incorrecta. Simplemente no aporta una base fijada suficiente para seleccionarla en esta iteración.

Pose/Hand/Gesture Tasks son candidatos, no componentes integrados. Antes de un adaptador: licencia/model card de cada .task/.tflite, procedencia, versión, hash/tamaño, datos/condiciones de uso comercial, reconocimiento explícito de que visibilidad/presencia no son exactitud de gesto y evaluación en secuencias permitidas. Hands puede carecer de calidad por landmark: no fabricar scores ni usar handedness como probabilidad de acción.

## MMAction2

PyPI1.2.0 (wheel publicado 2023-10-12), tag v1.2.0 `4d6c93474730cad2f25e51109adcf96824efc7a3`. LICENSE Apache-2.0 preservado en [copia de licencia](licenses/MMAction2-1.2.0-LICENSE.txt). Wheel `mmaction2-1.2.0-py2.py3-none-any.whl`, 882,189 bytes, SHA256 `4697af11801a7e7b45700a1d21cb27afb5350b28718c31ca19b65a927fde1614`, verificado contra PyPI y ZIP inspeccionado sin ejecutar; sin pesos de modelos en los sufijos revisados.

Declara torch>=1.3, decord, einops, matplotlib, NumPy, opencv-contrib-python, Pillow y SciPy. El extra mim fija mmcv>=2.0.0rc4,<2.2.0 y mmengine>=0.7.1,<1.0.0. README fijado muestra ejemplo con Python3.8 y exige cotejar PyTorch/CUDA. No hay prueba de esa combinación nativa con Python3.12/OpenCV5/NumPy2 ni del presupuesto de RAM/CPU del worker. La edad de una publicación PyPI no implica abandono del repositorio; git HEAD actual fue accesible, sin inferir mantenimiento por la fecha del wheel.

Decisión: aplazar integración y checkpoint hasta seleccionar arquitectura temporal, runtime fijado y condiciones de pesos/dataset para el uso previsto. Apache-2.0 del framework no concede derechos generales sobre vídeos/checkpoints/datasets. No se integran clasificadores frame a frame disfrazados de detector de caídas/agresión.

## Seguridad, procedencia y límites del examen

Las listas vulnerabilities de PyPI consultadas estaban vacías para las versiones revisadas. **No es un escaneo completo ni garantía de ausencia de CVE**, no cubre transitivas/nativas/modelos. No se importaron wheels, instaló código externo ni descargaron pesos. Una revisión de dependencias completas/SBOM y pruebas de aislamiento queda pendiente antes de habilitar un runtime externo.

GitHub REST API devolvió 403 en este entorno; se continuó con refs git y archivos raw fijados, además de metadatos y wheels oficiales de PyPI. No se desactivó TLS ni se cambiaron dominios permitidos. No se copiaron repositorios enteros ni implementaciones externas.

El código nuevo de laboratorio usa solo dependencias existentes (OpenCV/NumPy/Pydantic), contratos propios y conexiones anatómicas documentadas como índices. No utiliza MediaPipe/MMAction2 ni pesos en producción; las licencias aquí son evidencia de revisión, no anuncio de integración terminada.
