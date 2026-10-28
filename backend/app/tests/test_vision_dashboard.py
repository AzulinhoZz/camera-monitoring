import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
import os, subprocess, sys, time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from app.vision.contracts import CameraScope
from app.vision.dashboard import Snapshot, read_snapshot, write_snapshot, preview
from app.vision.worker import Frame

SCOPE=CameraScope(camera_id=uuid4(),owner_id=uuid4(),organization_id=uuid4())
NOW=datetime.now(timezone.utc)


def snapshot(**updates):
    data=dict(**SCOPE.model_dump(),session=uuid4(),published_at=NOW,frame_at=NOW,healthy=True,state='streaming',
        capture_fps=10,inference_frames=3,inference_dropped=0,rss_bytes=100,cpu_seconds=.2,model_version='fixture',image='aGVsbG8=',overlay_image='b3ZlcmxheQ==')
    data.update(updates)
    return Snapshot(**data)


def test_atomic_dashboard_ttl_scope_and_symlink(tmp_path):
    root=tmp_path/'private'
    write_snapshot(root,snapshot())
    assert read_snapshot(root,SCOPE,now=NOW).inference_frames==3
    for now in (NOW+timedelta(seconds=11),NOW-timedelta(seconds=1)):
        with pytest.raises(ValueError):read_snapshot(root,SCOPE,now=now)
    with pytest.raises(ValueError):read_snapshot(root,SCOPE.model_copy(update={'owner_id':uuid4()}),now=NOW)
    path=root/f'{SCOPE.camera_id}.json';path.unlink();path.symlink_to('/etc/passwd')
    with pytest.raises(OSError):read_snapshot(root,SCOPE,now=NOW)
    root.chmod(0o755)
    with pytest.raises(ValueError):read_snapshot(root,SCOPE,now=NOW)


def test_dashboard_api_authorization_transfer_expiry_and_private_response(monkeypatch,tmp_path):
    from app import vision_api as api
    root=tmp_path/'private';write_snapshot(root,snapshot(published_at=datetime.now(timezone.utc),frame_at=datetime.now(timezone.utc)))
    monkeypatch.setenv('VISION_DASHBOARD_DIRECTORY',str(root))
    monkeypatch.setattr(api,'get_client',lambda:object())
    monkeypatch.setattr(api,'camera_scope',lambda *args:SCOPE)
    monkeypatch.setattr(api,'has_camera_access',lambda *args:True)
    app.dependency_overrides[get_current_user]=lambda:{'id':str(SCOPE.owner_id)}
    http=TestClient(app);url=f'/cameras/{SCOPE.camera_id}/vision-status'
    response=http.get(url)
    assert response.status_code==200 and response.json()['image_base64'] is None
    assert response.headers['cache-control']=='no-store, private'
    assert 'owner_id' not in response.text and 'organization_id' not in response.text
    assert http.get(url,params={'preview':True,'overlay':True}).json()['image_base64']=='b3ZlcmxheQ=='
    write_snapshot(root,snapshot(published_at=datetime.now(timezone.utc),frame_at=NOW-timedelta(seconds=20)))
    assert http.get(url,params={'preview':True}).json()['image_base64'] is None
    monkeypatch.setattr(api,'camera_scope',lambda *args:SCOPE.model_copy(update={'organization_id':uuid4()}))
    assert http.get(url).json()['state']=='unavailable'
    monkeypatch.setattr(api,'has_camera_access',lambda *args:False)
    assert http.get(url).status_code==403


