"""One bounded synchronous pose request/camera; native work is killable externally."""
import mmap
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import threading
from collections import Counter,deque

import numpy as np

from .landmarks import LandmarkFrame
from .pose_backend import MAX_BYTES,MODEL_VERSION,receive,send


def validate_pose_budget(cameras,limit=None):
    """Fail early on a known inadequate cgroup cap; this is not a capacity proof."""
    count=sum(c.pose_enabled for c in cameras)
    required=(768*count+256*any(c.vision_enabled for c in cameras))*1024*1024
    if limit is None:
        try:
            raw=Path('/sys/fs/cgroup/memory.max').read_text().strip()
            limit=int(raw) if raw!='max' else None
        except (OSError,ValueError):limit=None
    if count and limit is not None and limit<required:
        raise ValueError('pose runtime exceeds declared memory budget')
    return required


class PoseProcess:
    def __init__(self,scope,python,*,timeout=5,startup_timeout=20):
        path=Path(python)
        if not path.is_absolute() or not path.is_file() or not os.access(path,os.X_OK):
            raise ValueError('pose Python must be an explicit server executable')
        if not .1<=timeout<=30 or not 1<=startup_timeout<=60:raise ValueError('invalid timeout')
        self.scope=scope;self.python=str(path);self.timeout=timeout;self.startup_timeout=startup_timeout
        self._lock=threading.Lock()
        self.process=None;self.sock=None;self.shared=None;self.file=None;self.directory=None
        self.retry_at=0;self.metrics=Counter();self.latencies=deque(maxlen=128)

    def _start(self):
        self.directory=tempfile.TemporaryDirectory(prefix='camera-pose-')
        self.file=tempfile.TemporaryFile(dir=self.directory.name)
        self.file.truncate(MAX_BYTES)
        self.shared=mmap.mmap(self.file.fileno(),MAX_BYTES)
        parent,child=socket.socketpair()
        self.sock=parent;parent.settimeout(self.startup_timeout)
        root=str(Path(__file__).resolve().parents[2])
        # Minimal child environment: no Supabase/RTSP keys are inherited.
        env={'PATH':'/usr/local/bin:/usr/bin:/bin','PYTHONPATH':root,'PYTHONUNBUFFERED':'1',
             'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','TF_NUM_INTRAOP_THREADS':'1','TF_NUM_INTEROP_THREADS':'1',
             'MPLCONFIGDIR':self.directory.name,'XDG_CACHE_HOME':self.directory.name}
        try:
            self.process=subprocess.Popen([self.python,'-m','app.vision.pose_backend',str(child.fileno()),str(self.file.fileno()),str(os.getpid())],pass_fds=(child.fileno(),self.file.fileno()),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
        finally:child.close()
        send(parent,{'scope':self.scope.model_dump(mode='json')})
        ready=receive(parent)
        if ready!={'ready':True,'model_version':MODEL_VERSION}:raise ValueError('unapproved runtime handshake')
        parent.settimeout(self.timeout)
        self.metrics['starts']+=1

    def infer(self,frame):
        if frame.scope!=self.scope:raise ValueError('pose frame tenant mismatch')
        if not self._lock.acquire(blocking=False):
            self.metrics['busy_skipped']+=1
            return None
        try:return self._infer(frame)
        finally:self._lock.release()

    def _infer(self,frame):
        if frame.scope!=self.scope:raise ValueError('pose frame tenant mismatch')
        pixels=frame.pixels
        if not isinstance(pixels,np.ndarray) or pixels.dtype!=np.uint8 or pixels.ndim!=3 or pixels.shape[2]!=3 or not 1<=pixels.shape[0]<=720 or not 1<=pixels.shape[1]<=1280:
            raise ValueError('invalid pose frame')
        if time.monotonic()<self.retry_at:
            self.metrics['backoff_skipped']+=1
            return None
        start=time.perf_counter()
        try:
            if self.process is None:self._start()
            if self.process.poll() is not None:raise ValueError('pose child stopped')
            raw=np.ascontiguousarray(pixels).tobytes()
            self.shared[:len(raw)]=raw
            send(self.sock,{'session':frame.session_id,'sequence':frame.sequence,'timestamp':frame.timestamp.isoformat(),
                            'width':pixels.shape[1],'height':pixels.shape[0]})
            response=receive(self.sock)
            if 'packet' not in response:raise ValueError('pose child failure')
            packet=LandmarkFrame.model_validate(response['packet']).require_scope(self.scope)
            if (str(packet.worker_session_id)!=frame.session_id or packet.frame_sequence!=frame.sequence or packet.timestamp!=frame.timestamp or packet.model_version!=MODEL_VERSION):
                raise ValueError('pose response mismatch')
            self.metrics['frames']+=1;self.latencies.append((time.perf_counter()-start)*1000)
            return packet
        except Exception:
            self.metrics['failed']+=1
            self.close()
            self.retry_at=time.monotonic()+1
            return None

    def snapshot(self):
        from .worker import process_resources
        values=sorted(self.latencies)
        return {'model_version':MODEL_VERSION,'counts':dict(self.metrics),
                'latency_ms':{'samples':len(values),'p50':values[(len(values)-1)//2] if values else None,'p95':values[int((len(values)-1)*.95)] if values else None},
                'resources':process_resources(self.process.pid) if self.process and self.process.poll() is None else None}

    def close(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=1)
            self.process=None
        if self.sock:self.sock.close();self.sock=None
        if self.shared:self.shared.close();self.shared=None
        if self.file:self.file.close();self.file=None
        if self.directory:self.directory.cleanup();self.directory=None
