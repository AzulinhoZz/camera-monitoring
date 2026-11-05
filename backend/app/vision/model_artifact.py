"""Pinned model identity and integrity verification; standard library only."""
import hashlib
from pathlib import Path

MODEL_SHA256 = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
MODEL_SIZE = 35858002
MODEL_VERSION = "opencv-zoo:yolox_s:2022nov:c5c2d13e"


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