def test_overlay_uses_exact_frame_and_keeps_original_unchanged():
    pixels=np.zeros((100,200,3),np.uint8)
    session=str(uuid4())
    frame=Frame(SCOPE,session,1,NOW,time.monotonic(),0,pixels)
    event={'schema_version':'1.0',**SCOPE.model_dump(mode='json'),'event_id':str(uuid4()),'timestamp':NOW.isoformat(),
        'model_version':'fixture','class':'person','confidence':.9,'bbox':{'x_min':.2,'y_min':.2,'x_max':.8,'y_max':.8},'worker_session_id':session,'track_id':1}
    plain,painted=preview(frame,[event])
    a=cv2.imdecode(np.frombuffer(base64.b64decode(plain),np.uint8),1)
    b=cv2.imdecode(np.frombuffer(base64.b64decode(painted),np.uint8),1)
    assert a.shape==b.shape==(100,200,3) and b.sum()>a.sum() and pixels.sum()==0
    event['timestamp']=(NOW+timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError):preview(frame,[event])


def test_fleet_admission_and_owned_group_cleanup():
    from app.vision.config import WorkerConfig,CameraConfig
    from app.vision.fleet import admit,group_resources,stop_group
    config=WorkerConfig(cameras=tuple(CameraConfig(camera_id=uuid4(),owner_id=SCOPE.owner_id) for _ in range(2)))
    with pytest.raises(ValueError):admit(config,1024,512,1)
    with pytest.raises(ValueError):admit(config,512,512,2)
    assert admit(config,1024,512,2)
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
    try:
        assert group_resources(child.pid)['processes']>=1
        stop_group(child)
        assert child.poll() is not None
    finally:
        if child.poll() is None:child.kill();child.wait()


def test_substream_requires_current_server_registry_binding(monkeypatch,tmp_path):
    import json
    from app.vision.config import CameraConfig,WorkerConfig
    from app.vision.registry import authorize_scopes
    camera=CameraConfig(**SCOPE.model_dump(),source_kind='rtsp',source='rtsp://127.0.0.1/original',inference_source='rtsp://127.0.0.1/sub')
    db=MagicMock();db.table.return_value.select.return_value.eq.return_value.execute.return_value.data=[{
        'id':str(SCOPE.camera_id),'user_id':str(SCOPE.owner_id),'organization_id':str(SCOPE.organization_id),'rtsp_url':camera.source}]
    path=tmp_path/'registry';monkeypatch.setenv('VISION_SUBSTREAM_REGISTRY',str(path))
    entry={'owner_id':str(SCOPE.owner_id),'organization_id':str(SCOPE.organization_id),'original':camera.source,'inference':camera.inference_source}
    path.write_text(json.dumps({str(SCOPE.camera_id):entry}))
    assert authorize_scopes(WorkerConfig(cameras=(camera,)),db).cameras[0].inference_source==camera.inference_source
    entry['owner_id']=str(uuid4());path.write_text(json.dumps({str(SCOPE.camera_id):entry}))
    with pytest.raises(ValueError):authorize_scopes(WorkerConfig(cameras=(camera,)),db)
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data[0]['rtsp_url']=camera.inference_source
    with pytest.raises(ValueError):authorize_scopes(WorkerConfig(cameras=(camera,)),db)


def test_original_evidence_alignment_fails_closed_without_media():
    from app.vision.evidence import EvidenceCollector
    dispatcher=MagicMock();dispatcher.submit.return_value=True
    collector=EvidenceCollector(SCOPE,dispatcher,separate_recording=True)
    session=str(uuid4());stamp=time.monotonic()
    infer=Frame(SCOPE,session,1,NOW,stamp,0,np.full((30,40,3),255,np.uint8))
    event={'schema_version':'1.0',**SCOPE.model_dump(mode='json'),'event_id':str(uuid4()),'rule_id':str(uuid4()),
        'worker_session_id':session,'track_id':1,'timestamp':NOW.isoformat(),'event_type':'intrusion','count':1,'review_status':'pending','description':'fixture'}
    assert collector.offer(event,1,infer)
    assert dispatcher.submit.call_args.args[0]['snapshot'] is None
    recording=Frame(SCOPE,str(uuid4()),1,NOW,stamp,0,np.full((30,40,3),20,np.uint8))
    collector.append(recording);collector.offer(event,1,infer)
    assert collector.pending['snapshot'].mean()==20 and collector.pending['session']==recording.session_id
    collector.close()
