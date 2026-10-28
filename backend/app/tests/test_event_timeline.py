"""HTTP contract and keyset queries against an isolated, filtering memory store."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from app import events as api
from app.auth import get_current_user
from app.main import app
from app.event_timeline import decode_cursor, encode_cursor

STAMP='2026-10-27T12:00:00+00:00'
CAMERA=str(UUID(int=1))
OTHER=str(UUID(int=2))


class Query:
    def __init__(self, rows):
        self.rows=rows.copy(); self.maximum=1000
    def select(self, *args):return self
    def in_(self, key, values):
        self.rows=[r for r in self.rows if r[key] in values];return self
    def eq(self, key, value):
        self.rows=[r for r in self.rows if r.get(key)==value];return self
    def gte(self, key, value):
        self.rows=[r for r in self.rows if r[key]>=value];return self
    def lte(self, key, value):
        self.rows=[r for r in self.rows if r[key]<=value];return self
    def or_(self, expression):
        stamp=expression.split('detected_at.lt.')[1].split(',and(')[0]
        identifier=expression.split('id.lt.')[1][:-1]
        self.rows=[r for r in self.rows if (r['detected_at'],r['id'])<(stamp,identifier)];return self
    def order(self, *args, **kwargs):return self
    def limit(self, maximum):self.maximum=maximum;return self
    def execute(self):
        rows=sorted(self.rows,key=lambda r:(r.get('detected_at',''),r['id']),reverse=True)
        return SimpleNamespace(data=rows[:self.maximum])


@pytest.fixture
def http(monkeypatch):
    rows=[{'id':str(UUID(int=i)), 'camera_id':CAMERA if i<5 else OTHER,
           'event_type':'vision_intrusion' if i%2 else 'motion_detected',
           'detected_at':STAMP, 'review_status':'pending' if i%2 else 'reviewed_ok'} for i in range(1,7)]
    class Client:
        def table(self, name):
            return Query(rows if name=='camera_events' else [{'id':CAMERA,'name':'Fixture'}])
    monkeypatch.setattr(api,'create_client',lambda *args:Client())
    monkeypatch.setattr(api,'get_authorized_camera_ids',lambda user:[CAMERA])
    monkeypatch.setattr(api,'has_camera_access',lambda user,camera:camera==CAMERA)
    app.dependency_overrides[get_current_user]=lambda:{'id':str(UUID(int=10))}
    with TestClient(app) as client:yield client


def test_tied_timestamp_pages_are_disjoint_scoped_and_backwards_compatible(http):
    first=http.get('/events',params={'limit':2}).json()
    assert first['total']==2 and first['has_more']
    assert [e['id'] for e in first['events']]==[str(UUID(int=4)),str(UUID(int=3))]
    second=http.get('/events',params={'limit':2,'cursor':first['next_cursor']}).json()
    assert [e['id'] for e in second['events']]==[str(UUID(int=2)),str(UUID(int=1))]
    assert not second['has_more'] and second['next_cursor'] is None
    all_events=http.get('/events').json()
    assert all_events['total']==4 and all(e['camera_id']==CAMERA for e in all_events['events'])
    assert first['summary']['scope']=='page'
    assert first['summary']['by_review_status']=={'reviewed_ok':1,'pending':1}


def test_filters_apply_before_limit_and_cannot_expand_authorization(http):
    response=http.get('/events',params={'event_type':'vision_intrusion','review_status':'pending','since':STAMP,'until':STAMP,'limit':1})
    assert response.status_code==200 and response.json()['events'][0]['id']==str(UUID(int=3))
    assert response.json()['has_more']
    assert http.get('/events',params={'camera_id':OTHER}).status_code==403
    forged=encode_cursor({'id':str(UUID(int=6)),'detected_at':STAMP})
    assert http.get('/events',params={'cursor':forged}).json()['total']==4
    assert http.get('/events',params={'until':'2026-10-26T12:00:00Z'}).json()['total']==0


@pytest.mark.parametrize('params',[
    {'limit':0},{'limit':101},{'cursor':'invalid!'}, {'cursor':'x'*513},
    {'event_type':'x),camera_id.neq.x'}, {'review_status':'anything'},
    {'since':'2026-10-27T12:00:00'},
    {'since':'2026-10-28T00:00:00Z','until':'2026-10-27T00:00:00Z'},
])
def test_invalid_search_is_rejected_without_query_syntax_leaks(http,params):
    response=http.get('/events',params=params)
    assert response.status_code==422


def test_cursor_normalizes_timezone_and_validates_uuid():
    cursor=encode_cursor({'id':str(UUID(int=8)),'detected_at':'2026-10-27T06:00:00-06:00'})
    assert decode_cursor(cursor)==(STAMP,str(UUID(int=8)))
