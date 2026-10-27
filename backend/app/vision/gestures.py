"""Laboratory geometric signals across frames, never inferred intent or alerts."""
from datetime import datetime, timezone
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import Field, field_validator
from typing import Literal
from .contracts import CameraScope, Contract, SafeLabel


class GestureSignal(CameraScope):
    schema_version: Literal['experimental-1.0']='experimental-1.0'
    event_id: UUID
    worker_session_id: UUID
    frame_sequence: int = Field(ge=1)
    landmark_set_id: int = Field(ge=0,lt=200)
    timestamp: datetime
    model_version: SafeLabel
    label: Literal['possible_hands_raised']='possible_hands_raised'
    basis: Literal['temporal_geometry']='temporal_geometry'
    review_status: Literal['pending']='pending'
    # Input visibility/presence minimum; NOT probability the gesture is correct.
    input_quality: float = Field(ge=0,le=1)

    @field_validator('timestamp')
    @classmethod
    def utc(cls,value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('timezone-aware timestamp required')
        return value.astimezone(timezone.utc)


class HandsRaisedLab:
    """Explicit opt-in, one camera, <=4 visible bodies, <=200 cooldown entries.

    No claim of robust association: caller must maintain ephemeral landmark-set
    indices across frames. Crossing/occlusion can invalidate that assumption.
    """
    def __init__(self,scope,*,enabled=False):
        self.scope=scope
        self.enabled=enabled
        self.session=None
        self.sequence=0
        self.last_timestamp=None
        self.model_version=None
        self.states={}
        self.cooldowns={}
        self.processed=0
        self.emitted=0

    def process(self,packet):
        packet.require_scope(self.scope)
        if self.session==packet.worker_session_id:
            if packet.frame_sequence<=self.sequence or packet.timestamp<=self.last_timestamp:
                raise ValueError('duplicate/out-of-order landmark frame')
            if packet.model_version!=self.model_version:
                raise ValueError('model change requires a new worker session')
        else:
            self.states={};self.cooldowns={}
        self.session=packet.worker_session_id
        self.sequence=packet.frame_sequence
        self.last_timestamp=packet.timestamp
        self.model_version=packet.model_version
        self.processed+=1
        if not self.enabled:
            self.states={};self.cooldowns={}
            return []
        now=packet.timestamp.timestamp()
        current={}
        signals=[]
        for body in packet.observations:
            if body.kind!='pose_body':continue
            points={p.index:p for p in body.points}
            required=[points[i] for i in (11,12,15,16,23,24)]
            if not all(p.reliable(.6) for p in required):continue
            shoulder_y=(points[11].y+points[12].y)/2
            hip_y=(points[23].y+points[24].y)/2
            if not (hip_y-shoulder_y>.1 and points[15].y<points[11].y-.05 and points[16].y<points[12].y-.05):continue
            key=body.landmark_set_id
            old=self.states.get(key)
            if old and now-old['last']>1.:old=None
            state={'start':old['start'] if old else now,'last':now,
                   'samples':min(60,old['samples']+1) if old else 1,'fired':old['fired'] if old else False}
            current[key]=state
            if state['samples']>=3 and now-state['start']>=1. and not state['fired'] and now-self.cooldowns.get(key,float('-inf'))>=30:
                signal=GestureSignal(**self.scope.model_dump(),event_id=uuid5(NAMESPACE_URL,f'{self.session}/{packet.model_version}/{key}/{self.sequence}/possible_hands_raised'),
                    worker_session_id=self.session,frame_sequence=self.sequence,landmark_set_id=key,timestamp=packet.timestamp,
                    model_version=packet.model_version,input_quality=min(min(p.visibility,p.presence) for p in required))
                signals.append(signal)
                self.cooldowns[key]=now;state['fired']=True;self.emitted+=1
        self.states=current
        return signals

    def metrics(self):
        return {'enabled':self.enabled,'processed_frames':self.processed,'provisional_signals':self.emitted,
                'active_candidates':len(self.states),'cooldown_entries':len(self.cooldowns)}
