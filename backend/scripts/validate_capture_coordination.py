"""Docker proof: root legacy API and non-root worker share a kill-safe lease."""
import argparse
import subprocess
import time
from uuid import uuid4

CAMERA='00000000-0000-0000-0000-000000000001'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',default='camera-monitoring-vision-worker:dev')
    args=parser.parse_args()
    name='capture-proof-'+uuid4().hex[:12]
    volume=name+'-volume'
    created=running=False
    def command(*parts):
        return subprocess.run(list(parts),check=True,capture_output=True,text=True).stdout.strip()
    def root_capture(code):
        return command('docker','run','--rm','--network','none','--mount',f'type=volume,src={volume},dst=/run/camera-leases',
                       '-e','CAMERA_LEASE_DIRECTORY=/run/camera-leases',args.image,'python','-c',code)
    try:
        command('docker','volume','create',volume);created=True
        setup=f'from app.capture_lease import CaptureLease; lease=CaptureLease("{CAMERA}").acquire(); lease.release()'
        root_capture(setup)  # Root owns the inode before the unprivileged worker opens it.
        command('docker','run','--rm','-d','--name',name,'--network','none','--read-only','--user','65534:65534',
                '--memory','512m','--cpus','1','--pids-limit','64','--tmpfs','/tmp:size=32m,mode=1777',
                '--mount',f'type=volume,src={volume},dst=/run/camera-leases','-e','CAMERA_LEASE_DIRECTORY=/run/camera-leases',
                args.image,'python','-m','app.vision','--config','/config/vision.json')
        running=True
        for _ in range(70):
            probe=subprocess.run(['docker','exec',name,'python','-c','import json; print(int(json.load(open("/tmp/vision-health.json"))["healthy"]))'],capture_output=True,text=True)
            if probe.returncode==0 and probe.stdout.strip()=='1':break
            time.sleep(.1)
        else:raise RuntimeError('non-root capture did not become healthy')
        blocked=f'''from app.capture_lease import CaptureLease
try:
 CaptureLease("{CAMERA}").acquire()
except RuntimeError:
 print("BLOCKED")
else:
 raise RuntimeError("duplicate camera capture allowed")
'''
        assert root_capture(blocked)=='BLOCKED'
        command('docker','stop','-t','10',name);running=False
        root_capture(setup)
        print('PASS: root-created lease readable by non-root; duplicate root capture blocked; shutdown releases ownership')
    finally:
        if running:command('docker','stop','-t','10',name)
        if created:command('docker','volume','rm',volume)


if __name__=='__main__':main()
