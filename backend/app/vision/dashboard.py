"""Opt-in, atomic, bounded snapshots on a private tmpfs shared by trusted services."""
import base64
from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import tempfile
from typing import Literal
from uuid import UUID

import cv2
from pydantic import Field, field_validator
from .contracts import CameraScope, Contract

MAX_BYTES = 1024 * 1024
TTL = 10


class Snapshot(CameraScope):
    schema_version: Literal['1.0'] = '1.0'
    session: UUID
    published_at: datetime
    frame_at: datetime | None = None
    healthy: bool
    state: Literal['starting', 'streaming', 'backoff', 'stopped', 'unavailable']
    capture_fps: float = Field(ge=0, le=1000)
    inference_fps: float = Field(default=0, ge=0, le=1000)
    inference_frames: int = Field(ge=0)
    inference_dropped: int = Field(ge=0)
    rss_bytes: int = Field(ge=0)
    cpu_seconds: float = Field(ge=0)
    model_version: str = Field(max_length=160)
    image: str | None = Field(default=None, max_length=450000)
    overlay_image: str | None = Field(default=None, max_length=450000)

    @field_validator('published_at', 'frame_at')
    @classmethod
    def aware(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('UTC timestamp required')
        return value.astimezone(timezone.utc) if value else None


def directory(path):
    root = Path(path)
    if not root.is_absolute() or root.is_symlink():
        raise ValueError('private absolute dashboard directory required')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('dashboard directory must be private and owned by this service UID')
    return root


def write_snapshot(root, snapshot):
    root = directory(root)
    data = snapshot.model_dump_json().encode()
    if len(data) > MAX_BYTES:
        raise ValueError('dashboard snapshot exceeds budget')
    with tempfile.NamedTemporaryFile(dir=root, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temp, root / f'{snapshot.camera_id}.json')
    finally:
        temp.unlink(missing_ok=True)


def read_snapshot(root, scope, now=None):
    root = directory(root)
    path = root / f'{scope.camera_id}.json'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError('dashboard file must be private and owned by this service UID')
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError('invalid dashboard file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        snapshot = Snapshot.model_validate_json(data)
    finally:
        os.close(fd)
    if CameraScope(**{k:getattr(snapshot,k) for k in CameraScope.model_fields}) != scope:
        raise ValueError('dashboard tenant changed')
    now = now or datetime.now(timezone.utc)
    age = (now - snapshot.published_at).total_seconds()
    if not 0 <= age <= TTL:
        raise ValueError('dashboard expired')
    return snapshot


def preview(frame, events, packet=None):
    from .contracts import DetectionEvent
    from .pose_rendering import draw_skeleton
    pixels = frame.pixels
    drawing = pixels.copy()
    for value in events[:100]:
        event = DetectionEvent.model_validate(value).require_scope(frame.scope)
        if event.timestamp != frame.timestamp or str(event.worker_session_id) != frame.session_id:
            raise ValueError('overlay frame mismatch')
        b = event.bbox
        height, width = drawing.shape[:2]
        cv2.rectangle(drawing, (int(b.x_min*width), int(b.y_min*height)),
                      (min(width-1,int(b.x_max*width)), min(height-1,int(b.y_max*height))), (0,255,255), 2)
    if packet is not None:
        if packet.timestamp != frame.timestamp or packet.frame_sequence != frame.sequence or str(packet.worker_session_id) != frame.session_id:
            raise ValueError('skeleton frame mismatch')
        drawing = draw_skeleton(drawing, packet, frame.scope)
    def encode(image):
        h,w=image.shape[:2]
        image=cv2.resize(image,(min(w,640),max(1,round(h*min(w,640)/w))))
        ok, data=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,65])
        if not ok or len(data)>330000:raise ValueError('preview encoding budget')
        return base64.b64encode(data).decode('ascii')
    return encode(pixels), encode(drawing)
