"""Bounded pre/post evidence collector using the recording lane, never a new capture.

One pending clip/camera; one global I/O consumer; queue size four. Event insert
precedes upload, duplicate/cooldown suppression prevents uploads. Explicit drops
are metrics, not unbounded retry or a promise of exactly-once delivery.
"""
from collections import Counter, deque
from pathlib import Path
from queue import Queue, Full, Empty
from tempfile import TemporaryDirectory
from threading import Lock, Thread
import time

import cv2

from app.clip_recorder import FrameRingBuffer, encode_clip_frames
from .contracts import CameraScope
from .persistence import EventStore, RuleEvent


class EvidenceCollector:
    fps=5
    pre_frames=10  # two seconds at five FPS, maximum 320x180 per frame
    post_frames=15

    def __init__(self,scope,dispatcher):
        self.scope=scope
        self.dispatcher=dispatcher
        self.buffer=FrameRingBuffer(maxlen=self.pre_frames)
        self.sample_times=deque(maxlen=self.pre_frames)
        self.lock=Lock()
        self.pending=None
        self.last_sample=None
        self.session=None
        self.metrics=Counter()

    def offer(self,event,revision,frame):
        parsed=RuleEvent.model_validate(event)
        if CameraScope(**{k:getattr(parsed,k) for k in CameraScope.model_fields})!=self.scope or frame.scope!=self.scope or str(parsed.worker_session_id)!=frame.session_id:
            raise ValueError('evidence scope mismatch')
        with self.lock:
            if self.pending is not None:
                self.metrics['evidence_busy']+=1
                accepted=self.dispatcher.submit({'event':parsed.model_dump(mode='json'),'revision':revision,'snapshot':None,'frames':[]})
                if not accepted: self.metrics['queue_dropped']+=1
                return accepted
            # Snapshot comes from the exact inference frame, not a later frame.
            snapshot=cv2.resize(frame.pixels,(320,180))
            self.pending={'event':parsed.model_dump(mode='json'),'revision':revision,
                'snapshot':snapshot,'frames':[pixels for stamp,pixels in zip(self.sample_times,self.buffer.get_frames_copy()) if frame.captured_monotonic-2-1e-6<=stamp<=frame.captured_monotonic] if self.session==frame.session_id else [],
                'deadline':time.monotonic()+3,'post':0,'session':frame.session_id,
                'event_monotonic':frame.captured_monotonic}
            self.metrics['offered']+=1
            return True

    def append(self,frame):
        if frame.scope!=self.scope:
            raise ValueError('recording scope mismatch')
        with self.lock:
            if self.session!=frame.session_id:
                self.buffer.clear()
                self.sample_times.clear()
                self.last_sample=None
                self.session=frame.session_id
            if self.pending and self.pending['session']!=frame.session_id:
                self.metrics['session_dropped']+=1
                self.pending=None
            if self.pending and time.monotonic()>=self.pending['deadline']:
                self._flush()
            if self.last_sample is not None and frame.captured_monotonic-self.last_sample+1e-6<1/self.fps:
                return
            self.last_sample=frame.captured_monotonic
            pixels=cv2.resize(frame.pixels,(320,180))
            self.buffer.append(pixels)
            self.sample_times.append(frame.captured_monotonic)
            if self.pending and frame.captured_monotonic>self.pending['event_monotonic']:
                self.pending['frames'].append(pixels)
                self.pending['post']+=1
                if self.pending['post']>=self.post_frames:
                    self._flush()

    def tick(self):
        with self.lock:
            if self.pending and time.monotonic()>=self.pending['deadline']:
                self._flush()

    def _flush(self):
        job=self.pending
        self.pending=None
        job['frames']=job['frames'][:self.pre_frames+self.post_frames]
        if not self.dispatcher.submit(job):
            self.metrics['queue_dropped']+=1

    def close(self):
        with self.lock:
            if self.pending:
                self._flush()
            self.buffer.clear()


class EvidenceDispatcher:
    def __init__(self,client):
        self.store=EventStore(client)
        self.queue=Queue(maxsize=4)
        self.metrics=Counter()
        self.closing=False
        self.thread=Thread(target=self._run,name='vision-evidence-io',daemon=True)
        self.thread.start()

    def submit(self,job):
        if self.closing:
            return False
        try:
            self.queue.put_nowait(job)
            return True
        except Full:
            return False

    def _run(self):
        while True:
            try:
                job=self.queue.get(timeout=.1)
            except Empty:
                if self.closing: return
                continue
            try:
                self._save(job)
            except Exception:
                # Exceptions may contain credentials or signed URLs: metrics only.
                self.metrics['failed']+=1
            finally:
                self.queue.task_done()

    def _upload(self,event,kind,data):
        suffix,bucket,mime=('.jpg','motion-evidence','image/jpeg') if kind=='snapshot' else ('.mp4','motion-clips','video/mp4')
        path=f"{event['owner_id']}/{event['camera_id']}/{event['event_id']}{suffix}"
        storage=self.store.client.storage.from_(bucket)
        self.store.attach(event,kind,None)  # Scope check before bytes leave this process.
        storage.upload(path,data,file_options={'content-type':mime,'x-upsert':'false'})
        try:
            self.store.attach(event,kind,path)
        except Exception:
            # Clean only the new, unreferenced object; never overwrite/delete old media.
            storage.remove([path])
            raise

    def _save(self,job):
        event=job['event']
        if not self.store.insert(event,job['revision']):
            self.metrics['suppressed']+=1
            return
        self.metrics['persisted']+=1
        try:
            if job['snapshot'] is None:
                return
            ok,jpeg=cv2.imencode('.jpg',job['snapshot'],[int(cv2.IMWRITE_JPEG_QUALITY),80])
            if not ok: raise ValueError('snapshot encoding failed')
            self._upload(event,'snapshot',jpeg.tobytes())
            self.metrics['snapshots']+=1
        except Exception:
            self.metrics['snapshot_failed']+=1
        if job['frames']:
            try:
                with TemporaryDirectory(prefix='vision-clip-') as directory:
                    path=Path(directory)/'clip.mp4'
                    encode_clip_frames(job['frames'],path,EvidenceCollector.fps)
                    if path.stat().st_size>16*1024*1024:
                        raise ValueError('clip too large')
                    self._upload(event,'clip',path.read_bytes())
                self.metrics['clips']+=1
            except Exception:
                self.metrics['clip_failed']+=1

    def close(self,timeout=15):
        self.closing=True
        self.thread.join(timeout)
        if self.thread.is_alive():
            self.metrics["shutdown_pending"]=self.queue.unfinished_tasks
        return not self.thread.is_alive()
