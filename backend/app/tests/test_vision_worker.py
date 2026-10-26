import multiprocessing as mp
import time

import cv2
import pytest

from app.vision.config import CameraConfig
from app.vision.source import synthetic_frame
from app.vision.worker import CameraWorker


CAMERA = "00000000-0000-0000-0000-000000000001"
OWNER = "00000000-0000-0000-0000-000000000002"


def camera(**kwargs):
    return CameraConfig(camera_id=CAMERA, owner_id=OWNER, max_width=160, max_height=120, **kwargs)


def until(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.01)
    pytest.fail("condition did not become true within bounded deadline")


def blocked_open(config, channel, stop):
    # Ignores cancellation, emulating a stuck native decoder.
    time.sleep(60)


def blocked_mailbox(config, channel, stop):
    channel._lock.acquire()
    time.sleep(60)


def blocked_read(config, channel, stop):
    channel.put(("opened", None))
    time.sleep(60)


def test_bounded_lanes_independent_fps_scope_and_restart():
    worker = CameraWorker(camera(capture_fps=30, recording_fps=15, inference_fps=3, queue_size=2))
    try:
        worker.start()
        worker.start()  # Idempotent, no second decoder.
        until(lambda: worker.metrics()["counts"].get("frames_received", 0) >= 35)
        metrics = worker.metrics()
        assert metrics["healthy"]
        assert metrics["counts"]["connection_attempts"] == 1
        assert metrics["counts"]["recording_sampled"] > metrics["counts"]["inference_sampled"] * 2
        assert metrics["queue_depth"] == {"recording": 2, "inference": 2}
        assert metrics["counts"]["recording_dropped"] > 0
        frame = worker.get_frame("inference")
        assert str(frame.scope.camera_id) == CAMERA
        assert frame.scope.organization_id is None
        assert frame.timestamp.utcoffset().total_seconds() == 0
        assert frame.pixels.shape == (120, 160, 3)
        assert not frame.pixels.flags.writeable
        first_session = frame.session_id
        pid = worker.decoder_pid
        worker.stop()
        assert not worker.is_alive and worker.decoder_pid is None
        assert all(p.pid != pid for p in mp.active_children())
        worker.start()
        frame = until(lambda: worker.get_frame("inference"))
        assert frame.session_id != first_session
    finally:
        worker.stop()
    assert worker.get_frame("inference") is None


@pytest.mark.parametrize("target,error", [(blocked_open, "open_timeout"), (blocked_read, "read_timeout"), (blocked_mailbox, "open_timeout")])
def test_watchdog_kills_blocking_native_io(target, error):
    worker = CameraWorker(camera(open_timeout_seconds=2, read_timeout_seconds=.2,
                                 shutdown_timeout_seconds=.1, reconnect_initial_seconds=.05), decoder_target=target)
    try:
        worker.start()
        until(lambda: worker.metrics()["counts"].get(error, 0), timeout=6)
        start = time.monotonic()
        worker.stop()
        assert time.monotonic() - start < 2
        assert worker.decoder_pid is None and not worker.is_alive
        assert not worker.metrics()["healthy"]
    finally:
        worker.stop()


def test_decoder_crash_recovers_and_old_frames_expire():
    worker = CameraWorker(camera(stale_after_seconds=.1, reconnect_initial_seconds=.3))
    try:
        worker.start()
        until(lambda: worker.metrics()["counts"].get("frames_received", 0) >= 3)
        worker._process.kill()  # Simulated decoder crash; no camera/network involved.
        worker._process.join(1)
        time.sleep(.15)
        assert worker.get_frame("inference") is None
        assert not worker.metrics()["healthy"]
        until(lambda: worker.metrics()["counts"].get("reconnections", 0) >= 1)
        frame = until(lambda: worker.get_frame("inference"))
        assert frame.sequence >= 4
    finally:
        worker.stop()


@pytest.fixture
def permitted_video(tmp_path):
    # Original geometric frames, generated locally; no downloaded media.
    path = tmp_path / "geometric.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 15, (160, 120))
    assert writer.isOpened(), "fixture codec MJPG unavailable"
    for sequence in range(12):
        writer.write(synthetic_frame(sequence, 160, 120))
    writer.release()
    assert path.stat().st_size > 0
    return path


def test_real_video_decode_eof_reopens_without_stale_loop(permitted_video):
    worker = CameraWorker(camera(source_kind="video", source=str(permitted_video),
                                 capture_fps=30, recording_fps=15, inference_fps=3,
                                 reconnect_initial_seconds=.05))
    try:
        worker.start()
        frame = until(lambda: worker.get_frame("recording"))
        assert frame.pixels.shape == (120, 160, 3)
        until(lambda: worker.metrics()["counts"].get("source_errors", 0) >= 1)
        until(lambda: worker.metrics()["counts"].get("frames_received", 0) > 12)
        assert worker.metrics()["counts"]["connection_attempts"] >= 2
    finally:
        worker.stop()


def test_bad_video_fails_observably_and_stop_during_backoff(tmp_path):
    path = tmp_path / "corrupt.avi"
    path.write_bytes(b"not a video")
    worker = CameraWorker(camera(source_kind="video", source=str(path), reconnect_initial_seconds=5,
                                 reconnect_max_seconds=5))
    try:
        worker.start()
        until(lambda: worker.metrics()["counts"].get("source_errors", 0))
        assert not worker.metrics()["healthy"]
        assert worker.metrics()["counts"].get("frames_received", 0) == 0
        started = time.monotonic()
        worker.stop()
        assert time.monotonic() - started < 2
    finally:
        worker.stop()
