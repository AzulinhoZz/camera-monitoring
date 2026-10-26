"""Opt-in operator entrypoint. Drains frame lanes only; never emits AI detections."""
import argparse
import json
import math
import signal
import sys
import threading
import time
from pathlib import Path

from .config import WorkerConfig
from .worker import CameraWorker, process_resources


def write_health(filename, snapshot):
    if filename:
        path = Path(filename)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(snapshot))
        temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--duration", type=float, default=0, help="seconds; 0 runs until SIGTERM")
    parser.add_argument("--health-file", default="/tmp/vision-health.json")
    args = parser.parse_args(argv)
    if not math.isfinite(args.duration) or args.duration < 0:
        parser.error("duration must be finite and nonnegative")
    try:
        config = WorkerConfig.load(args.config)
    except Exception:
        print("Invalid server vision configuration; source details suppressed", file=sys.stderr)
        return 2
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    workers = [CameraWorker(camera) for camera in config.cameras]
    started = time.monotonic()
    next_metrics = started
    result = 0
    try:
        for worker in workers:
            worker.start()
        while not stop.is_set():
            now = time.monotonic()
            for worker in workers:
                # Placeholder consumers: capture infrastructure only. No DB, FCM,
                # clip upload, detector model or default-sensitive alert side effects.
                for lane in ("recording", "inference"):
                    worker.get_frame(lane)
            if now >= next_metrics:
                metrics = [worker.metrics() for worker in workers]
                snapshot = {"schema_version": "1.0", "timestamp_unix": time.time(),
                            "healthy": all(m["healthy"] for m in metrics), "supervisor_resources": process_resources(), "cameras": metrics}
                print(json.dumps(snapshot), flush=True)
                write_health(args.health_file, snapshot)
                next_metrics = now + config.metrics_interval_seconds
            if any(not worker.is_alive for worker in workers):
                result = 1
                break
            if args.duration and now - started >= args.duration:
                break
            stop.wait(.01)
        if any(not w.metrics()["counts"].get("frames_received") for w in workers):
            result = 1
    finally:
        for worker in workers:
            worker.stop()
        snapshot = {"schema_version": "1.0", "timestamp_unix": time.time(),
                    "healthy": False, "cameras": [w.metrics() for w in workers]}
        print(json.dumps(snapshot), flush=True)
        write_health(args.health_file, snapshot)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
