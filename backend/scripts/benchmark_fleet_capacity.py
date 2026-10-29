"""Local synthetic YOLOX capacity check: isolated CPU-affined camera groups, no remote I/O."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))


def main():
    from app.vision.config import WorkerConfig,CameraConfig
    from app.vision.fleet import admit
    from app.vision.detection import verify_model
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',required=True);p.add_argument('--output',required=True);p.add_argument('--duration',type=int,default=12);a=p.parse_args()
    if not 10<=a.duration<=60:p.error('duration must be 10..60 seconds')
    model=Path(a.model).resolve(strict=True);verify_model(model)
    output=Path(a.output);output.mkdir(parents=True,exist_ok=True,mode=0o700)
    results=[]
    for count in (1,2,4):
        config=WorkerConfig(cameras=tuple(CameraConfig(camera_id=UUID(int=i+1),owner_id=UUID(int=100),source_kind='synthetic',max_width=320,max_height=180,capture_fps=10,recording_fps=5,inference_fps=3,vision_enabled=True,object_classes=(0,)) for i in range(count)))
        try:admit(config,count*512,512,count)
        except ValueError:
            results.append({'cameras':count,'status':'NOT_RUN_ADMISSION_BUDGET'});continue
        run=output/f'{count}-cameras';run.mkdir(mode=0o700)
        dashboard=run/'dashboard';dashboard.mkdir(mode=0o700)
        configuration=run/'config.json';configuration.write_text(config.model_dump_json());configuration.chmod(0o600)
        health=run/'health.json'
        env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','HOME')}
        env.update(PYTHONPATH=str(ROOT/'backend'),CAMERA_LEASE_DIRECTORY=str(run/'leases'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        args=[sys.executable,'-m','app.vision.fleet','--config',str(configuration),'--model',str(model),'--cpu-slots',str(count),'--memory-mib',str(count*512),'--camera-memory-mib','512','--duration',str(a.duration),'--health-file',str(health),'--dashboard-directory',str(dashboard)]
        snapshots={};peak=0;started=time.monotonic()
        with (run/'worker.log').open('wb') as log:
            process=subprocess.Popen(args,env=env,stdout=log,stderr=log)
            try:
                while process.poll() is None:
                    if time.monotonic()-started>a.duration+30:raise RuntimeError('owned fleet deadline')
                    try:
                        row=json.loads(health.read_text());peak=max(peak,sum(c.get('resources',{}).get('rss_bytes',0) for c in row.get('cameras',[])))
                    except (OSError,ValueError):pass
                    for path in dashboard.glob('*.json'):
                        try:
                            sample=json.loads(path.read_text())
                            if sample.get('healthy') and sample.get('inference_frames',0)>0:
                                snapshots[sample['camera_id']]={k:sample[k] for k in ('inference_fps','inference_frames','capture_fps','inference_dropped')}
                        except (OSError,ValueError):pass
                    time.sleep(.15)
                code=process.wait()
                results.append({'cameras':count,'status':'MEASURED' if code==0 and len(snapshots)==count else 'FAILED','exit_code':code,'peak_group_rss_mib':peak/1024**2,'per_camera':snapshots,'target_fps':2,'meets_fps_target':len(snapshots)==count and all(s['inference_fps']>=2 for s in snapshots.values())})
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=25)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    report={'scope':'current cloud host; synthetic frames; isolated camera groups with one CPU slot each; not target-hardware soak or natural accuracy','configured_inference_fps':3,'pose_enabled':False,'production_accessed':False,'results':results}
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':'MEASURED','output':str(output/'result.json')}))
    return 1 if any(r['status']=='FAILED' for r in results) else 0

if __name__=='__main__':raise SystemExit(main())
