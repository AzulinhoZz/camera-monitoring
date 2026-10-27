import base64
import os
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient

from app import auth, permissions
from app.main import app
from app.streaming import issue_stream, verify_stream
from app.capture_lease import CaptureLease
from app.vision.worker import CameraWorker
from app.vision.config import CameraConfig, WorkerConfig
from app.vision.registry import authorize_scopes
from app.tests.test_api_phase1_regressions import Database, user


@pytest.fixture
def gateway(monkeypatch):
    database = Database()
    monkeypatch.setattr(auth, "create_client", lambda *a, **k: database)
    monkeypatch.setattr(auth, "get_user_profile", lambda identity, email: user(identity))
    monkeypatch.setattr(permissions, "get_supabase_client", lambda: database)
    headers = {"Authorization": "Basic " + base64.b64encode(("gateway:" + os.environ["MEDIAMTX_GATEWAY_SECRET"]).encode()).decode()}
    return TestClient(app), database, headers


def test_gateway_rejects_spoofed_ip_publishing_and_missing_callback_auth(gateway):
    client, _, headers = gateway
    payload = dict(path="cam_cam-a", ip="127.0.0.1", action="publish", protocol="rtsp")
    assert client.post("/auth/mediamtx", json=payload).status_code == 401
    assert client.post("/auth/mediamtx", json=payload, headers=headers).status_code == 403
    payload.update(user="publisher", password=os.environ["MEDIAMTX_PUBLISH_SECRET"])
    assert client.post("/auth/mediamtx", json=payload, headers=headers).status_code == 200
    payload["path"] = "cam_missing"
    assert client.post("/auth/mediamtx", json=payload, headers=headers).status_code == 403


