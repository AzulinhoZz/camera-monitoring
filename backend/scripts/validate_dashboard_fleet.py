"""Real CPU capture/YOLOX/pose fleets + concurrent generated evidence, local I/O only.

Evidence events are explicitly injected fixtures, not neural positives. No remote
camera, Supabase, Storage or FCM is contacted. All model paths are explicit.
"""
import argparse
import base64
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID,uuid4

import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.vision.evidence import EvidenceDispatcher
from app.vision.dashboard import read_snapshot
from app.vision.contracts import CameraScope


class LocalIO:
    def __init__(self):self.uploads=0;self.bytes=0;self.storage=self
    def rpc(self,*args):return SimpleNamespace(execute=lambda:SimpleNamespace(data=True))
    def from_(self,bucket):return self
    def upload(self,path,data,file_options):self.uploads+=1;self.bytes+=len(data)
    def remove(self,*args):raise AssertionError('no failed attachment expected')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--pose-python',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
    results=[]
    for count in (1,2,4):
        directory=output/f'{count}-cameras';directory.mkdir(exist_ok=True)
        dashboard=directory/'dashboard';dashboard.mkdir(mode=0o700,exist_ok=True)
        scopes=[CameraScope(camera_id=UUID(int=i+1),owner_id=UUID(int=10)) for i in range(count)]
        cameras=[dict(**s.model_dump(mode='json'),source_kind='synthetic',capture_fps=12,recording_fps=5,inference_fps=3,
            max_width=320,max_height=180,vision_enabled=True,pose_enabled=True) for s in scopes]
        path=directory/'config.json';path.write_text(json.dumps({'cameras':cameras,'metrics_interval_seconds':1}))
        health=directory/'health.json'; health.unlink(missing_ok=True); local=LocalIO();evidence=EvidenceDispatcher(local)
        duration=30 if count==2 else 16
        command=[sys.executable,'-m','app.vision.fleet','--config',str(path),'--model',str(Path(a.model).resolve()),
            '--pose-runtime-python',a.pose_python,'--dashboard-directory',str(dashboard),'--cpu-slots',str(count),
            '--memory-mib',str(count*1024),'--camera-memory-mib','1024','--duration',str(duration),'--health-file',str(health)]
        env=os.environ|{'PYTHONPATH':str(Path(__file__).resolve().parents[1]),'CAMERA_LEASE_DIRECTORY':str(directory/'leases')}
        process=subprocess.Popen(command,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        fleet_started=time.monotonic()
        seen={};peaks={};snapshots={};killed=False;recovered=False;other_continued=False;last_evidence=0;preview_verified=False;queue_dropped=0
        try:
            while process.poll() is None:
                now=time.monotonic()
                try:
                    status=json.loads(health.read_text())
                    for row in status.get('cameras',[]):
                        key=row['camera_id'];peaks[key]=max(peaks.get(key,0),row['resources']['rss_bytes'])
                        if row['healthy'] and not status.get('stopped'):seen[key]=seen.get(key,0)+1
                        if killed and key==str(scopes[0].camera_id) and row['restarts']>0 and row['healthy']:recovered=True
                        if killed and key==str(scopes[-1].camera_id) and row['healthy']:other_continued=True
                except (OSError,ValueError,KeyError):pass
                if count==2 and now-fleet_started>5 and not killed and process.poll() is None:
                    children=[]
                    for proc in Path('/proc').glob('[0-9]*/stat'):
                        try:
                            fields=proc.read_text().rsplit(')',1)[1].split()
                            if int(fields[1])==process.pid:children.append(int(proc.parent.name))
                        except (OSError,ValueError,IndexError):pass
                    children.sort()
                    # First process created is the first camera; kill only this owned child.
                    assert len(children)>=2
                    os.kill(int(children[0]),signal.SIGKILL);killed=True
                for scope in scopes:
                    try:
                        snap=read_snapshot(dashboard,scope)
                        snapshots[str(scope.camera_id)]=snap.model_dump(mode='json',exclude={'image','overlay_image'})
                        if snap.healthy and snap.image and not preview_verified:
                            data=snap.overlay_image
                            assert data and cv2.imdecode(np.frombuffer(base64.b64decode(data),np.uint8),1) is not None
                            preview_verified=True
                    except (OSError,ValueError):pass
                if now-last_evidence>=2:
                    for scope in scopes:
                        pixels=np.full((180,320,3),70,np.uint8)
                        event={'schema_version':'1.0',**scope.model_dump(mode='json'),'event_id':str(uuid4()),'rule_id':str(uuid4()),
                            'worker_session_id':str(uuid4()),'track_id':1,'timestamp':datetime.now(timezone.utc).isoformat(),
                            'event_type':'intrusion','count':1,'review_status':'pending','description':'Injected geometric evidence fixture; not a model detection'}
                        if not evidence.submit({'event':event,'revision':1,'snapshot':pixels,'frames':[pixels]*25}):queue_dropped+=1
                    last_evidence=now
                time.sleep(.15)
            code=process.wait();error=process.stderr.read().decode()
            assert code==0,(code,error)
            assert len(seen)==count and all(s['inference_frames']>0 for s in snapshots.values()),seen
            assert preview_verified
            if count==2:assert killed and recovered and other_continued
            assert evidence.close(timeout=30) and not evidence.metrics['failed'] and not evidence.metrics['clip_failed'] and not evidence.metrics['snapshot_failed']
            assert local.uploads>=count*2
            assert not list(dashboard.glob('*.json')),'private previews removed at shutdown'
            results.append({'cameras':count,'duration_seconds':duration,'exit_code':code,'native_models':'YOLOX_s + MediaPipe Tasks pose/hands, CPU',
                'scope':'Synthetic capture and real negative inference; concurrent injected evidence with local RPC/Storage substitutes, not natural action accuracy or managed integration',
                'last_running_snapshots':snapshots,'peak_summed_group_rss_bytes':peaks,'evidence_counts':dict(evidence.metrics),'local_upload_bytes':local.bytes,'fixture_evidence_queue_dropped':queue_dropped,
                'scoped_preview_decoded':preview_verified,'one_child_killed':killed,'recovered':recovered,'other_camera_continued':other_continued})
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=25)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            evidence.close()
    (output/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({'result':'PASS','fleets':[r['cameras'] for r in results],'output':str(output/'result.json')}))

if __name__=='__main__':main()
