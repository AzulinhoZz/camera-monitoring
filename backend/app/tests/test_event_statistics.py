from types import SimpleNamespace
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.main import app
from app import events as api


def test_statistics_counts_are_scoped_bounded_and_do_not_load_media(monkeypatch):
    camera=str(uuid4());calls=[]
    class Query:
        def select(self,*args,**kwargs):
            assert args==('id',) and kwargs=={'count':'exact','head':True};return self
        def in_(self,key,ids):assert key=='camera_id' and ids==[camera];return self
        def gte(self,*args):return self
        def lte(self,*args):return self
        def eq(self,key,value):calls.append((key,value));return self
        def execute(self):return SimpleNamespace(count=5)
    class Client:
        def table(self,name):assert name=='camera_events';return Query()
    monkeypatch.setattr(api,'create_client',lambda *args:Client())
    monkeypatch.setattr(api,'get_authorized_camera_ids',lambda user:[camera])
    monkeypatch.setattr(api,'has_camera_access',lambda user,value:value==camera)
    app.dependency_overrides[get_current_user]=lambda:{'id':str(uuid4())}
    http=TestClient(app)
    response=http.get('/events/statistics',params={'camera_id':camera,'event_type':'vision_intrusion'})
    assert response.status_code==200 and response.json()['total']==5
    assert response.json()['scope']=='authorized_window' and ('review_status','pending') in calls
    assert http.get('/events/statistics',params={'camera_id':str(uuid4())}).status_code==403
    assert http.get('/events/statistics',params={'since':'2020-01-01T00:00:00Z'}).status_code==422
    assert http.get('/events/statistics',params={'since':'2026-10-27T12:00:00'}).status_code==422
