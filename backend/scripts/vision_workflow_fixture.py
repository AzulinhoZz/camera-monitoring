"""Integration fixture ONLY: real disposable PostgreSQL, generated frames and local media.

Called by validate_database_security; no DSN, Supabase network or production keys.
Auth/Storage are explicit in-process substitutes, not managed Supabase certification.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4
import time

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from app.vision.config import CameraConfig
from app.vision.contracts import CameraScope, BoundingBox
from app.vision.detection import ObjectDetection
from app.vision.evidence import EvidenceCollector, EvidenceDispatcher
from app.vision.persistence import load_rules
from app.vision.pipeline import ObjectPipeline
from app.vision.rules import Rule
from app.vision.worker import Frame


def literal(value):
    if value is None:return 'NULL'
    if isinstance(value,bool):return 'true' if value else 'false'
    return "'"+str(value).replace("'","''")+"'"


def identifier(value):
    if not re.fullmatch('[a-z_]+',value):raise ValueError('fixture SQL identifier denied')
    return value


class Query:
    def __init__(self,adapter,table):
        self.adapter=adapter;self.table=identifier(table);self.columns='*';self.filters=[];self.updates=None
    def select(self,columns):
        self.columns=','.join(identifier(v.strip()) for v in columns.split(','));return self
    def eq(self,column,value):
        self.filters.append(f'{identifier(column)}={literal(value)}');return self
    def in_(self,column,values):
        self.filters.append(f"{identifier(column)} IN ({','.join(literal(v) for v in values)})");return self
    def lt(self,column,value):
        self.filters.append(f'{identifier(column)}<{literal(value)}');return self
    def order(self,*args,**kwargs):return self
    def limit(self,*args):return self
    def update(self,payload):self.updates=payload;return self
    def execute(self):
        where=' AND '.join(self.filters) or 'true'
        if self.updates is None:
            sql=f'SELECT {self.columns} FROM public.{self.table} WHERE {where}'
            outer=f"SELECT COALESCE(jsonb_agg(x),'[]'::jsonb) FROM ({sql}) x"
        else:
            assignments=','.join(f'{identifier(k)}={literal(v)}' for k,v in self.updates.items())
            sql=f'UPDATE public.{self.table} SET {assignments} WHERE {where} RETURNING *'
            outer=f"WITH x AS ({sql}) SELECT COALESCE(jsonb_agg(x),'[]'::jsonb) FROM x"
        return SimpleNamespace(data=self.adapter.sql(outer))


class LocalBucket:
    def __init__(self,root):self.root=root
    def target(self,path):
        target=(self.root/path).resolve()
        if not target.is_relative_to(self.root.resolve()):raise ValueError('fixture path denied')
        return target
    def upload(self,path,data,**kwargs):
        target=self.target(path);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with target.open('xb') as f:f.write(data)
    def remove(self,paths):
        for path in paths:self.target(path).unlink(missing_ok=True)
    def create_signed_url(self,path,expiry):
        assert self.target(path).is_file() and expiry>0
        return {'signedURL':'fixture-private://'+path}


class Adapter:
    def __init__(self,psql,root):
        self.psql=psql;self.root=root;self.storage=self
    def sql(self,sql):return json.loads(self.psql('-tAc','SET ROLE service_role; '+sql).strip().removeprefix('SET\n'))
    def table(self,name):return Query(self,name)
    def from_(self,bucket):return LocalBucket(self.root/bucket)
    def rpc(self,name,args):
        signatures={
            'save_vision_config':[('p_actor_id','uuid'),('p_camera_id','uuid'),('p_revision','bigint'),('p_rules','jsonb')],
            'ingest_vision_event':[('p_event','jsonb'),('p_revision','bigint')],
            'attach_vision_media':[('p_event_id','uuid'),('p_owner_id','uuid'),('p_org_id','uuid'),('p_kind','text'),('p_path','text')]}
        values=','.join(literal(json.dumps(args[k]) if kind=='jsonb' else args[k])+'::'+kind for k,kind in signatures[name])
        sql=f'SELECT public.{name}({values})'
        if name=='save_vision_config':sql=f"SELECT jsonb_agg(x) FROM public.{name}({values}) x"
        else:sql=f'SELECT to_jsonb(public.{name}({values}))'
        return SimpleNamespace(execute=lambda:SimpleNamespace(data=self.sql(sql)))


def run(psql,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    adapter=Adapter(psql,directory)
    scope=CameraScope(camera_id=UUID('c1000000-0000-0000-0000-000000000001'),owner_id=UUID('f7210242-a53d-495b-a7d7-26f0e0313ca1'))
    r=Rule(**scope.model_dump(),rule_id=uuid4(),kind='intrusion',enabled=True,
           polygon=({'x':.1,'y':.1},{'x':.9,'y':.1},{'x':.9,'y':.9},{'x':.1,'y':.9}))
    payload={k:v for k,v in r.model_dump(mode='json').items() if k not in CameraScope.model_fields}
    user={'id':str(scope.owner_id),'role':'conductor','organization_id':None}
    app.dependency_overrides[get_current_user]=lambda:user
    try:
        with patch.dict('os.environ',{'SUPABASE_URL':'https://supabase.invalid','SUPABASE_SECRET_KEY':'fixture-not-a-key'}),patch('app.vision_api.get_client',return_value=adapter),patch('app.vision_api.has_camera_access',return_value=True),patch('app.vision_api.can_manage_camera',return_value=True),patch('app.events.create_client',return_value=adapter),patch('app.events.has_camera_access',return_value=True),patch('app.events.get_authorized_camera_ids',return_value=[str(scope.camera_id)]):
            http=TestClient(app)
            response=http.put(f'/cameras/{scope.camera_id}/vision-rules',json={'revision':0,'rules':[payload]})
            assert response.status_code==200,response.text
            revision,rules=load_rules(adapter,scope)
            class Detector:
                def detect(self,*args,**kwargs):
                    return [ObjectDetection(class_id=0,confidence=.9,bbox=BoundingBox(x_min=.3,y_min=.3,x_max=.5,y_max=.6))]
            pipeline=ObjectPipeline(CameraConfig(**scope.model_dump(),vision_enabled=True,rules=rules),Detector())
            session=str(uuid4());stamp=datetime.now(timezone.utc);mono=time.monotonic()
            def frame(n,offset):
                pixels=np.zeros((180,320,3),np.uint8)
                cv2.rectangle(pixels,(96,54),(160,108),(0,180,255),-1)
                return Frame(scope,session,n,stamp,mono+offset,0.,pixels)
            io=EvidenceDispatcher(adapter);collector=EvidenceCollector(scope,io)
            for n in range(10):collector.append(frame(n+1,-2+n*.2))
            captured=frame(11,0)
            batch=pipeline.process(captured)
            assert len(batch['rule_events'])==1
            event=batch['rule_events'][0]
            collector.offer(event,revision,captured)
            for n in range(15):collector.append(frame(n+12,(n+1)*.21))
            collector.close();assert io.close(20)
            assert io.metrics['persisted']==io.metrics['snapshots']==io.metrics['clips']==1,dict(io.metrics)
            # Real DB replay, with no duplicate event, evidence or review mutation.
            assert not io.store.insert(event,revision)
            event_id=event['event_id']
            for kind in ('evidence','clip'):
                media=http.get(f'/events/{event_id}/{kind}')
                assert media.status_code==200 and media.json()['signed_url'].startswith('fixture-private://'),media.text
            reviewed=http.post(f'/events/{event_id}/review',json={'review_status':'reviewed_ok'})
            assert reviewed.status_code==200,reviewed.text
            listing=http.get('/events')
            assert listing.status_code==200,listing.text
            row=next(e for e in listing.json()['events'] if e['id']==event_id)
            assert row['review_status']=='reviewed_ok' and row['has_clip'] and row['has_evidence']
            path=next(directory.rglob('*.mp4'))
            video=cv2.VideoCapture(str(path));readable,_=video.read();frames=int(video.get(cv2.CAP_PROP_FRAME_COUNT));video.release()
            assert readable and frames==25
            # Exercise the existing retention implementation on this vision event.
            from app.retention_manager import RetentionManager
            import shutil
            archive=directory/'demo-artifacts';archive.mkdir()
            shutil.copyfile(path,archive/'clip.mp4')
            shutil.copyfile(next(directory.rglob('*.jpg')),archive/'snapshot.jpg')
            manager=RetentionManager()
            with patch('app.retention_manager.get_supabase_client',return_value=adapter),patch.object(manager,'get_user_config',return_value={'retention_days':30,'auto_cleanup_enabled':True}):
                manager.set_event_protection(str(scope.owner_id),event_id,True)
                psql('-c',f"SET ROLE service_role; UPDATE camera_events SET detected_at=now()-interval '40 days' WHERE id={literal(event_id)}::uuid")
                protected=manager.cleanup_expired_evidence(str(scope.owner_id),dry_run=False)
                assert protected['deleted_photos']==protected['deleted_clips']==0
                manager.set_event_protection(str(scope.owner_id),event_id,False)
                cleaned=manager.cleanup_expired_evidence(str(scope.owner_id),dry_run=False)
                assert cleaned['deleted_photos']==cleaned['deleted_clips']==1
                retained=adapter.table('camera_events').select('id,review_status,evidence_path,clip_path').eq('id',event_id).execute().data[0]
                assert retained['review_status']=='reviewed_ok' and retained['evidence_path'] is None and retained['clip_path'] is None
            (directory/'summary.json').write_text(json.dumps({'fixture':'generated rectangles, injected detector, real isolated PostgreSQL; local Storage/Auth substitutes',
                'api_config':True,'rules':True,'persisted':True,'duplicate_suppressed':True,'reviewed':True,'jpeg':True,'mp4_frames':frames,'protection':True,'retention':True,'metrics':dict(io.metrics)},indent=2))
            psql('-c',f"SET ROLE service_role; DELETE FROM camera_events WHERE id={literal(event_id)}::uuid; DELETE FROM camera_vision_configs WHERE camera_id={literal(str(scope.camera_id))}::uuid;")
            print('PASS: API config → scoped rules → PostgreSQL event → JPEG/MP4 → media lookup → human review/protection/retention; local Auth/Storage substitutes')
    finally:app.dependency_overrides.clear()
