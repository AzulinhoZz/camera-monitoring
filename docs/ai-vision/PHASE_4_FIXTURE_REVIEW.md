# Procedencia de fixtures de fase 4

Fecha: 2026-10-27, America/Mexico_City. No se usan cámaras ni datos de clientes. Las imágenes públicas incluyen un cuerpo/manos; no son datos sintéticos ni se utilizan para identificar personas. Las secuencias de caídas son coordenadas generadas, no vídeos de accidentes.

## Cuerpo

`backend/scripts/download_pose_fixture.py --kind body --output /tmp/astronaut.png` extrae solamente `astronaut.png` del wheel scikit-image 0.26.0 verificado, sin instalarlo. El módulo `_fetchers.py` de esa distribución declara para esta imagen NASA: “No known copyright restrictions, released into the public domain.” Fuente histórica: NASA Great Images. No se presupone que todas las imágenes de scikit-image tengan esa licencia.

- Wheel: tamaño 13,561,683 bytes; SHA256 `7df650e79031634ac90b11e64a9eedaf5a5e06fcd09bcd03a34be01745744466`.
- PNG: SHA256 `88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5`.
- Se evalúan landmarks corporales, excluyendo del contrato los índices faciales 0–10. No hay reconocimiento facial ni identidad persistente.

## Manos

Fixture oficial de TensorFlow.js Models `hand-pose-detection/test_data/hands.jpg`, commit inmutable `c731b9ebbd6f4c9e8bf99b0df76bbdbf9c25b07f`:

https://raw.githubusercontent.com/tensorflow/tfjs-models/c731b9ebbd6f4c9e8bf99b0df76bbdbf9c25b07f/hand-pose-detection/test_data/hands.jpg

- JPEG: 54,888 bytes; SHA256 `240c082e80128ff1ca8a83ce645e2ba4d8bc30f0967b7991cf5fa375bab489e1`.
- Licencia raíz Apache-2.0 del mismo commit, conservada íntegramente en [licenses/TFJS-HAND-FIXTURE-LICENSE.txt](licenses/TFJS-HAND-FIXTURE-LICENSE.txt); SHA256 `58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd`.
- Atribución: TensorFlow.js Models / sus autores, según el aviso copyright de esa licencia. El fixture no tiene un aviso de excepción en la ruta revisada. No se descarga el repositorio completo.
- El helper `--kind hand` verifica tamaño/hash. Imagen con dos manos; el validador usa también un recorte/repetición temporal de una mano. Es asociación suministrada por el ensayo, no prueba de tracking de sujetos en vídeo.

## Límites

Los binarios/fotos no se añaden a Git. Descarga explícita, HTTPS y hashes fijos; ninguna descarga desde el worker. Repetir imágenes valida integración y geometría, no precisión/recall de gestos ni caídas naturales. El corpus `action_sequences.py` incluye un contraejemplo de acostarse voluntariamente rápido que provoca un candidato: no se oculta como negativo aprobado. Antes de activar escenarios reales se requiere un conjunto autorizado, anotado y representativo con evaluación humana de falsos positivos/negativos. No hay permiso implícito para usar grabaciones de clientes ni nuevas afirmaciones sobre derechos de los datasets originales de entrenamiento.
