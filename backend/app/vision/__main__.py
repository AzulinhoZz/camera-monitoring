"""Opt-in operator entrypoint. Models require audited weights and per-camera opt-in."""
import argparse
import json
import math
import os
import signal
import sys
import threading
import time
from pathlib import Path

from .config import WorkerConfig
from .worker import CameraWorker, process_resources
from .registry import authorize_scopes


def write_health(filename, snapshot):
    if filename:
        path = Path(filename)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(snapshot))
        temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--emit-detections", action="store_true", help="export laboratory fixture events to stdout (not permitted for RTSP)")
    parser.add_argument("--model", help="audited YOLOX_s ONNX; only used for explicitly enabled cameras")
    parser.add_argument("--resolve-scopes", action="store_true", help="verify RTSP scopes against server camera registry")
    parser.add_argument("--duration", type=float, default=0, help="seconds; 0 runs until SIGTERM")
    parser.add_argument("--health-file", default="/tmp/vision-health.json")
    args = parser.parse_args(argv)
    if not math.isfinite(args.duration) or args.duration < 0:
        parser.error("duration must be finite and nonnegative")
    try:
        config = WorkerConfig.load(args.config)
        if args.emit_detections and any(c.source_kind == "rtsp" for c in config.cameras):
            raise ValueError("real stream events must not be written to diagnostic logs")
        registry_client = None
        if any(c.source_kind == "rtsp" for c in config.cameras):
            if not args.resolve_scopes:
                raise ValueError("real RTSP requires the server scope registry")
            from supabase import create_client
            registry_client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
            config = authorize_scopes(config, registry_client)
        detector = None
        enabled = any(c.vision_enabled for c in config.cameras)
        if enabled != bool(args.model):
            raise ValueError("model and camera opt-in must both be configured")
        if enabled:
            from .detection import YOLOXDetector
            detector = YOLOXDetector(args.model)
    except Exception:
        print("Invalid server vision configuration; source details suppressed", file=sys.stderr)
        return 2
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    workers = [CameraWorker(camera) for camera in config.cameras]
    from .pipeline import ObjectPipeline
    pipelines = {c.camera_id:ObjectPipeline(c,detector) for c in config.cameras if c.vision_enabled}
    started = time.monotonic()
    next_metrics = started
    result = 0
    recording_threads = []
    def drain_recording(worker):
        while not stop.is_set():
            worker.get_frame("recording", timeout=.1)

    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            recorder = threading.Thread(target=drain_recording, args=(worker,), name="vision-recording-consumer", daemon=True)
            recording_threads.append(recorder)
            recorder.start()
        while not stop.is_set():
            now = time.monotonic()
            if args.duration and now - started >= args.duration:
                break
            if now >= next_metrics and registry_client is not None:
                try:
                    refreshed = authorize_scopes(config, registry_client)
                    if any(old.source != new.source for old, new in zip(config.cameras, refreshed.cameras)):
                        raise ValueError("camera source changed")
                except Exception:
                    result = 1
                    break  # Fail closed on revoked/moved camera or DB unavailability.
            for worker in workers:
                frame = worker.get_frame("inference")
                pipeline = pipelines.get(worker.config.camera_id)
                if frame is not None and pipeline is not None:
                    try:
                        batch = pipeline.process(frame)
                        if args.emit_detections:
                            print(json.dumps(batch), flush=True)
                    except Exception:
                        print(json.dumps({"type":"inference_error","camera_id":str(worker.config.camera_id)}), flush=True)
                        result = 1
                        stop.set()
                        break
            if now >= next_metrics:
                metrics = []
                for worker in workers:
                    row=worker.metrics()
                    pipeline=pipelines.get(worker.config.camera_id)
                    if pipeline:
                        row["inference"]=pipeline.metrics()
                    metrics.append(row)
                snapshot = {"schema_version": "1.0", "timestamp_unix": time.time(),
                            "healthy": not stop.is_set() and all(recorder.is_alive() for recorder in recording_threads) and all(m["healthy"] for m in metrics), "supervisor_resources": process_resources(), "cameras": metrics}
                print(json.dumps(snapshot), flush=True)
                write_health(args.health_file, snapshot)
                next_metrics = now + config.metrics_interval_seconds
            if any(not worker.is_alive for worker in workers):
                result = 1
                break
            if args.duration and time.monotonic() - started >= args.duration:
                break
            stop.wait(.01)
        if any(not w.metrics()["counts"].get("frames_received") for w in workers):
            result = 1
    finally:
        stop.set()
        for recorder in recording_threads:
            recorder.join(1)
        for worker in workers:
            worker.stop()
        snapshot = {"schema_version": "1.0", "timestamp_unix": time.time(),
                    "healthy": False, "cameras": [w.metrics() for w in workers]}
        print(json.dumps(snapshot), flush=True)
        write_health(args.health_file, snapshot)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
