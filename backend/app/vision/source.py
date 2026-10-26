"""Disposable decoder subprocess: watchdog in parent also bounds native blocking I/O."""
import os
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from .config import CameraConfig, checked_rtsp_url


class ProcessStop:
    """Lock-free cancellation flag: safe even if a child is killed in wait()."""
    def __init__(self, context):
        self._value = context.RawValue("b", 0)

    def is_set(self):
        return bool(self._value.value)

    def set(self):
        self._value.value = 1

    def wait(self, seconds):
        deadline = time.monotonic() + seconds
        while not self.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(.01, remaining))
        return self.is_set()


class FrameMailbox:
    """One fixed-size frame slot, never a pipe carrying partially written images.

    A child killed inside the critical section can leave its lock acquired. Both
    sides use timed acquisition; the parent watchdog abandons the entire mailbox
    and creates a new one on reconnect. No unbounded get()/join_thread() calls.
    """
    _ERRORS = {"open_failed": -1, "read_failed": -2, "invalid_frame": -3, "source_failed": -4}

    def __init__(self, context, config):
        self._pixels = context.RawArray("B", config.max_width * config.max_height * 3)
        self._shape = context.RawArray("i", 2)
        self._timing = context.RawArray("d", 3)
        self._sequence = context.RawValue("Q", 0)
        self._revision = context.RawValue("Q", 0)
        self._status = context.RawValue("i", 0)
        self._lock = context.Lock()
        self._seen = 0

    def put(self, message):
        if not self._lock.acquire(timeout=.01):
            return
        try:
            kind, payload = message
            if kind == "opened":
                self._status.value = 1
            elif kind == "error":
                self._status.value = self._ERRORS.get(payload, -4)
            else:
                sequence, timestamp, captured, frame, decode_ms = payload
                flat = frame.reshape(-1)
                if flat.size > len(self._pixels):
                    self._status.value = -3
                else:
                    np.copyto(np.frombuffer(self._pixels, dtype=np.uint8)[:flat.size], flat)
                    self._shape[0], self._shape[1] = frame.shape[:2]
                    self._timing[0], self._timing[1], self._timing[2] = timestamp.timestamp(), captured, decode_ms
                    self._sequence.value = sequence
                    self._status.value = 2
            self._revision.value += 1
        finally:
            self._lock.release()

    def read(self):
        if not self._lock.acquire(timeout=.01):
            return None
        try:
            if self._revision.value == self._seen:
                return None
            self._seen = self._revision.value
            status = self._status.value
            if status == 1:
                return "opened", None
            if status < 0:
                return "error", next((name for name, code in self._ERRORS.items() if code == status), "source_failed")
            if status == 2:
                h, w = self._shape[:]
                pixels = np.frombuffer(self._pixels, dtype=np.uint8)[:h*w*3].reshape(h, w, 3).copy()
                return "frame", (self._sequence.value, datetime.fromtimestamp(self._timing[0], timezone.utc), self._timing[1], pixels, self._timing[2])
            return None
        finally:
            self._lock.release()


def offer_latest(channel, value):
    channel.put(value)


def decoder_main(config: CameraConfig, channel, stop):
    # Native FFmpeg/OpenCV diagnostics can contain URLs. Report typed status only.
    with open(os.devnull, "w") as quiet:
        os.dup2(quiet.fileno(), 2)
    cv2.setNumThreads(1)
    cap = None
    try:
        if config.source_kind == "rtsp":
            source = checked_rtsp_url(config)  # DNS work is inside watchdog boundary.
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        else:
            source = config.source
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "protocol_whitelist;file"
        if config.source_kind != "synthetic":
            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(config.open_timeout_seconds * 1000),
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(config.read_timeout_seconds * 1000),
            ])
            if not cap.isOpened():
                offer_latest(channel, ("error", "open_failed"))
                return
        offer_latest(channel, ("opened", None))
        sequence = 0
        next_frame = time.monotonic()
        while not stop.is_set():
            if stop.wait(max(0, next_frame - time.monotonic())):
                break
            capture_started = time.monotonic()
            if config.source_kind == "synthetic":
                frame = synthetic_frame(sequence, config.max_width, config.max_height)
            else:
                ok, frame = cap.read()
                if not ok or frame is None or frame.size == 0:
                    offer_latest(channel, ("error", "read_failed"))
                    return  # Always reopen after read failure, even if isOpened=True.
            if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
                offer_latest(channel, ("error", "invalid_frame"))
                return
            h, w = frame.shape[:2]
            scale = min(1.0, config.max_width / w, config.max_height / h)
            if scale < 1:
                frame = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))))
            sequence += 1
            offer_latest(channel, ("frame", (sequence, datetime.now(timezone.utc), time.monotonic(), frame, (time.monotonic() - capture_started) * 1000)))
            next_frame = max(next_frame + 1 / config.capture_fps, time.monotonic())
    except Exception:
        offer_latest(channel, ("error", "source_failed"))
    finally:
        if cap is not None:
            cap.release()


def synthetic_frame(sequence: int, width: int = 640, height: int = 480):
    """Original geometric fixture, no images, personal data or external model weights."""
    frame = np.full((height, width, 3), 48, dtype=np.uint8)
    size = max(4, min(width, height) // 6)
    x = (sequence * 7) % max(1, width - size)
    y = height // 3
    cv2.rectangle(frame, (x, y), (x + size, min(height - 1, y + size)), (220, 220, 220), -1)
    return frame
