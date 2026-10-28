"""Per-camera capture supervisor with two bounded, independent sampling lanes."""
import multiprocessing as mp
import os
from pathlib import Path
import queue
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

import numpy as np

from app.capture_lease import CaptureLease
from .config import CameraConfig
from .contracts import CameraScope
from .source import FrameMailbox, ProcessStop, decoder_main, guarded_decoder


def process_resources(pid=None):
    """Linux process counters, not machine capacity; None on unsupported hosts."""
    pid = pid or os.getpid()
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "cpu_seconds": (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"),
                "rss_bytes": int(fields[21]) * os.sysconf("SC_PAGE_SIZE")}
    except (OSError, ValueError, IndexError):
        return None


@dataclass(frozen=True)
class Frame:
    scope: CameraScope
    session_id: str
    sequence: int
    timestamp: datetime
    captured_monotonic: float
    decode_latency_ms: float
    pixels: np.ndarray = field(repr=False, compare=False)


class CameraWorker:
    def __init__(self, config: CameraConfig, *, decoder_target=decoder_main, lease_id=None):
        self.config = config
        self.scope = CameraScope(camera_id=config.camera_id, owner_id=config.owner_id,
                                 organization_id=config.organization_id)
        self._lease_id = lease_id or config.camera_id
        self._lease = None
        self._target = decoder_target
        self._ctx = mp.get_context("spawn")
        self._stop = threading.Event()
        self._thread = None
        self._process = None
        self._lifecycle_lock = threading.Lock()
        self._lock = threading.Lock()
        self._lanes = {name: queue.Queue(maxsize=config.queue_size) for name in ("recording", "inference")}
        self._decode_times = deque(maxlen=256)
        self._counts = Counter()
        self._ages = {name: deque(maxlen=256) for name in self._lanes}
        self._last_frame = None
        self._last_decoder_resources = None
        self._last_error = None
        self._started = None
        self._state = "stopped"
        self.session_id = str(uuid4())

    def start(self):
        with self._lifecycle_lock:
            if self._thread and self._thread.is_alive():
                return
            self._lease = CaptureLease(self._lease_id).acquire()
            self._stop.clear()
            for lane in self._lanes.values():
                self._clear(lane)
            with self._lock:
                self.session_id = str(uuid4())
                self._counts.clear()
                self._decode_times.clear()
                self._last_decoder_resources = None
                for ages in self._ages.values():
                    ages.clear()
                self._last_frame = None
                self._last_error = None
                self._started = time.monotonic()
                self._state = "starting"
            self._thread = threading.Thread(target=self._run, name=f"vision-{self.config.camera_id}", daemon=True)
            try:
                self._thread.start()
            except BaseException:
                self._lease.release()
                raise

    def stop(self):
        with self._lifecycle_lock:
            self._stop.set()
            if self._thread:
                # The supervisor bounds child join/terminate/kill independently.
                self._thread.join(self.config.shutdown_timeout_seconds + 2)
                if self._thread.is_alive():
                    raise RuntimeError("vision supervisor did not stop within its deadline")
            for lane in self._lanes.values():
                self._clear(lane)
            if self._lease:
                self._lease.release()
                self._lease = None

    @staticmethod
    def _clear(lane):
        while True:
            try:
                lane.get_nowait()
            except queue.Empty:
                return

    @property
    def is_alive(self):
        return bool(self._thread and self._thread.is_alive())

    @property
    def decoder_pid(self):
        process = self._process
        return process.pid if process and process.is_alive() else None

    def get_frame(self, lane: str, timeout: float = 0):
        """Nonblocking by default; expired frames are discarded even after source loss."""
        if lane not in self._lanes:
            raise ValueError("unknown frame lane")
        deadline = time.monotonic() + timeout
        while True:
            try:
                frame = self._lanes[lane].get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                return None
            age = time.monotonic() - frame.captured_monotonic
            with self._lock:
                if age > self.config.stale_after_seconds:
                    self._counts[f"{lane}_stale"] += 1
                else:
                    self._counts[f"{lane}_consumed"] += 1
                    self._ages[lane].append(age * 1000)
                    return frame
            if time.monotonic() >= deadline:
                return None

    def metrics(self):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._started if self._started else 0
            last_age = now - self._last_frame if self._last_frame is not None else None
            result = {
                **self.scope.model_dump(mode="json"), "worker_session_id": self.session_id,
                "state": self._state, "healthy": self._state == "streaming" and last_age is not None
                    and last_age <= self.config.stale_after_seconds,
                "last_error": self._last_error, "uptime_seconds": round(elapsed, 3),
                "last_frame_age_seconds": round(last_age, 3) if last_age is not None else None,
                "counts": dict(self._counts),
                "capture_fps_observed": self._counts["frames_received"] / elapsed if elapsed else 0,
                "queue_depth": {name: lane.qsize() for name, lane in self._lanes.items()},
                "queue_capacity": self.config.queue_size,
                "configured_fps": {"capture": self.config.capture_fps, "recording": self.config.recording_fps,
                                   "inference": self.config.inference_fps},
                "decode_latency_ms": {
                    "sample_count": len(self._decode_times),
                    "p50": sorted(self._decode_times)[(len(self._decode_times)-1)//2] if self._decode_times else None,
                    "p95": sorted(self._decode_times)[int((len(self._decode_times)-1)*.95)] if self._decode_times else None,
                },
                "frame_age_ms": {},
                "decoder_resources": process_resources(self.decoder_pid) if self.decoder_pid else self._last_decoder_resources,
            }
            for lane, values in self._ages.items():
                ordered = sorted(values)
                result["frame_age_ms"][lane] = {
                    "sample_count": len(ordered),
                    "p50": ordered[(len(ordered)-1)//2] if ordered else None,
                    "p95": ordered[int((len(ordered)-1)*.95)] if ordered else None,
                }
            return result

    def _offer(self, name, frame):
        lane = self._lanes[name]
        try:
            lane.put_nowait(frame)
        except queue.Full:
            try:
                lane.get_nowait()
                with self._lock:
                    self._counts[f"{name}_dropped"] += 1
            except queue.Empty:
                pass
            lane.put_nowait(frame)  # Only the supervisor produces into this lane.
        with self._lock:
            self._counts[f"{name}_sampled"] += 1

    def _dispose(self, process, channel, child_stop):
        self._last_decoder_resources = process_resources(process.pid) or self._last_decoder_resources
        child_stop.set()
        process.join(self.config.shutdown_timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(.25)
        if process.is_alive():
            process.kill()
            process.join(.25)
        with self._lock:
            self._counts["decoder_exits"] += 1

    def _run(self):
        backoff = self.config.reconnect_initial_seconds
        next_due = {name: 0 for name in self._lanes}
        sequence = 0
        try:
            while not self._stop.is_set():
                channel = FrameMailbox(self._ctx, self.config)
                child_stop = ProcessStop(self._ctx)
                process = self._ctx.Process(target=guarded_decoder, args=(self._target, self.config, channel, child_stop, os.getpid()), daemon=True)
                self._process = process
                process.start()
                with self._lock:
                    self._state = "connecting"
                    self._counts["connection_attempts"] += 1
                deadline = time.monotonic() + self.config.open_timeout_seconds
                # Includes process spawn, imports, DNS and native open.
                opened = False
                last_source_sequence = 0
                try:
                    while not self._stop.is_set():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            with self._lock:
                                self._last_error = "read_timeout" if opened else "open_timeout"
                                self._counts[self._last_error] += 1
                            break
                        message = channel.read()
                        if message is None:
                            if not process.is_alive():
                                with self._lock:
                                    self._last_error = "decoder_exit"
                                    self._counts["decoder_exit"] += 1
                                break
                            self._stop.wait(min(.01, remaining))
                            continue
                        kind, payload = message
                        if kind == "opened":
                            opened = True
                            deadline = time.monotonic() + self.config.read_timeout_seconds
                            continue
                        if kind == "error":
                            with self._lock:
                                self._last_error = payload
                                self._counts["source_errors"] += 1
                            break
                        if kind != "frame":
                            continue
                        source_sequence, timestamp, captured, pixels, decode_ms = payload
                        with self._lock:
                            self._counts["capture_dropped"] += max(0, source_sequence - last_source_sequence - 1)
                        last_source_sequence = source_sequence
                        now = time.monotonic()
                        deadline = now + self.config.read_timeout_seconds
                        opened = True
                        backoff = self.config.reconnect_initial_seconds
                        sequence += 1
                        pixels.setflags(write=False)
                        frame = Frame(self.scope, self.session_id, sequence, timestamp, captured, decode_ms, pixels)
                        with self._lock:
                            self._state = "streaming"
                            self._last_error = None
                            self._last_frame = captured
                            self._counts["frames_received"] += 1
                            self._decode_times.append(decode_ms)
                        if now - captured > self.config.stale_after_seconds:
                            with self._lock:
                                self._counts["capture_stale"] += 1
                            continue
                        for name in self._lanes:
                            if now >= next_due[name]:
                                self._offer(name, frame)
                                interval = 1 / getattr(self.config, f"{name}_fps")
                                next_due[name] = max(next_due[name] + interval, now) if next_due[name] else now + interval
                finally:
                    self._dispose(process, channel, child_stop)
                    self._process = None
                with self._lock:
                    self._state = "reconnecting" if not self._stop.is_set() else "stopping"
                if self._stop.wait(backoff):
                    break
                with self._lock:
                    self._counts["reconnections"] += 1
                backoff = min(backoff * 2, self.config.reconnect_max_seconds)
        except Exception:
            # Never put raw native exceptions or source values in metrics/logs.
            with self._lock:
                self._last_error = "supervisor_failed"
                self._counts["supervisor_errors"] += 1
        finally:
            if self._lease:
                self._lease.release()
            with self._lock:
                self._state = "stopped"
