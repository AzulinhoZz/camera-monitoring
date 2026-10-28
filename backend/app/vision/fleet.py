"""Host-local admission and one killable process group per camera. No public API."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from .config import WorkerConfig


def group_resources(group):
    rss=cpu=processes=0
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields=path.read_text().rsplit(')',1)[1].split()
            if int(fields[2])!=group:continue
            processes+=1
            cpu+=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
            rss+=max(0,int(fields[21]))*os.sysconf('SC_PAGE_SIZE')
        except (OSError,ValueError,IndexError):continue
    return {'rss_bytes':rss,'cpu_seconds':cpu,'processes':processes}


def stop_group(process):
    # The group ID is an owned child's PID, never an externally supplied identifier.
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:pass
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait(timeout=2)


def stop_groups(processes, grace=15):
    deadline=time.monotonic()+grace
    for child in processes:
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    for child in processes:
        try:child.wait(timeout=max(.01,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:pass
    for child in processes:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=2)


def admit(config,memory_mib,camera_memory_mib,cpu_slots):
    from .pose_process import validate_pose_budget
    if not hasattr(os,'sched_getaffinity') or cpu_slots>len(os.sched_getaffinity(0)):
        raise ValueError('CPU affinity unavailable or insufficient')
    if len(config.cameras)>cpu_slots or len(config.cameras)*camera_memory_mib>memory_mib:
        raise ValueError('fleet admission budget exceeded')
    if any(validate_pose_budget([c],camera_memory_mib*1024*1024)>camera_memory_mib*1024*1024 for c in config.cameras):
        raise ValueError('per-camera memory budget too small')
    try:
        cap=Path('/sys/fs/cgroup/memory.max').read_text().strip()
        if cap!='max' and memory_mib*1024*1024>int(cap):raise ValueError('fleet budget exceeds cgroup memory')
    except OSError:pass
    try:
        quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota!='max' and cpu_slots>int(quota)/int(period):
            raise ValueError('fleet slots exceed cgroup CPU quota')
    except OSError:pass
    return True


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True)
    p.add_argument('--model');p.add_argument('--pose-runtime-python')
    p.add_argument('--dashboard-directory');p.add_argument('--resolve-scopes',action='store_true')
    p.add_argument('--persist-events',action='store_true')
    p.add_argument('--memory-mib',type=int,default=2048)
    p.add_argument('--camera-memory-mib',type=int,default=512)
    p.add_argument('--cpu-slots',type=int,default=2)
    p.add_argument('--duration',type=float,default=0)
    p.add_argument('--health-file',default='/tmp/vision-fleet-health.json')
    args=p.parse_args(argv)
    try:
        if not 128<=args.camera_memory_mib<=8192 or not 128<=args.memory_mib<=32768 or not 1<=args.cpu_slots<=4 or not 0<=args.duration<=86400:
            raise ValueError('invalid limits')
        config=WorkerConfig.load(args.config)
        admit(config,args.memory_mib,args.camera_memory_mib,args.cpu_slots)
        if args.model:args.model=str(Path(args.model).resolve(strict=True))
        if args.dashboard_directory:
            from .dashboard import directory
            directory(args.dashboard_directory)
    except Exception:
        print('Invalid fleet configuration or resource admission',file=sys.stderr);return 2
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
    counters=Counter(); rows=[];started=time.monotonic();failure=False
    with tempfile.TemporaryDirectory(prefix='vision-fleet-') as temporary:
        root=Path(temporary)
        available_cpus=sorted(os.sched_getaffinity(0))
        for index,camera in enumerate(config.cameras):
            # Operator files include excluded secrets, unlike serializable API contracts.
            data=camera.model_dump(mode='json');data['source']=camera.source
            if hasattr(camera,'inference_source'):data['inference_source']=camera.inference_source
            path=root/f'{camera.camera_id}.json'
            path.write_text(json.dumps({'cameras':[data],'metrics_interval_seconds':1}))
            path.chmod(0o600)
            health=root/f'{camera.camera_id}.health'
            command=[sys.executable,'-m','app.vision.fleet_child',str(os.getpid()),'--config',str(path),'--health-file',str(health)]
            for name in ('model','pose_runtime_python','dashboard_directory'):
                if getattr(args,name):command.extend(['--'+name.replace('_','-'),getattr(args,name)])
            for name in ('resolve_scopes','persist_events'):
                if getattr(args,name):command.append('--'+name.replace('_','-'))
            rows.append({'camera_id':str(camera.camera_id),'cpu':available_cpus[index],'command':command,'health':health,'process':None,'retries':0,'retry_at':0,'started':0,'prior_cpu':0,'prior_time':0,'ever_healthy':False})
        statuses=[]
        try:
            while not stopping and (not args.duration or time.monotonic()-started<args.duration):
                now=time.monotonic();statuses=[]
                for row in rows:
                    child=row['process']
                    if child is None and now>=row['retry_at'] and row['retries']<=3:
                        env=os.environ|{'VISION_FLEET_CPU':str(row['cpu']),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','TF_NUM_INTRAOP_THREADS':'1','TF_NUM_INTEROP_THREADS':'1'}
                        row['health'].unlink(missing_ok=True)
                        child=subprocess.Popen(row['command'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,env=env)
                        row.update(process=child,started=now,prior_cpu=0,prior_time=now)
                        counters['starts']+=1
                    resources=group_resources(child.pid) if child else {'rss_bytes':0,'cpu_seconds':0,'processes':0}
                    fresh=False;healthy=False
                    try:
                        health=json.loads(row['health'].read_text())
                        fresh=time.time()-row['health'].stat().st_mtime<20 and row['health'].stat().st_mtime>=time.time()-(now-row['started'])-1
                        healthy=fresh and health.get('healthy') is True
                        row['ever_healthy']=row['ever_healthy'] or healthy
                    except (OSError,ValueError):pass
                    elapsed=now-row['prior_time']
                    cpu_rate=max(0,resources['cpu_seconds']-row['prior_cpu'])/elapsed if elapsed>.1 else 0
                    row.update(prior_cpu=resources['cpu_seconds'],prior_time=now)
                    reason=None
                    if child:
                        if child.poll() is not None:reason='exit'
                        elif resources['rss_bytes']>args.camera_memory_mib*1024*1024 or resources['processes']>32:reason='resource_limit'
                        elif now-row['started']>30 and not fresh:reason='watchdog'
                        elif now-row['started']>30 and cpu_rate>1.5:reason='cpu_limit'
                    if reason:
                        stop_group(child);row['process']=None;row['retries']+=1
                        if args.dashboard_directory:(Path(args.dashboard_directory)/f"{row['camera_id']}.json").unlink(missing_ok=True)
                        row['retry_at']=now+min(8,2**row['retries']);counters[reason]+=1
                        healthy=False
                        if row['retries']>3:failure=True
                    statuses.append({'camera_id':row['camera_id'],'healthy':healthy,'restarts':row['retries'],'resources':resources,'cpu_cores_observed':cpu_rate})
                payload={'healthy':all(r['healthy'] for r in statuses),'cameras':statuses,'counts':dict(counters)}
                from .__main__ import write_health
                write_health(args.health_file,payload)
                if failure:break
                time.sleep(.25)
        finally:
            stop_groups([row['process'] for row in rows if row['process']])
            for row in rows:
                if args.dashboard_directory:(Path(args.dashboard_directory)/f"{row['camera_id']}.json").unlink(missing_ok=True)
            from .__main__ import write_health
            write_health(args.health_file,{'healthy':False,'stopped':True,'counts':dict(counters),'cameras':statuses})
    return 1 if failure or not all(row['ever_healthy'] for row in rows) else 0

if __name__=='__main__':raise SystemExit(main())
