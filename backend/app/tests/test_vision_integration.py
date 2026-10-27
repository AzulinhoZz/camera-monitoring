"""Production bindings replaced with memory adapters; all imagery is generated."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import cv2
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user
from app.vision.contracts import CameraScope
from app.vision.evidence import EvidenceCollector, EvidenceDispatcher
from app.vision.persistence import EventStore, load_rules
from app.vision.rules import Rule
from app.vision.worker import Frame
from app.events import verify_vision_media_scope

SCOPE=CameraScope(camera_id=uuid4(),owner_id=uuid4(),organization_id=uuid4())
SESSION=uuid4()
NOW=datetime.now(timezone.utc)


def rule():
    return Rule(**SCOPE.model_dump(),rule_id=uuid4(),kind='intrusion',enabled=True,
                polygon=({'x':0,'y':0},{'x':1,'y':0},{'x':1,'y':1}))


def event():
    return {'schema_version':'1.0',**SCOPE.model_dump(mode='json'),'event_id':str(uuid4()),
            'rule_id':str(rule().rule_id),'worker_session_id':str(SESSION),'track_id':1,
            'timestamp':NOW.isoformat(),'event_type':'intrusion','direction':None,'count':1,
            'review_status':'pending','evidence':None,'description':'fixture'}


def frame(sequence=1,stamp=1.,session=SESSION,scope=SCOPE):
    return Frame(scope,str(session),sequence,NOW,stamp,stamp,np.full((120,160,3),80,np.uint8))


def api_setup(monkeypatch,manage=True):
    from app import vision_api as api
    client=MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data=[{
        'id':str(SCOPE.camera_id),'user_id':str(SCOPE.owner_id),'organization_id':str(SCOPE.organization_id)}]
    monkeypatch.setattr(api,'get_client',lambda:client)
    monkeypatch.setattr(api,'has_camera_access',lambda *args:True)
    monkeypatch.setattr(api,'can_manage_camera',lambda *args:manage)
    app.dependency_overrides[get_current_user]=lambda:{'id':str(SCOPE.owner_id)}
    return client,TestClient(app)


def test_rules_api_derives_scope_and_writes_actor(monkeypatch):
    db,http=api_setup(monkeypatch)
    r=rule().model_dump(mode='json')
    body={k:v for k,v in r.items() if k not in CameraScope.model_fields}
    db.rpc.return_value.execute.return_value.data=[{'revision':1,'rules':[r]}]
    response=http.put(f'/cameras/{SCOPE.camera_id}/vision-rules',json={'revision':0,'rules':[body]})
    assert response.status_code==200
    args=db.rpc.call_args.args
    assert args[0]=='save_vision_config'
    assert args[1]['p_actor_id']==str(SCOPE.owner_id)
    assert args[1]['p_rules'][0]['organization_id']==str(SCOPE.organization_id)
    assert http.put(f'/cameras/{SCOPE.camera_id}/vision-rules',json={'revision':0,'rules':[r]}).status_code==422


def test_rules_api_readonly_invalid_geometry_conflict_and_outage(monkeypatch):
    db,http=api_setup(monkeypatch,False)
    url=f'/cameras/{SCOPE.camera_id}/vision-rules'
    assert http.put(url,json={'revision':0,'rules':[]}).status_code==403
    db,http=api_setup(monkeypatch)
    r=rule().model_dump(mode='json'); body={k:v for k,v in r.items() if k not in CameraScope.model_fields}
    assert http.put(url,json={'revision':0,'rules':[{**body,'polygon':[]}]}).status_code==422
    assert http.put(url,json={'revision':0,'rules':[{**body,'timezone_name':'bad/timezone'}]}).status_code==422
    class Conflict(Exception): code='40001'
    db.rpc.return_value.execute.side_effect=Conflict('do not expose secret')
    response=http.put(url,json={'revision':0,'rules':[]})
    assert response.status_code==409 and 'secret' not in response.text
    db.rpc.return_value.execute.side_effect=RuntimeError('secret')
    response=http.put(url,json={'revision':0,'rules':[]})
    assert response.status_code==503 and 'secret' not in response.text


def test_registry_rejects_scope_change_and_missing_rules():
    client=MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data=[{
        'id':str(SCOPE.camera_id),'user_id':str(uuid4()),'organization_id':str(SCOPE.organization_id)}]
    with pytest.raises(ValueError):load_rules(client,SCOPE)


def test_recording_bounded_pre_post_scope_and_busy(monkeypatch):
    dispatcher=MagicMock();dispatcher.submit.return_value=True
    collector=EvidenceCollector(SCOPE,dispatcher)
    for i in range(20):collector.append(frame(i+1,i*.2))
    e=event();f=frame(21,4.)
    assert collector.offer(e,1,f)
    assert collector.offer(event(),1,f) # persist even when evidence slot busy
    assert dispatcher.submit.call_args.args[0]['snapshot'] is None
    for i in range(15):collector.append(frame(22+i,4.21+i*.21))
    job=dispatcher.submit.call_args.args[0]
    assert len(job['frames'])==25 and job['snapshot'].shape==(180,320,3)
    assert collector.pending is None
    with pytest.raises(ValueError):collector.append(frame(scope=SCOPE.model_copy(update={'owner_id':uuid4()})))
    collector.close()


def test_event_and_evidence_real_codec_and_duplicate_suppression(tmp_path):
    client=MagicMock();client.rpc.return_value.execute.return_value.data=True
    dispatcher=EvidenceDispatcher(client)
    e=event()
    pixels=np.full((180,320,3),160,np.uint8)
    job={'event':e,'revision':1,'snapshot':pixels,'frames':[pixels]*10}
    assert dispatcher.submit(job)
    assert dispatcher.close()
    assert dispatcher.metrics['persisted']==1
    assert dispatcher.metrics['snapshots']==1 and dispatcher.metrics['clips']==1
    assert client.rpc.call_args.args[0]=='attach_vision_media'
    buckets=[c.args[0] for c in client.storage.from_.call_args_list]
    assert 'motion-evidence' in buckets and 'motion-clips' in buckets
    client.rpc.return_value.execute.return_value.data=False
    second=EvidenceDispatcher(client);second.submit(job);assert second.close()
    assert second.metrics['suppressed']==1 and second.metrics['snapshots']==0


def test_media_attach_failure_removes_only_new_object():
    client=MagicMock()
    dispatcher=EvidenceDispatcher(client)
    dispatcher.store.attach=MagicMock(side_effect=[None,ValueError('denied')])
    e=event()
    with pytest.raises(ValueError):dispatcher._upload(e,'snapshot',b'fixture')
    expected=f"{e['owner_id']}/{e['camera_id']}/{e['event_id']}.jpg"
    client.storage.from_.return_value.remove.assert_called_once_with([expected])
    assert dispatcher.close()


def test_media_access_denies_old_scope_and_forged_prefix():
    db=MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data=[{
      'id':str(SCOPE.camera_id),'user_id':str(SCOPE.owner_id),'organization_id':str(SCOPE.organization_id)}]
    e=event();row={'id':e['event_id'],'camera_id':e['camera_id'],'vision_metadata':e}
    with pytest.raises(HTTPException):verify_vision_media_scope(db,row,'someone/else.jpg','.jpg')
    path=f"{e['owner_id']}/{e['camera_id']}/{e['event_id']}.jpg"
    verify_vision_media_scope(db,row,path,'.jpg')
    row['vision_metadata']={**e,'organization_id':str(uuid4())}
    with pytest.raises(HTTPException):verify_vision_media_scope(db,row,path,'.jpg')


def test_evidence_queue_limit_deadline_session_and_network_failure(monkeypatch):
    # No worker thread: deterministic saturation of the production bounded queue.
    from queue import Queue
    dispatcher=EvidenceDispatcher.__new__(EvidenceDispatcher)
    dispatcher.queue=Queue(maxsize=4);dispatcher.closing=False
    for i in range(4):assert dispatcher.submit({'i':i})
    assert not dispatcher.submit({'i':5})
    sink=MagicMock();sink.submit.return_value=True
    collector=EvidenceCollector(SCOPE,sink)
    collector.offer(event(),1,frame())
    collector.pending['deadline']=0
    collector.tick()
    assert collector.pending is None
    assert sink.submit.call_args.args[0]['frames']==[]
    collector.offer(event(),1,frame())
    collector.append(frame(session=uuid4()))
    assert collector.pending is None and collector.metrics['session_dropped']==1
    client=MagicMock();client.rpc.return_value.execute.side_effect=RuntimeError('hidden token')
    io=EvidenceDispatcher(client)
    io.submit({'event':event(),'revision':1,'snapshot':None,'frames':[]})
    assert io.close() and io.metrics['failed']==1
    client.storage.from_.assert_not_called()


def test_revoked_scope_does_not_upload_or_delete_media():
    client=MagicMock();io=EvidenceDispatcher(client)
    io.store.attach=MagicMock(side_effect=ValueError('scope revoked'))
    with pytest.raises(ValueError):io._upload(event(),'snapshot',b'fixture')
    client.storage.from_.return_value.upload.assert_not_called()
    client.storage.from_.return_value.remove.assert_not_called()
    assert io.close()


def test_rules_api_read_access_and_current_scope(monkeypatch):
    from app import vision_api as api
    db,http=api_setup(monkeypatch,False)
    r=rule().model_dump(mode='json')
    db.table.return_value.select.return_value.eq.return_value.execute.side_effect=[
        SimpleNamespace(data=[{'id':str(SCOPE.camera_id),'user_id':str(SCOPE.owner_id),'organization_id':str(SCOPE.organization_id)}]),
        SimpleNamespace(data=[{'revision':3,'rules':[r],'owner_id':str(SCOPE.owner_id),'organization_id':str(SCOPE.organization_id)}])]
    response=http.get(f'/cameras/{SCOPE.camera_id}/vision-rules')
    assert response.status_code==200 and not response.json()['can_manage']
    monkeypatch.setattr(api,'has_camera_access',lambda *args:False)
    assert http.get(f'/cameras/{SCOPE.camera_id}/vision-rules').status_code==403


def test_pipeline_includes_enabled_rule_classes_without_second_capture():
    from app.vision.config import CameraConfig
    from app.vision.pipeline import ObjectPipeline
    detector=MagicMock();detector.detect.return_value=[]
    r=rule().model_copy(update={'classes':('car',)})
    config=CameraConfig(**SCOPE.model_dump(),vision_enabled=True,object_classes=(0,),rules=(r,))
    pipeline=ObjectPipeline(config,detector)
    pipeline.process(frame())
    assert detector.detect.call_args.kwargs['classes']==(0,2)


def test_schema_compatibility_is_legacy_only():
    from app.events import query_events
    db=MagicMock()
    class MissingColumn(Exception):code='42703'
    db.table.return_value.select.return_value.eq.return_value.execute.side_effect=[MissingColumn('vision_metadata missing'),SimpleNamespace(data=[])]
    assert query_events(db,'id',lambda q:q.eq('id','fixture')).data==[]
    assert db.table.return_value.select.call_count==2
    with pytest.raises(HTTPException):
        verify_vision_media_scope(db,{'event_type':'vision_intrusion'},'fixture.jpg','.jpg')


def test_stale_pre_event_frames_are_not_attached_after_capture_gap():
    sink=MagicMock();sink.submit.return_value=True
    collector=EvidenceCollector(SCOPE,sink)
    collector.append(frame(stamp=1.))
    collector.offer(event(),1,frame(sequence=10,stamp=100.))
    assert collector.pending['frames']==[]
    collector.close()
