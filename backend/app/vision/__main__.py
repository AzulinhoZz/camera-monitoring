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
    parser.add_argument("--persist-events", action="store_true", help="explicit server opt-in to scoped rules/event/media persistence; requires --resolve-scopes")
    parser.add_argument("--pose-runtime-python", help="explicit isolated Python with audited bundled MediaPipe runtime")
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
        revisions = {}
        if args.persist_events or any(c.source_kind == "rtsp" for c in config.cameras):
            if not args.resolve_scopes:
                raise ValueError("real RTSP requires the server scope registry")
            from supabase import create_client, ClientOptions
            registry_client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"], options=ClientOptions(postgrest_client_timeout=5, storage_client_timeout=5))
            config = authorize_scopes(config, registry_client)
        if args.persist_events:
            from .persistence import load_rules
            from .contracts import CameraScope
            cameras=[]
            for camera in config.cameras:
                scope=CameraScope(camera_id=camera.camera_id,owner_id=camera.owner_id,organization_id=camera.organization_id)
                revision,rules=load_rules(registry_client,scope)
                revisions[camera.camera_id]=revision
                cameras.append(camera.model_copy(update={'rules':rules if camera.vision_enabled else ()}))
            config=config.model_copy(update={'cameras':tuple(cameras)})
        pose_enabled=any(c.pose_enabled for c in config.cameras)
        if pose_enabled!=bool(args.pose_runtime_python):
            raise ValueError("pose runtime and camera opt-in must both be configured")
        if pose_enabled:
            from .pose_process import validate_pose_budget
            validate_pose_budget(config.cameras)
            runtime=Path(args.pose_runtime_python)
            if not runtime.is_absolute() or not runtime.is_file() or not os.access(runtime,os.X_OK):
                raise ValueError("pose runtime unavailable")
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
    from .pose_process import PoseProcess
    from .actions import TemporalActions,associated_person
    from .contracts import CameraScope
    pose_clients={c.camera_id:PoseProcess(CameraScope(camera_id=c.camera_id,owner_id=c.owner_id,organization_id=c.organization_id),args.pose_runtime_python) for c in config.cameras if c.pose_enabled}
    actions={c.camera_id:TemporalActions(pose_clients[c.camera_id].scope,gestures=c.hand_gestures_enabled,falls=c.fall_candidates_enabled) for c in config.cameras if c.pose_enabled}
    started = time.monotonic()
    next_metrics = started
    result = 0
    recording_threads = []
    dispatcher = None
    collectors = {}
    if args.persist_events:
        from .evidence import EvidenceCollector, EvidenceDispatcher
        dispatcher=EvidenceDispatcher(registry_client)
        collectors={camera_id:EvidenceCollector(pipeline.scope,dispatcher) for camera_id,pipeline in pipelines.items()}
    def drain_recording(worker):
        while not stop.is_set():
            frame=worker.get_frame("recording", timeout=.1)
            collector=collectors.get(worker.config.camera_id)
            if collector:
                if frame is not None:
                    collector.append(frame)
                collector.tick()

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
                    if args.persist_events:
                        for camera_id,pipeline in pipelines.items():
                            revision,rules=load_rules(registry_client,pipeline.scope)
                            if revisions[camera_id]!=revision:
                                from .rules import RuleEngine
                                pipeline.config=pipeline.config.model_copy(update={'rules':rules})
                                pipeline.rules=RuleEngine(pipeline.scope,rules)
                                revisions[camera_id]=revision
                except Exception:
                    result = 1
                    break  # Fail closed on revoked/moved camera or DB unavailability.
            for worker in workers:
                frame = worker.get_frame("inference")
                pipeline = pipelines.get(worker.config.camera_id)
                if frame is not None and (pipeline is not None or worker.config.camera_id in pose_clients):
                    try:
                        batch = pipeline.process(frame) if pipeline else {'events':[],'rule_events':[]}
                        if args.persist_events:
                            for event in batch['rule_events']:
                                collectors[worker.config.camera_id].offer(event,revisions[worker.config.camera_id],frame)
                        client=pose_clients.get(worker.config.camera_id)
                        if client:
                            packet=client.infer(frame)
                            if packet is not None and time.monotonic()-frame.captured_monotonic>worker.config.stale_after_seconds:
                                client.metrics['stale_results']+=1
                                packet=None
                            if packet is None:
                                actions[worker.config.camera_id].reset_candidates()
                            else:
                                signals=actions[worker.config.camera_id].process(packet,person_track_id=associated_person(packet,batch['events']))
                                # Human-review candidates remain a separate experimental contract.
                                # Never feed sensitive actions to rules, FCM or automatic evidence.
                                if args.emit_detections:
                                    batch['pose_signals']=[s.model_dump(mode='json') for s in signals]
                                batch['pose_observations']=len(packet.observations)
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
                    client=pose_clients.get(worker.config.camera_id)
                    if client:
                        row['pose']={**client.snapshot(),'actions':dict(actions[worker.config.camera_id].metrics)}
                    collector=collectors.get(worker.config.camera_id)
                    if collector:
                        row['evidence']=dict(collector.metrics)
                    metrics.append(row)
                snapshot = {"schema_version": "1.0", "timestamp_unix": time.time(),
                            "healthy": all(c.process is not None and c.process.poll() is None for c in pose_clients.values()) and (dispatcher is None or dispatcher.thread.is_alive()) and not stop.is_set() and all(recorder.is_alive() for recorder in recording_threads) and all(m["healthy"] for m in metrics), "supervisor_resources": process_resources(), "cameras": metrics, "event_io": dict(dispatcher.metrics) if dispatcher else {}, "delivery_degraded": bool(dispatcher and any(dispatcher.metrics[k] for k in ("failed","snapshot_failed","clip_failed","shutdown_pending"))) or any(c.metrics["queue_dropped"] for c in collectors.values())}
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
        for client in pose_clients.values():
            client.close()
        for collector in collectors.values():
            collector.close()
        if dispatcher:
            if not dispatcher.close() or any(dispatcher.metrics[k] for k in ('failed','snapshot_failed','clip_failed')):
                result=1
        if any(client.metrics['failed'] for client in pose_clients.values()):
            result=1
        if any(c.metrics['queue_dropped'] for c in collectors.values()):
            result=1
        snapshot = {"schema_version": "1.0", "timestamp_unix": time.time(),
                    "healthy": False, "cameras": [w.metrics() for w in workers], "event_io": dict(dispatcher.metrics) if dispatcher else {}, "delivery_degraded": bool(dispatcher and any(dispatcher.metrics[k] for k in ("failed","snapshot_failed","clip_failed","shutdown_pending"))) or any(c.metrics["queue_dropped"] for c in collectors.values())}
        print(json.dumps(snapshot), flush=True)
        write_health(args.health_file, snapshot)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
