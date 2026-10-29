"""Smoke the actual locally built image; no mounts, real cameras or production secrets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',required=True);p.add_argument('--output',required=True);p.add_argument('--model');a=p.parse_args()
    if a.model:
        model=Path(a.model)
        if model.stat().st_size!=35858002 or hashlib.sha256(model.read_bytes()).hexdigest()!='c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063':
            p.error('only the reviewed YOLOX_s artifact is accepted')
    name='camera-release-'+uuid4().hex[:10];directory=Path(a.output);directory.mkdir(parents=True,mode=0o700,exist_ok=True)
    def docker(*args,**kwargs):
        kwargs.setdefault('timeout',45)
        return subprocess.run(['docker',*args],capture_output=True,check=True,**kwargs)
    try:
        docker('run','-d','--name',name,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--network','none','--memory','768m','--cpus','1','--pids-limit','96','--tmpfs','/tmp:size=128m,mode=1777',
               '-e','CAMERA_LEASE_DIRECTORY=/tmp/leases','-e','OMP_NUM_THREADS=1','-e','OPENBLAS_NUM_THREADS=1',a.image,'python','-c','import time;time.sleep(120)')
        info=json.loads(docker('inspect',name).stdout)[0]
        assert info['Config']['User']=='65534:65534' and info['HostConfig']['ReadonlyRootfs'] and info['HostConfig']['NetworkMode']=='none'
        docker('exec','-d',name,'uvicorn','app.main:app','--host','127.0.0.1','--port','8000')
        docker('exec',name,'python','-c',"import time,json;from urllib.request import urlopen;from urllib.error import HTTPError,URLError\nfor _ in range(80):\n try:\n  r=urlopen('http://127.0.0.1:8000/health',timeout=1);assert r.status==200;break\n except (URLError,TimeoutError):time.sleep(.1)\nelse:raise RuntimeError('API startup deadline')\nfor path,expected in [('/events',(401,403)),('/health/db',(503,))]:\n try:urlopen('http://127.0.0.1:8000'+path,timeout=2)\n except HTTPError as e:assert e.code in expected\n else:raise AssertionError('unexpected unauthenticated/DB access')")
        docker('exec',name,'python','-c',"import os,signal,time;from pathlib import Path\ndef api_pids():\n matches=[]\n for p in Path('/proc').glob('[0-9]*/cmdline'):\n  try:\n   if b'app.main:app' in p.read_bytes().split(b'\\0'):matches.append(int(p.parent.name))\n  except OSError:pass\n return matches\npids=api_pids();assert len(pids)==1;os.kill(pids[0],signal.SIGTERM)\nfor _ in range(80):\n if not api_pids():break\n time.sleep(.1)\nelse:raise RuntimeError('API SIGTERM deadline')")
        args=['--config','/config/vision.json']
        if a.model:
            docker('exec','-i',name,'sh','-c','cat > /tmp/model.onnx',input=Path(a.model).read_bytes())
            args=['--config','/config/detection.json','--model','/tmp/model.onnx']
        execution=docker('exec',name,'python','-m','app.vision',*args,'--duration','8','--health-file','/tmp/health.json')
        (directory/'worker.log').write_bytes(execution.stdout+execution.stderr)
        rows=[json.loads(line) for line in execution.stdout.decode().splitlines() if line.startswith('{')]
        healthy=[r for r in rows if r.get('healthy')]
        assert healthy and rows[-1]['cameras'][0]['state']=='stopped'
        if a.model:assert any(c.get('inference',{}).get('processed_frames',0)>0 for r in healthy for c in r['cameras'])
        docker('exec','-d',name,'python','-m','app.vision','--config','/config/vision.json','--health-file','/tmp/signal-health.json')
        for _ in range(50):
            check=subprocess.run(['docker','exec',name,'cat','/tmp/signal-health.json'],capture_output=True)
            try:
                if json.loads(check.stdout).get('healthy'):break
            except ValueError:pass
            time.sleep(.1)
        else:raise AssertionError('signal-test worker never healthy')
        docker('exec',name,'python','-c',"import os,signal;from pathlib import Path; matches=[]\nfor p in Path('/proc').glob('[0-9]*/cmdline'):\n try:\n  a=p.read_bytes().split(b'\\0')\n  if b'app.vision' in a:matches.append(int(p.parent.name))\n except OSError:pass\nassert len(matches)==1\nos.kill(matches[0],signal.SIGTERM)")
        for _ in range(80):
            state=json.loads(docker('exec',name,'cat','/tmp/signal-health.json').stdout)
            if state['cameras'][0]['state']=='stopped':break
            time.sleep(.1)
        else:raise AssertionError('SIGTERM deadline')
        result={'result':'PASS','image_id':info['Image'],'uid':info['Config']['User'],'network':'none','read_only':True,
                'api_health':True,'real_uvicorn_startup_and_sigterm':True,'unconfigured_db_denied':True,'anonymous_events_denied':True,'native_inference':bool(a.model),'sigterm_stopped':True,'healthy_snapshots':len(healthy),
                'last_counts':rows[-1]['cameras'][0]['counts'],'scope':'generated synthetic input only; not model accuracy or managed integration'}
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:subprocess.run(['docker','rm','-f',name],capture_output=True)

if __name__=='__main__':main()
