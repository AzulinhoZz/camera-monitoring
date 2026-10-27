# FASE 2 iniciada — objetos y tracking temporal

Rama: `feat/ai-vision-platform`. El usuario autorizó resolver los bloqueos e iniciar FASE 2. Se conservan auth, cámaras, zonas, clips, horarios y retención; no se inició FASE 3 ni se hizo merge/despliegue. Esta entrega es una base experimental verificada, **no la aceptación final de precisión ni una release**.

Commits de implementación: `9b56c62` (gates de seguridad) y `f5af196` (detector/tracker auditados). Los resultados se refieren al estado final combinado.

## 1. Inventario de entrada y alcance

| Existía / faltaba / riesgo | Decisión / archivos |
| --- | --- |
| Existía worker acotado, contrato v1 y fuente sintética/video/RTSP | Reutilizados `vision/worker.py`, `source.py`, `contracts.py`; colas y namespaces por cámara. |
| RLS, callback, grants y coordinación tenían pendientes | Correcciones y resultados en [SECURITY_GATE_CLOSURE.md](SECURITY_GATE_CLOSURE.md). Migración 010 y down probados solo en PostgreSQL desechable. |
| Faltaban detector, tracker y expediente de licencias | `vision/detection.py`, `tracking.py`, `pipeline.py` y [MODEL_SELECTION_REVIEW.md](MODEL_SELECTION_REVIEW.md). |
| Riesgo de modelos/IDs no autorizados | Solo ONNX fijado por tamaño/hash, flags por cámara, fuente/scope de servidor, IDs temporales sin reidentificación. |
| No había línea base de inferencia | Benchmark real CPU 1→2→4 cámaras sintéticas con presupuesto 512 MiB. No se utilizan resultados mocked como FPS de IA. |

Dependencias: stack OpenCV/NumPy/Pydantic ya disponible; declaraciones directas PyJWT>=2.15.1 y HTTPX>=0.28,<0.29 para streaming seguro. No se añade PyTorch, ONNX Runtime, Ultralytics, ByteTrack ni modelos de poses/acciones. No hay tablas IA nuevas: se reutiliza contrato v1 en memoria. Los únicos cambios SQL son de seguridad sobre esquemas existentes.

## 2. Selección y suministro del modelo

YOLOX_s de OpenCV Zoo, snapshot `48b10fa505aeb51fbd127fc60a5c660040e823b7`, artefacto `object_detection_yolox_2022nov.onnx` (35,858,002 bytes):

```text
sha256 c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063
```

README/licencia del distribuidor declara Apache-2.0 para los archivos del directorio, incluidos los pesos. Expediente previo compara Ultralytics AGPL/enterprise y ByteTrack MIT; se eligió una primera integración CPU sin esas dependencias. Licencia/NOTICE se conservan en `backend/licenses` y en la imagen. Snapshot de paquetes y consulta PyPI: [PHASE_2_DEPENDENCY_SNAPSHOT.json](PHASE_2_DEPENDENCY_SNAPSHOT.json), [PHASE_2_PACKAGE_REVIEW.json](PHASE_2_PACKAGE_REVIEW.json). Listas de vulnerabilidades vacías para las cuatro releases consultadas no constituyen escaneo completo de transitivos/C++ ni garantía de ausencia de CVEs.

La descarga oficial estuvo inicialmente bloqueada con 403. Se guardó `media.githubusercontent.com` en el borrador de red preservando Supabase y una comprobación posterior descargó/verificó el archivo. No se afirma publicación de ese borrador. Peso local bajo `.models/`, ignorado por Git y Docker; no se incluye en imagen ni se descarga al arrancar. El loader verifica tamaño/hash y vuelve a verificar los bytes que pasa al parser, evitando cargar otro archivo si cambia la ruta. No usa pickle/torch.load ni acepta modelos subidos por usuarios.

```bash
.venv/bin/python backend/scripts/download_vision_model.py --output .models/yolox_s.onnx
```

El script verifica TLS, tamaño y SHA-256 antes del rename/enlace final y no sobrescribe un archivo existente inválido. El artefacto es público y queda legible para el usuario no root del contenedor. No se manejan claves de aplicación en este proceso.

## 3. Detector y contrato

