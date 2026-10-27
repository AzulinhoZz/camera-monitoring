# FASE 2 — Revisión previa de detector y tracker

Alcance: evaluación técnica para desarrollo aislado; no autorización de producción ni garantía jurídica sobre datasets. No se copian repositorios ni se descargan imágenes personales.

| Opción | Fuente/licencia comprobada | Decisión |
| --- | --- | --- |
| Ultralytics YOLO | LICENSE oficial AGPL-3.0: https://github.com/ultralytics/ultralytics/blob/main/LICENSE . La oferta enterprise requiere contratación separada. | No instalar/integrar en esta iteración: no se ha elegido cumplir AGPL ni contratar enterprise para este producto. No es una prohibición de uso comercial. |
| YOLOX / OpenCV Zoo | YOLOX Apache-2.0; README del directorio Zoo declara **todos los archivos** bajo Apache-2.0, incluidos pesos ONNX. Snapshot Zoo `48b10fa505aeb51fbd127fc60a5c660040e823b7`. | Elegido para adaptador optativo CPU OpenCV DNN; conservar licencia/atribución. No necesita PyTorch ni servicios de pago. |
| ByteTrack | LICENSE oficial MIT, copyright 2021 Yifu Zhang: https://github.com/ifzhang/ByteTrack/blob/main/LICENSE . | Evaluado; no incorporado: integración upstream añade dependencias y validación específicas no necesarias para iniciar tracking. No se presenta el tracker propio como ByteTrack. |
| Tracker temporal IoU propio | Implementación nueva, sin pesos ni código copiado. Asignación greedy por clase y solapamiento, TTL y trayectorias acotadas. | Primera opción experimental; no reidentificación, Kalman, apariencia ni asociación entre cámaras. Documentar cambios de ID/oclusiones; conteos son tracklets, no personas únicas. |

## Procedencia e integridad del modelo elegido

- Directorio y declaración de licencia: https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_yolox
- `object_detection_yolox_2022nov.onnx`: YOLOX_s, entrada 640×640, 80 clases COCO, salida esperada 1×8400×85.
- Puntero Git LFS del snapshot leído con TLS verificado: tamaño **35,858,002 bytes**, SHA-256 **c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063**.
- No sustituir hash por el de un archivo descargado arbitrario. Verificar tamaño/hash **antes** de pasarlo al parser ONNX nativo. Sin pickle ni torch.load.
- Licencia completa conservada en `licenses/YOLOX-OpenCV-Zoo-Apache-2.0.txt`. Adaptador y matemáticas de decodificación referencian `yolox.py`/`demo.py` oficiales del mismo snapshot; atribución a OpenCV y Sri Siddarth Chakaravarthy (GSoC 2022). No se incorporan los demos ni repositorio completo.
- Modelo COCO preentrenado: no implica que todas las imágenes originales de entrenamiento sean redistribuibles por el producto. No se descargan ni redistribuyen aquí. La declaración Apache del directorio cubre el artefacto del distribuidor; las obligaciones de despliegue/dataset deben revisarse antes de distribución comercial.

## Mantenimiento y vulnerabilidades

La fuente se fija a un commit comprobado mediante `git ls-remote`; no se presume soporte futuro ni que el modelo de 2022 sea el más preciso. Se evalúa compatibilidad con OpenCV existente, CPU y arrays NumPy; ONNX Runtime/aceleración se mantienen fuera de este incremento.

Consulta de metadatos de vulnerabilidades por release en PyPI del **venv de este repositorio**: OpenCV headless 5.0.0.93, NumPy 2.5.4, Pydantic 2.14.1 y PyJWT 2.15.1 devolvieron listas vacías. Esto no certifica ausencia de CVEs del código nativo ni constituye escaneo completo de todos los transitivos. Se declara PyJWT >=2.15.1: otra instalación del host usa 2.13.0 y sus avisos no deben confundirse con las dependencias verificadas del proyecto.

Un ONNX sigue siendo entrada para un parser C++: usar solo el artefacto fijado y contenedor con límites; no aceptar uploads/modelos del usuario. Pesos no incluidos en Git ni en imagen por defecto. Ingesta real y métricas de exactitud requieren dataset permitido y aprobación de despliegue.

## Estado de descarga y aceptación

El destino oficial `media.githubusercontent.com` devolvió inicialmente HTTP 403. Se añadió ese dominio al borrador preservando los existentes y una comprobación posterior descargó y verificó el artefacto: 35,858,002 bytes y SHA-256 esperado. Se ejecutaron tres inferencias reales CPU sobre frames geométricos, todas sin detecciones (latencias 640.46/573.18/550.86 ms). Esto valida carga/ejecución, no precisión semántica, mAP ni ausencia de falsos positivos en escenas reales. Las pruebas con salidas simuladas validan postproceso/tracking por separado. El cambio de configuración permanece guardado como borrador; no se afirma publicación del entorno.

Referencias de código adicionales comprobadas con `git ls-remote`: Ultralytics `eac9491607fd1ea7fe32d43e734e1c22924dc9e3`, ByteTrack `d1bf0191adff59bc8fcfeaa0b33d3d1642552a99`. Su licencia se consultó en la fuente oficial; ninguno se integra en esta entrega.
