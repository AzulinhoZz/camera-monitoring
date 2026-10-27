"""Trusted worker adapter: current scoped config and atomic idempotent event writes."""
from uuid import UUID
from .contracts import CameraScope, Contract
from .rules import Rule, RuleEngine
from pydantic import Field, field_validator
from datetime import datetime, timezone
from typing import Literal


class RuleEvent(CameraScope):
    schema_version: Literal['1.0']='1.0'
    event_id: UUID
    rule_id: UUID
    worker_session_id: UUID
    track_id: int | None = Field(default=None,ge=0)
    timestamp: datetime
    event_type: Literal['intrusion','dwell','line_crossing','count','probable_abandoned_object']
    direction: Literal['positive','negative'] | None = None
    count: int = Field(ge=0,le=100)
    review_status: Literal['pending']='pending'
    evidence: None = None
    description: str = Field(max_length=160)

    @field_validator('timestamp')
    @classmethod
    def utc(cls,value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('UTC timestamp required')
        return value.astimezone(timezone.utc)


def load_rules(client, scope):
    # Always check camera too: an old config must not authorize a moved camera.
    rows=client.table('cameras').select('id,user_id,organization_id').eq('id',str(scope.camera_id)).execute().data or []
    if len(rows)!=1 or CameraScope(camera_id=rows[0]['id'],owner_id=rows[0]['user_id'],organization_id=rows[0].get('organization_id'))!=scope:
        raise ValueError('camera scope changed')
    rows=client.table('camera_vision_configs').select('revision,rules,owner_id,organization_id').eq('camera_id',str(scope.camera_id)).execute().data or []
    if not rows:
        return 0, ()
    row=rows[0]
    if UUID(row['owner_id'])!=scope.owner_id or (UUID(row['organization_id']) if row.get('organization_id') else None)!=scope.organization_id:
        raise ValueError('configuration scope changed')
    rules=tuple(Rule.model_validate(r) for r in row['rules'])
    RuleEngine(scope,rules)
    return row['revision'],rules


class EventStore:
    def __init__(self,client):
        self.client=client

    def insert(self,event,revision):
        parsed=RuleEvent.model_validate(event)
        return self.client.rpc('ingest_vision_event',{'p_event':parsed.model_dump(mode='json'),'p_revision':revision}).execute().data is True

    def attach(self,event,kind,path):
        parsed=RuleEvent.model_validate(event)
        result=self.client.rpc('attach_vision_media',{'p_event_id':str(parsed.event_id),'p_owner_id':str(parsed.owner_id),
             'p_org_id':str(parsed.organization_id) if parsed.organization_id else None,'p_kind':kind,'p_path':path}).execute()
        if result.data is not True:
            raise ValueError('media attachment denied')
