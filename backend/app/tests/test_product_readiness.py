from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from app import events as api
from app.auth import get_current_user
from app.main import app
from app.vision.diagnostics import diagnose

CAMERA=str(UUID(int=1));OTHER=str(UUID(int=2));RULE=str(UUID(int=10))


class Query:
    def __init__(self,rows):self.rows=rows.copy();self.cap=10000;self.counting=False
    def select(self,*args,**kwargs):self.counting=kwargs.get('head',False);return self
    def in_(self,key,values):self.rows=[r for r in self.rows if r.get(key) in values];return self
    def eq(self,key,value):
        def get(row):
            if '->>' in key:
                parent,child=key.split('->>');return (row.get(parent) or {}).get(child)
            return row.get(key)
        self.rows=[r for r in self.rows if get(r)==value];return self
    def gte(self,key,value):self.rows=[r for r in self.rows if r.get(key,'')>=value];return self
    def lte(self,key,value):self.rows=[r for r in self.rows if r.get(key,'')<=value];return self
    def order(self,*args,**kwargs):return self
    def limit(self,value):self.cap=value;return self
    def execute(self):return SimpleNamespace(data=self.rows[:self.cap],count=len(self.rows))


@pytest.fixture
def store(monkeypatch):
    now=datetime.now(timezone.utc).isoformat()
    rows=[{'id':str(UUID(int=20+i)),'camera_id':camera,'event_type':'vision_intrusion','detected_at':now,
           'review_status':'pending','vision_metadata':{'rule_id':rule}} for i,(camera,rule) in enumerate([(CAMERA,RULE),(CAMERA,str(UUID(int=11))),(OTHER,RULE)])]
    def table(name):return Query(rows if name=='camera_events' else [{'id':CAMERA,'name':'Permitida'}])
    monkeypatch.setattr(api,'create_client',lambda *args:SimpleNamespace(table=table))
    monkeypatch.setattr(api,'get_authorized_camera_ids',lambda user:[CAMERA])
    monkeypatch.setattr(api,'has_camera_access',lambda user,camera:camera==CAMERA)
    app.dependency_overrides[get_current_user]=lambda:{'id':'fixture'}
    with TestClient(app) as http:yield http,rows


def test_rule_search_and_statistics_share_filter_and_authorization(store):
    http,rows=store
    result=http.get('/events',params={'rule_id':RULE})
    assert result.status_code==200 and len(result.json()['events'])==1
    assert result.json()['applied_filters']['rule_id']==RULE
    assert result.json()['events'][0]['camera_id']==CAMERA
    stats=http.get('/events/statistics',params={'rule_id':RULE}).json()
    assert stats['total']==1 and stats['pending']==1
    assert stats['applied_filters']['rule_id']==RULE
    assert http.get('/events',params={'rule_id':'x),camera_id.eq.other'}).status_code==422
    assert http.get('/events',params={'rule_id':RULE,'camera_id':OTHER}).status_code==403


def test_attention_never_leaks_other_cameras_and_marks_truncation(store):
    http,rows=store
    result=http.get('/events/attention')
    assert result.headers['cache-control']=='no-store, private'
    assert result.json()['pending_by_camera']=={CAMERA:2}
    assert result.json()['complete'] is True
    rows.extend([dict(rows[0],id=str(UUID(int=100+i))) for i in range(1002)])
    result=http.get('/events/attention').json()
    assert result['complete'] is False and result['sampled_events']==1000
    assert OTHER not in result['pending_by_camera']


def test_attention_with_no_access_is_empty_without_query(store,monkeypatch):
    monkeypatch.setattr(api,'get_authorized_camera_ids',lambda user:[])
    def forbidden(*args):raise AssertionError('no access must not query')
    monkeypatch.setattr(api,'create_client',forbidden)
    result=store[0].get('/events/attention').json()
    assert result['complete'] and result['pending_by_camera']=={}


def test_diagnostics_detect_stale_frame_low_capacity_and_never_label_people():
    snapshot=SimpleNamespace(healthy=True,state='streaming',inference_frames=3,inference_fps=.5,inference_dropped=2)
    result=diagnose(snapshot,5)
    assert set(result['codes'])=={'frame_stale','inference_below_target','inference_drops_observed'}
    assert result['scope']=='technical_health_only' and not result['ready']
    snapshot.inference_fps=3
    assert diagnose(snapshot,1)['ready']  # Historical drops are informational, not permanent failure.
    snapshot.inference_dropped=0
    assert diagnose(snapshot,1)['ready']


def test_attention_detects_postgrest_server_row_cap_and_unknown_count(store,monkeypatch):
    http,rows=store;rows.extend([dict(rows[0],id=str(UUID(int=100+i))) for i in range(1200)])
    original=Query.execute
    def capped(self):
        result=original(self);result.data=result.data[:1000];return result
    monkeypatch.setattr(Query,'execute',capped)
    assert http.get('/events/attention').json()['complete'] is False
    def unknown(self):
        result=capped(self);result.count=None;return result
    monkeypatch.setattr(Query,'execute',unknown)
    assert http.get('/events/attention').json()['complete'] is False
