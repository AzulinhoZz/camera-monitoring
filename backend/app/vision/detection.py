"""Opt-in YOLOX_s adapter. Architecture/postprocess based on OpenCV Zoo,
48b10fa505aeb51fbd127fc60a5c660040e823b7 (Apache-2.0).
Attribution: OpenCV / Sri Siddarth Chakaravarthy (GSoC 2022).
Full upstream license: docs/ai-vision/licenses/YOLOX-OpenCV-Zoo-Apache-2.0.txt.
Only the fixed, verified ONNX artifact is accepted; no runtime downloading.
"""
import hashlib
from pathlib import Path

import cv2
import numpy as np
from pydantic import Field

from .contracts import BoundingBox, Contract

MODEL_SHA256 = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
MODEL_SIZE = 35858002
MODEL_VERSION = "opencv-zoo:yolox_s:2022nov:c5c2d13e"
COCO_CLASSES = tuple("person bicycle car motorcycle airplane bus train truck boat traffic_light fire_hydrant stop_sign parking_meter bench bird cat dog horse sheep cow elephant bear zebra giraffe backpack umbrella handbag tie suitcase frisbee skis snowboard sports_ball kite baseball_bat baseball_glove skateboard surfboard tennis_racket bottle wine_glass cup fork knife spoon bowl banana apple sandwich orange broccoli carrot hot_dog pizza donut cake chair couch potted_plant bed dining_table toilet tv laptop mouse remote keyboard cell_phone microwave oven toaster sink refrigerator book clock vase scissors teddy_bear hair_drier toothbrush".split())


class ObjectDetection(Contract):
    class_id: int = Field(ge=0, le=79)
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox


def verify_model(path):
    file = Path(path)
    if file.stat().st_size != MODEL_SIZE:
        raise ValueError("model size mismatch")
    digest = hashlib.sha256()
    with file.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_SHA256:
        raise ValueError("model checksum mismatch")
    return file


class YOLOXDetector:
    def __init__(self, path):
        verified = verify_model(path)
        cv2.setNumThreads(1)
        data = verified.read_bytes()
        if len(data) != MODEL_SIZE or hashlib.sha256(data).hexdigest() != MODEL_SHA256:
            raise ValueError("model changed before load")
        self.net = cv2.dnn.readNetFromONNX(np.frombuffer(data, dtype=np.uint8))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        grids, strides = [], []
        for stride in (8, 16, 32):
            y, x = np.mgrid[:640 // stride, :640 // stride]
            grids.append(np.column_stack((x.ravel(), y.ravel())))
            strides.append(np.full((x.size, 1), stride, dtype=np.float32))
        self.grids = np.concatenate(grids)
        self.strides = np.concatenate(strides)

    def detect(self, frame, *, classes=(0,), confidence=.5):
        if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8 or frame.size == 0:
            raise ValueError("invalid detector frame")
        if not classes:
            return []
        h, w = frame.shape[:2]
        scale = min(640 / w, 640 / h)
        canvas = np.full((640, 640, 3), 114, dtype=np.float32)
        resized = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), (max(1, int(w * scale)), max(1, int(h * scale))))
        canvas[:resized.shape[0], :resized.shape[1]] = resized
        self.net.setInput(np.transpose(canvas, (2, 0, 1))[None])
        output = self.net.forward()
        return self.postprocess(output, w, h, scale, classes, confidence)

    def postprocess(self, output, width, height, scale, classes, confidence):
        if output.shape != (1, 8400, 85) or not np.isfinite(output).all():
            raise ValueError("invalid YOLOX output contract")
        values = output[0]
        scores = values[:, 4, None] * values[:, 5:]
        class_ids = scores.argmax(axis=1)
        best = scores[np.arange(len(scores)), class_ids]
        mask = (best >= confidence) & np.isin(class_ids, classes)
        indices = np.flatnonzero(mask)
        # Bound NMS work even for corrupted/unexpected high-confidence predictions.
        indices = indices[np.argsort(-best[indices], kind="stable")[:1000]]
        if not len(indices):
            return []
        center = (values[indices, :2] + self.grids[indices]) * self.strides[indices]
        dimensions = np.exp(np.clip(values[indices, 2:4], -16, 16)) * self.strides[indices]
        xywh = np.column_stack((center - dimensions / 2, dimensions))
        keep = cv2.dnn.NMSBoxesBatched(xywh.tolist(), best[indices].tolist(), class_ids[indices].tolist(), confidence, .45)
        result = []
        for candidate in np.asarray(keep).reshape(-1)[:100]:
            index = indices[candidate]
            x, y, bw, bh = xywh[candidate] / scale
            x1, y1 = max(0., x / width), max(0., y / height)
            x2, y2 = min(1., (x + bw) / width), min(1., (y + bh) / height)
            if x1 >= x2 or y1 >= y2:
                continue
            result.append(ObjectDetection(class_id=int(class_ids[index]), confidence=min(1., float(best[index])),
                          bbox=BoundingBox(x_min=x1, y_min=y1, x_max=x2, y_max=y2)))
        return result
