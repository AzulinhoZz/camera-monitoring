from datetime import datetime,timezone
from pathlib import Path
import sys,time
from uuid import uuid4

import numpy as np
import pytest

from app.vision.contracts import CameraScope
from app.vision.worker import Frame
from app.vision.pose_backend import receive,verify_models,MODEL_VERSION
from app.vision.pose_process import PoseProcess

SCOPE=CameraScope(camera_id=uuid4(),owner_id=uuid4())


def test_ipc_rejects_oversized_messages():
    class Socket:
        def recv(self,n):return b'x'*65537
    with pytest.raises(ValueError):receive(Socket())


def test_model_verification_fails_before_loading_native_code(monkeypatch,tmp_path):
    from app.vision import pose_backend as module
    versions={'mediapipe':'0.10.32','numpy':'2.5.4','opencv-contrib-python':'5.0.0.93','pydantic':'2.14.1'}
    monkeypatch.setattr(module.importlib.metadata,'version',lambda name:versions[name])
    class Distribution:
        def locate_file(self,name):return tmp_path
    monkeypatch.setattr(module.importlib.metadata,'distribution',lambda *args:Distribution())
    first=next(iter(module.MODELS))
    target=tmp_path/first;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='model'):verify_models(tmp_path)


def test_native_request_timeout_kills_only_owned_child(tmp_path):
    # A test executable emulates a native backend that stops answering after ready.
    executable=tmp_path/'fake-python'
    executable.write_text(f'''#!{sys.executable}
import socket,sys,time,json
s=socket.socket(fileno=int(sys.argv[3]))
s.recv(4096)
s.sendall((json.dumps({{'ready':True,'model_version':MODEL_VERSION}})+'\\n').encode())
s.recv(4096)
time.sleep(30)
''')
    executable.chmod(0o700)
    client=PoseProcess(SCOPE,str(executable),timeout=.1,startup_timeout=2)
    frame=Frame(SCOPE,str(uuid4()),1,datetime.now(timezone.utc),time.monotonic(),0.,np.zeros((32,32,3),np.uint8))
    started=time.monotonic()
    try:
        assert client.infer(frame) is None
        assert time.monotonic()-started<5 and client.process is None
        assert client.metrics['failed']==1
        assert client.infer(frame) is None and client.metrics['backoff_skipped']==1
        with pytest.raises(ValueError):client.infer(Frame(SCOPE.model_copy(update={'owner_id':uuid4()}),frame.session_id,2,frame.timestamp,0.,0.,frame.pixels))
    finally:client.close()


def test_pose_memory_budget_rejects_original_small_container():
    from app.vision.config import CameraConfig
    from app.vision.pose_process import validate_pose_budget
    camera=CameraConfig(**SCOPE.model_dump(),pose_enabled=True)
    with pytest.raises(ValueError):validate_pose_budget([camera],512*1024*1024)
    assert validate_pose_budget([camera],1024*1024*1024)==768*1024*1024