- Entrada RGB con letterbox superior izquierdo a 640×640, padding 114, float32 sin normalización adicional, conforme al modelo revisado.
- Salida esperada 1×8400×85; valores finitos obligatorios, strides 8/16/32, score objectness×clase, NMS por clase.
- Clases COCO seleccionables por cámara y umbral configurable, cajas recortadas/normalizadas de área positiva. Se limita trabajo NMS a 1000 candidatos y salida a 100 detecciones.
- OpenCV DNN CPU, un modelo compartido y procesamiento secuencial en el proceso operador. Se solicita un hilo OpenCV; el motor nuevo de OpenCV 5 imprime un aviso de que ignora la selección de target. Se observó ejecución CPU, sin GPU; no se presenta como aceleración certificada.
- `ObjectPipeline` compara scope completo de Frame con cámara/owner/org antes de inferir; rechaza replay/secuencia desordenada. Produce eventos v1 con model_version, confidence, class, bbox y track_id temporal.
- event_id determinista por sesión/cámara/frame/track/modelo; esto permite correlación, **no implementa persistencia/idempotencia durable** ni transporte distribuido. No se escriben eventos en Supabase, clips, FCM ni alertas.
- Consumo de grabación en thread independiente por cámara: DNN lento no debe bloquear el drenaje de esa cola. Sigue siendo consumidor de laboratorio, no un segundo grabador; clips/retención existentes no se reemplazan.

## 4. Tracking y conteos (límites explícitos)

`IoUTracker` es implementación propia greedy por clase/IoU, **no ByteTrack**. ByteTrack se evaluó, pero no se incorporaron su código/pesos/transitivos. Cada cámara/sesión tiene tracker distinto; asociación uno-a-uno, expiración por tiempo monotónico, hasta 200 tracks, hasta 32 puntos por trayectoria. Rechaza tiempos desordenados y batches mayores de 100 detecciones.

Se exponen conteos visibles por clase y tracklets creados por clase. **No son personas únicas, conteos de cruce de línea ni identidad**: oclusiones, cruces y caídas de frames pueden crear IDs nuevos. La sesión reiniciada limpia tracker y contador; no hay seguimiento entre cámaras ni almacenamiento de identidades. La calidad ante oclusiones debe medirse con fixture etiquetada; no se prometen métricas de ID switches no medidas.

## 5. Activación optativa y rollback

Ejemplo anterior `backend/vision-worker.example.json` mantiene visión desactivada. Ejemplo nuevo `backend/vision-detection.example.json` activa solo fuente sintética con clases person/car/bus, confianza .5 y objetivo 1 FPS de inferencia. No restaura ni toma cámaras de DB automáticamente.

Host, desde raíz:

```bash
.venv/bin/python -m pip install --no-cache-dir -r backend/requirements-dev.txt
cd backend
../.venv/bin/python -m app.vision --config vision-detection.example.json \
  --model ../.models/yolox_s.onnx --emit-detections --duration 8
```

Sin `--emit-detections`, el CLI solo publica métricas, no posiciones/trayectorias en logs. Ese flag es de fixtures de laboratorio y se rechaza con RTSP. Los eventos reales permanecen en memoria hasta diseñar transporte/almacenamiento autorizado, no se vuelcan automáticamente a logs del servidor.

Demo Docker aislada, sin credenciales ni red:

```bash
BUILDX_CONFIG=/tmp/camera-ai-phase1-buildx docker build \
  --secret id=package_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t camera-monitoring-vision-worker:dev backend
docker compose -f docker-compose.vision.yml -f docker-compose.detection.yml --profile vision \
  run --no-deps --rm vision-worker python -m app.vision \
  --config /config/detection.json --model /models/yolox_s.onnx --emit-detections --duration 8
```

El bundle público de CA es solo montaje de build para este cloud; no se desactiva TLS ni se guarda una clave en imagen. La demo conserva UID 65534, filesystem readonly, 1 CPU, 512 MiB, límites de PIDs y colas. Pesos montados readonly; licencia/NOTICE incluidos en imagen. Para desactivar, detener solo vision-worker y usar configuración anterior sin `vision_enabled`/modelo. No borrar evidencia ni resetear main. Rollback SQL 010 es independiente y necesita revisión de mantenimiento; no revertir a upsert inseguro para apagar inferencia.

## 6. Pruebas y mediciones reales

```bash
.venv/bin/python -m pytest backend/tests backend/app/tests -q
.venv/bin/python backend/scripts/validate_database_security.py
.venv/bin/python backend/scripts/validate_gateway_security.py
.venv/bin/python backend/scripts/validate_capture_coordination.py
.venv/bin/python backend/scripts/validate_vision_rtsp.py
.venv/bin/python backend/scripts/benchmark_vision.py --model .models/yolox_s.onnx --seconds 6 --cameras 1 2 4
```

Resultados de esta iteración:

