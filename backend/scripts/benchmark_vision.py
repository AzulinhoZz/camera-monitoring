"""Short synthetic 1/2/4-camera CPU smoke, shared verified model and bounded memory.

Not an accuracy benchmark. Run on permitted fixtures only; stops/skips when the
configured RSS budget is exceeded. Model inference is real, never mocked.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import time
import threading
from uuid import UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from app.vision.config import CameraConfig
from app.vision.detection import YOLOXDetector, MODEL_VERSION
from app.vision.pipeline import ObjectPipeline
from app.vision.worker import CameraWorker, process_resources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True)
    parser.add_argument('--seconds',type=float,default=6)
    parser.add_argument('--cameras',nargs='+',type=int,choices=(1,2,4),default=[1,2,4])
    parser.add_argument('--memory-mib',type=int,default=512)
    parser.add_argument('--inference-fps',type=float,default=1)
    args=parser.parse_args()
    if not math.isfinite(args.seconds) or not 2<=args.seconds<=60 or not 128<=args.memory_mib<=2048:
        parser.error('invalid benchmark limits')
    if not math.isfinite(args.inference_fps) or not .1<=args.inference_fps<=10:parser.error('inference FPS must be between .1 and 10')
    detector=YOLOXDetector(args.model)
    from app.vision.source import synthetic_frame
    detector.detect(synthetic_frame(0,160,120),classes=(0,2,5),confidence=.5)  # Unmeasured warm-up.
    results=[]
    decoder_bytes=0
    for count in sorted(set(args.cameras)):
        parent=process_resources()
        if decoder_bytes and parent and parent['rss_bytes']+decoder_bytes*count>args.memory_mib*1024**2:
            results.append({'cameras':count,'status':'NOT RUN: estimated memory exceeds budget'})
            continue
        workers=[];pipelines=[]
        for index in range(count):
            config=CameraConfig(camera_id=UUID(int=index+1),owner_id=UUID(int=100),source_kind='synthetic',
                                max_width=160,max_height=120,capture_fps=10,recording_fps=5,inference_fps=args.inference_fps,
                                vision_enabled=True,object_classes=(0,2,5),open_timeout_seconds=5)
            workers.append(CameraWorker(config));pipelines.append(ObjectPipeline(config,detector))
        peak=0;exceeded=False
        stop=threading.Event()
        def drain_recording(worker):
            while not stop.is_set():worker.get_frame('recording',timeout=.1)
        recorders=[threading.Thread(target=drain_recording,args=(worker,),daemon=True) for worker in workers]
        started=time.monotonic();cpu_start=time.process_time()
        try:
            for worker in workers:worker.start()
            for recorder in recorders:recorder.start()
            while time.monotonic()-started<args.seconds:
                for worker,pipeline in zip(workers,pipelines):
                    if time.monotonic()-started>=args.seconds:break
                    frame=worker.get_frame('inference')
                    if frame: pipeline.process(frame)
                snapshot=[worker.metrics() for worker in workers]
                own=process_resources()
                total=(own['rss_bytes'] if own else 0)+sum((s.get('decoder_resources') or {}).get('rss_bytes',0) for s in snapshot)
                peak=max(peak,total)
                if total>args.memory_mib*1024**2:
                    exceeded=True;break
                time.sleep(.01)
        finally:
            stop.set()
            for recorder in recorders:
                if recorder.is_alive():recorder.join(1)
            for worker in workers:worker.stop()
        elapsed=time.monotonic()-started
        snapshot=[worker.metrics() for worker in workers]
        decoder_bytes=max(decoder_bytes,max(((s.get('decoder_resources') or {}).get('rss_bytes',0) for s in snapshot),default=0))
        results.append({'cameras':count,'status':'STOPPED: RSS budget exceeded' if exceeded else 'completed',
                        'wall_seconds':elapsed,'parent_cpu_seconds':time.process_time()-cpu_start,
                        'peak_summed_rss_mib':peak/1024**2,
                        'inference_frames':[p.processed for p in pipelines],
                        'inference_fps_per_camera':[p.processed/elapsed for p in pipelines],
                        'inference':[p.metrics() for p in pipelines],
                        'capture':[s['counts'] for s in snapshot]})
    print(json.dumps({'workload':'synthetic geometric frames 160x120, ONNX input 640x640',
                      'model_version':MODEL_VERSION,'threads':1,'rss_budget_mib':args.memory_mib,'configured_inference_fps':args.inference_fps,'results':results},indent=2))


if __name__=='__main__':main()
