"""Local-only RTSP fault smoke. Requires Docker + ffmpeg; never opens real cameras."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from app.vision.config import CameraConfig
from app.vision.source import synthetic_frame
from app.vision.worker import CameraWorker

IMAGE = "bluenviron/mediamtx@sha256:59e43552f3be43695b70c19424dc2a42fcec18075f88d91561a24ac5d70a586c"


def wait_for(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.05)
    raise RuntimeError("local RTSP smoke deadline exceeded")


def main():
    name = f"vision-smoke-{uuid4().hex[:12]}"
    gateway = Path(__file__).resolve().parents[1] / "app/tests/fixtures/mediamtx-open.yml"
    worker = publisher = None
    created = False
    try:
        subprocess.run(["docker", "run", "--rm", "-d", "--name", name,
                        "-p", "127.0.0.1::8554", "--mount",
                        f"type=bind,src={gateway},dst=/mediamtx.yml,readonly", IMAGE],
                       check=True, capture_output=True)
        created = True
        binding = subprocess.run(["docker", "port", name, "8554/tcp"], check=True,
                                 capture_output=True, text=True).stdout.strip()
        port = int(binding.rsplit(":", 1)[1])
        url = f"rtsp://127.0.0.1:{port}/geometric"
        with tempfile.TemporaryDirectory(prefix="vision-smoke-") as directory:
            path = Path(directory) / "geometric.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 15, (160, 120))
            if not writer.isOpened():
                raise RuntimeError("MJPG fixture codec unavailable")
            for sequence in range(45):
                writer.write(synthetic_frame(sequence, 160, 120))
            writer.release()
            with (Path(directory) / "ffmpeg.log").open("w") as logfile:
                def publish():
                    return subprocess.Popen([
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-re", "-stream_loop", "-1",
                        "-i", str(path), "-an", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                        "-g", "15", "-keyint_min", "15", "-sc_threshold", "0", "-pix_fmt", "yuv420p",
                        "-f", "rtsp", "-rtsp_transport", "tcp", url
                    ], stdout=logfile, stderr=logfile)
                publisher = publish()
                worker = CameraWorker(CameraConfig(
                    camera_id="00000000-0000-0000-0000-000000000001",
                    owner_id="00000000-0000-0000-0000-000000000002",
                    source_kind="rtsp", source=url, allowed_cidrs=("127.0.0.0/8",),
                    allow_loopback=True, allowed_ports=(port,), capture_fps=15,
                    recording_fps=10, inference_fps=3, max_width=160, max_height=120,
                    open_timeout_seconds=8, read_timeout_seconds=3, stale_after_seconds=.5))
                worker.start()
                wait_for(lambda: worker.metrics()["counts"].get("frames_received", 0) >= 5)
                if publisher.poll() is not None:
                    raise RuntimeError("local publisher failed")
                publisher.terminate()
                publisher.wait(5)
                wait_for(lambda: worker.metrics()["counts"].get("source_errors", 0)
                         + worker.metrics()["counts"].get("read_timeout", 0) > 0)
                previous = worker.metrics()["counts"]["frames_received"]
                publisher = publish()
                wait_for(lambda: worker.metrics()["counts"].get("frames_received", 0) > previous + 5)
                if worker.metrics()["counts"]["connection_attempts"] < 2:
                    raise RuntimeError("reconnect was not exercised")
                # Exercise both consumers; this does not invoke an inference model.
                if not worker.get_frame("recording") or not worker.get_frame("inference"):
                    raise RuntimeError("no fresh frames available to consumers")
                print(json.dumps(worker.metrics()), flush=True)
                print("PASS: geometric RTSP decode, publisher interruption and recovery")
    finally:
        if worker:
            worker.stop()
        if publisher and publisher.poll() is None:
            publisher.terminate()
            publisher.wait(5)
        if created:
            subprocess.run(["docker", "stop", name], check=True, capture_output=True)


if __name__ == "__main__":
    main()