- **102 pruebas Python aprobadas**, 0 fallidas/omitidas/xfail. Incluyen las 86 previas, scope/revocación, leases/SIGKILL, proxy por segmento, redacción RTSP, contratos/postproceso/tracking/replay. Cinco avisos legados TestClient/on_event, sin assertions desactivadas.
- PostgreSQL 001–010: preservación, mínimos privilegios, aislamiento y negativos, concesión/revocación, carrera de org, rollback/reapply: PASS con procesos reales, no strings de SQL presentados como integración.
- MediaMTX MPEG-TS + proxy y publicador sintético: PASS. LowLatency/fMP4 opcional recibió 404 en recurso; no se habilita ni declara validado.
- Captura compartida root/no-root en Docker: PASS. Decoder muere al SIGKILL del supervisor en prueba separada; recuperación/EOF/stream interrumpido y colas acotadas conservan cobertura.
- ONNX real: hash/tamaño correctos; tres primeras inferencias geométricas 640.46/573.18/550.86 ms, cero detecciones. No sustituye pruebas positivas de exactitud.
- Demo de inferencia en contenedor: 8 batches reales sobre geometría, alcanza healthy y termina con código 0, colas vacías y 0 drops de grabación. No se confunden batches sin objetos con detecciones positivas.
- Android: build de tests intentado, **tests NO EJECUTADOS** por bootstrap de Gradle; no se cambiaron pines/checksums. No se afirma reproducción móvil.

### Benchmark corto 1→2→4 (host, no capacidad productiva)

Resultado completo versionado: [PHASE_2_BENCHMARK.json](PHASE_2_BENCHMARK.json).

CPU Linux, cuota del entorno 4 CPU equivalentes, memoria disponible amplia; OpenCV solicita 1 hilo. Fuente geométrica 160×120, entrada del modelo 640×640, captura 10 FPS, inferencia objetivo 1 FPS/cámara, modelo compartido secuencial, un warmup no medido. Duración pedida 6 s; se completa una inferencia en curso y cierre. Presupuesto observado de RSS sumado ≤512 MiB; si se supera, el runner detiene/omite etapas. RSS suma procesos y puede contar páginas compartidas más de una vez.

| Cámaras | Pared s | Frames inferidos | FPS/cámara observado | RSS sumado máximo MiB | Drops cola grabación |
| --- | ---: | --- | --- | ---: | --- |
| 1 | 6.134 | 6 | 0.978 | 260.30 | 0 |
| 2 | 6.396 | 5 / 6 | 0.782 / 0.938 | 329.11 | 0 / 0 |
| 4 | 6.581 | 2 / 3 / 3 / 3 | 0.304 / 0.456 / 0.456 / 0.456 | 472.32 | 0 / 0 / 0 / 0 |

Latencia de pipeline p50 por cámara: 573.07 ms (1); 530.87/502.48 ms (2); 511.65/525.99/520.36/534.07 ms (4). Pocas muestras, calentamiento/contención y ejecución secuencial: no comparativa científica ni garantía de 1 FPS para 4 cámaras. Una versión inicial drenaba grabación en el mismo loop de inferencia y perdió muchas muestras; el consumidor independiente corrigió ese acoplamiento y se repitió la medición. No se oculta el descarte: las colas siguen contando drops/stale cuando hay sobrecarga.

No se miden precisión/recall/mAP, ID switches reales, conteos de personas, tasa de alertas, HLS end-to-end en móvil ni MB/h de Storage. Los frames geométricos no contienen objetos COCO; pruebas positivas de asociación/cajas usan salidas sintéticas explícitas. **No confundir pasar postproceso/tracking con demostrar detección semántica sobre cámaras reales.**

## 7. Estado y siguiente incremento

FASE 2 está **iniciada e implementada como prototipo aislado**. Para aceptarla como funcionalidad real faltan video permitido/etiquetado con objetos, métricas de exactitud/oclusiones/conteo, selección del tracker definitivo, límites/SLO por hardware y persistencia/transporte revisados. El motor actual no afirma acciones, delitos ni identidad.

Se cerraron los bloqueos de código comprobados de RLS/grants, HLS por recurso y captura en un host; egress remoto, Android y activación en un proyecto de prueba real conservan sus gates explícitos en el informe de seguridad. No se conecta a producción, no se activa FASE 3 ni se publica el entorno desde esta entrega. El borrador de red puede revisarse/guardarse y publicarse mediante la UI cuando el usuario decida conservarlo; eso es independiente de desplegar la aplicación.


## Configuración reutilizable del cloud

Se guardaron en el borrador el dominio adicional `media.githubusercontent.com` (sin retirar Supabase) y `start_skill` actualizado: pruebas offline, smoke sin DB, demo de modelo y gates de activación. No se cambió la lista de repositorios ni se guardaron valores de secretos. Guardar el borrador no publica ni despliega; revisar y guardar la configuración y publicar el entorno en la UI permite conservar ese ajuste/snapshot cuando el usuario lo decida.