def test_stream_scoped_token_expiry_and_revocation(gateway):
    client, database, headers = gateway
    camera = database.rows["cameras"][0]
    response = issue_stream("reader", camera)
    assert "token=" not in response["hls_url"]
    payload = dict(path="cam_cam-a", action="read", protocol="hls", token=response["stream_token"])
    assert client.post("/auth/mediamtx", json=payload, headers=headers).status_code == 200
    assert client.post("/auth/mediamtx", json=payload | {"path": "cam_other"}, headers=headers).status_code == 403
    database.rows["camera_access_grants"].clear()
    assert client.post("/auth/mediamtx", json=payload, headers=headers).status_code == 403
    expired = jwt.encode(dict(sub="owner", camera_id="cam-a", owner_id="owner", organization_id="org-a",
                              path="cam_cam-a", aud="camera-stream", iss="camera-monitoring", iat=int(time.time())-100,
                              exp=int(time.time())-1), os.environ["STREAM_TOKEN_SECRET"], algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_stream(expired, "cam_cam-a")
    camera["organization_id"] = None
    personal = issue_stream("owner", camera)
    assert verify_stream(personal["stream_token"], "cam_cam-a")["organization_id"] is None


def test_stale_grants_no_longer_authorize_other_organizations(gateway):
    _, database, _ = gateway
    assert permissions.has_camera_access(user("reader"), "cam-a")
    assert not permissions.has_camera_access(user("reader", org="org-b"), "cam-a")
    assert permissions.get_authorized_camera_ids(user("reader", org="org-b")) == []


def test_capture_lease_blocks_duplicate_owner_and_survives_file_persistence():
    first = CaptureLease("camera/a").acquire()
    try:
        with pytest.raises(RuntimeError): CaptureLease("camera/a").acquire()
        second = CaptureLease("camera/b").acquire()
        second.release()
    finally:
        first.release()
    third = CaptureLease("camera/a").acquire()
    third.release()


def test_legacy_and_vision_share_capture_ownership(monkeypatch):
    from app.motion_detector import MotionDetectorWorker
    from conftest import ClosedCapture
    monkeypatch.setattr("cv2.VideoCapture", ClosedCapture)
    monkeypatch.setattr("app.motion_detector.policy_rtsp_url", lambda value: value)
    camera_id = "00000000-0000-0000-0000-000000000001"
    worker = MotionDetectorWorker(camera_id, "rtsp://fixture.invalid/live")
    vision = CameraWorker(CameraConfig(camera_id=camera_id, owner_id="00000000-0000-0000-0000-000000000002"))
    worker.start()
    try:
        with pytest.raises(RuntimeError): vision.start()
    finally:
        worker.stop()
        worker.join(5)
    vision.start()
    try:
        duplicate = MotionDetectorWorker(camera_id, "rtsp://fixture.invalid/live")
        with pytest.raises(RuntimeError): duplicate.start()
    finally:
        vision.stop()


def test_registry_derives_source_and_rejects_scope_changes():
    from uuid import UUID
    camera_id="00000000-0000-0000-0000-000000000001"
    owner_id="00000000-0000-0000-0000-000000000002"
    config = WorkerConfig(cameras=(CameraConfig(camera_id=camera_id, owner_id=owner_id, source_kind="rtsp", source="rtsp://untrusted.invalid/live"),))
    database=Database()
    database.rows["cameras"]=[dict(id=camera_id,user_id=owner_id,organization_id=None,rtsp_url="rtsp://10.42.0.2/live")]
    verified = authorize_scopes(config, database)
    assert verified.cameras[0].source == "rtsp://10.42.0.2/live"
    database.rows["cameras"][0]["organization_id"]="00000000-0000-0000-0000-000000000003"
    with pytest.raises(ValueError, match="scope changed"): authorize_scopes(config,database)


def test_hls_proxy_authenticates_segments_before_fetch_and_uses_only_internal_secret(gateway, monkeypatch):
    import httpx
    from app import stream_proxy
    client,database,_=gateway
    token=issue_stream('owner',database.rows['cameras'][0])['stream_token']
    original=httpx.Client
    requested=[]
    def transport(request):
        requested.append(request.url.path)
        assert request.headers['Authorization']=='Bearer '+os.environ['MEDIAMTX_HLS_SECRET']
        assert token not in str(request.url)
        return httpx.Response(200,content=b'synthetic-segment')
    monkeypatch.setattr(stream_proxy.httpx,'Client',lambda **kwargs: original(transport=httpx.MockTransport(transport)))
    path='/streams/cam-a/segment0.ts'
    assert client.get(path).status_code==401
    assert requested==[]
    response=client.get(path,headers={'Authorization':'Bearer '+token})
    assert response.status_code==200 and response.content==b'synthetic-segment'
    assert response.headers['Cache-Control']=='private, no-store'
    assert requested==['/cam_cam-a/segment0.ts']
    database.rows['cameras'][0]['user_id']='changed-owner'
    assert client.get(path,headers={'Authorization':'Bearer '+token}).status_code==403
    assert len(requested)==1


def test_hls_proxy_refuses_redirects_and_remote_playlist_targets(gateway,monkeypatch):
    import httpx
    from app import stream_proxy
    client,database,_=gateway
    token=issue_stream('owner',database.rows['cameras'][0])['stream_token']
    original=httpx.Client
    count=[]
    response=httpx.Response(302,headers={'Location':'https://forbidden.invalid/stream'})
    def transport(request): count.append(1); return response
    monkeypatch.setattr(stream_proxy.httpx,'Client',lambda **kwargs: original(transport=httpx.MockTransport(transport)))
    url='/streams/cam-a/index.m3u8'
    assert client.get(url,headers={'Authorization':'Bearer '+token}).status_code==502
    assert len(count)==1
    response=httpx.Response(200,content=b'#EXTM3U\nhttps://forbidden.invalid/segment.ts\n')
    assert client.get(url,headers={'Authorization':'Bearer '+token}).status_code==502
    assert len(count)==2


def test_manager_lease_conflict_does_not_keep_unstarted_thread():
    from app.motion_detector import motion_manager
    camera_id='blocked-manager-camera'
    lease=CaptureLease(camera_id).acquire()
    try:
        with pytest.raises(RuntimeError):
            motion_manager.start_detector(camera_id,'rtsp://fixture.invalid/live')
        assert camera_id not in motion_manager.workers
        motion_manager.stop_all()  # Must not join a thread that never started.
    finally:
        lease.release()


def test_supervisor_sigkill_terminates_decoder_and_releases_lease():
    import subprocess
    import sys
    import select
    from pathlib import Path
    camera_id='00000000-0000-0000-0000-000000000009'
    code=f'''
import time
from app.vision.worker import CameraWorker
from app.vision.config import CameraConfig
worker=CameraWorker(CameraConfig(camera_id="{camera_id}",owner_id="00000000-0000-0000-0000-000000000002"))
worker.start()
deadline=time.monotonic()+8
while time.monotonic()<deadline:
 if worker.metrics()["healthy"]:
  print(worker.decoder_pid,flush=True)
  break
 time.sleep(.02)
else:raise RuntimeError("fixture capture failed")
time.sleep(60)
'''
    parent=subprocess.Popen([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[2],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert select.select([parent.stdout],[],[],10)[0], 'supervisor fixture timed out'
        pid=int(parent.stdout.readline().strip())
        parent.kill();parent.wait(5)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            file=Path(f'/proc/{pid}/stat')
            if not file.exists() or file.read_text().rsplit(')',1)[1].split()[0]=='Z':break
            time.sleep(.02)
        else:pytest.fail('decoder survived supervisor SIGKILL')
        lease=CaptureLease(camera_id).acquire();lease.release()
    finally:
        if parent.poll() is None:parent.kill();parent.wait(5)


def test_legacy_camera_response_removes_rtsp_credentials_and_query():
    from app.cameras import _format_camera
    response=_format_camera(dict(id='cam-a',name='Synthetic',rtsp_url='rtsp://private-user:private-password@10.42.0.2:8554/live?token=private-token'))
    assert response['rtsp_url']=='rtsp://10.42.0.2:8554/live'
    assert all(value not in str(response) for value in ('private-user','private-password','private-token'))
