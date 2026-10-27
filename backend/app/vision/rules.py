"""Opt-in, camera-scoped temporal rules. No persistence, uploads or notifications."""
from datetime import datetime, time, timezone
from math import hypot
from typing import Literal
from uuid import UUID, NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from .contracts import CameraScope, Contract, DetectionEvent


class Point(Contract):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


def side(a, b, p):
    return (b.x-a.x)*(p.y-a.y)-(b.y-a.y)*(p.x-a.x)


def on_segment(a, b, p):
    return abs(side(a,b,p)) < 1e-9 and min(a.x,b.x)-1e-9 <= p.x <= max(a.x,b.x)+1e-9 and min(a.y,b.y)-1e-9 <= p.y <= max(a.y,b.y)+1e-9


def intersects(a,b,c,d):
    return (side(a,b,c)*side(a,b,d)<0 and side(c,d,a)*side(c,d,b)<0) or any((on_segment(a,b,c),on_segment(a,b,d),on_segment(c,d,a),on_segment(c,d,b)))


def inside(p, polygon):
    result = False
    for a,b in zip(polygon, polygon[1:]+polygon[:1]):
        if on_segment(a,b,p):
            return True
        if (a.y>p.y)!=(b.y>p.y) and p.x < (b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x:
            result = not result
    return result


class Rule(CameraScope):
    rule_id: UUID
    kind: Literal['intrusion','dwell','line_crossing','count','probable_abandoned_object']
    enabled: bool = False
    classes: tuple[str, ...] = Field(default=('person',), min_length=1, max_length=80)
    polygon: tuple[Point, ...] = Field(default=(), max_length=32)
    line: tuple[Point, Point] | None = None
    direction: Literal['both','positive','negative'] = 'both'
    threshold: int = Field(default=1, ge=1, le=100)
    duration_seconds: float = Field(default=10, ge=1, le=86400)
    cooldown_seconds: float = Field(default=30, ge=0, le=86400)
    stationary_radius: float = Field(default=.02, gt=0, le=.2)
    timezone_name: str = 'UTC'
    weekdays: tuple[int, ...] = (0,1,2,3,4,5,6)
    start: time = time(0)
    end: time = time(23,59,59,999999)

    @model_validator(mode='after')
    def geometry(self):
        ZoneInfo(self.timezone_name)
        if self.start.tzinfo or self.end.tzinfo or not self.weekdays or any(d not in range(7) for d in self.weekdays):
            raise ValueError('invalid schedule')
        if self.kind == 'line_crossing':
            if not self.line or self.line[0] == self.line[1]:
                raise ValueError('distinct line endpoints required')
        else:
            p = self.polygon
            if len(p)<3 or len(set((v.x,v.y) for v in p))!=len(p):
                raise ValueError('simple polygon required')
            area=sum(a.x*b.y-b.x*a.y for a,b in zip(p,p[1:]+p[:1]))
            if abs(area)<1e-9:
                raise ValueError('zero area polygon')
            edges=list(zip(p,p[1:]+p[:1]))
            for i,(a,b) in enumerate(edges):
                for j,(c,d) in enumerate(edges):
                    if j>i+1 and not (i==0 and j==len(edges)-1) and intersects(a,b,c,d):
                        raise ValueError('self intersecting polygon')
        if self.kind=='probable_abandoned_object' and 'person' in self.classes:
            raise ValueError('abandoned object cannot target people')
        return self

    def active(self, timestamp):
        local=timestamp.astimezone(ZoneInfo(self.timezone_name))
        clock=local.time()
        # Overnight early hours belong to the preceding start day.
        day=local.weekday()
        if self.start>self.end and clock<=self.end:
            day=(day-1)%7
        return self.enabled and day in self.weekdays and (self.start<=clock<=self.end if self.start<=self.end else clock>=self.start or clock<=self.end)


class RuleEngine:
    """One full scope/session; at most 32 rules × 100 visible tracks, no identity."""
    def __init__(self, scope: CameraScope, rules):
        if len(rules)>32 or len({r.rule_id for r in rules})!=len(rules):
            raise ValueError('invalid rule set')
        for r in rules:
            if CameraScope(**{k:getattr(r,k) for k in CameraScope.model_fields})!=scope:
                raise ValueError('rule scope mismatch')
        self.scope=scope
        self.rules=tuple(rules)
        self.session=None
        self.last=None
        self.state={}
        self.cooldowns={}

    def process(self, events, *, timestamp: datetime, session: UUID):
        if timestamp.tzinfo is None or timestamp.utcoffset() is None or len(events)>100:
            raise ValueError('invalid frame')
        timestamp=timestamp.astimezone(timezone.utc)
        parsed=[DetectionEvent.model_validate(e) for e in events]
        seen=set()
        for e in parsed:
            e.require_scope(self.scope)
            if e.timestamp!=timestamp or e.worker_session_id!=session or e.track_id is None or e.track_id in seen:
                raise ValueError('invalid event batch')
            seen.add(e.track_id)
        if self.session==session and self.last is not None and timestamp<=self.last:
            raise ValueError('duplicate/out-of-order rule frame')
        if self.session!=session:
            self.state={}; self.cooldowns={}; self.session=session
        self.last=timestamp
        now=timestamp.timestamp()
        output=[]
        for rule in self.rules:
            previous=self.state.get(rule.rule_id,{})
            current={}
            candidates=[]
            if not rule.active(timestamp):
                self.state.pop(rule.rule_id,None)
                continue
            for event in parsed:
                if event.class_name not in rule.classes:
                    continue
                box=event.bbox
                p=Point(x=(box.x_min+box.x_max)/2,y=(box.y_min+box.y_max)/2)
                old=previous.get(event.track_id)
                if old and now-old['last']>2:
                    old=None
                entered=old['entered'] if old else now
                anchor=old['anchor'] if old else p
                triggered=False
                direction=None
                if rule.kind=='line_crossing':
                    a,b=rule.line
                    value=side(a,b,p)
                    # Keep last nonzero side through points exactly on the line.
                    prior=old['side'] if old else 0
                    prior_point=old['point'] if old else p
                    if value and prior and value*prior<0 and intersects(a,b,prior_point,p):
                        direction='positive' if value>0 else 'negative'
                        triggered=rule.direction in ('both',direction)
                    current[event.track_id]={'side':value or prior,'point':p if value else prior_point,'entered':entered,'anchor':anchor,'last':now,'fired':False}
                elif inside(p,rule.polygon):
                    if rule.kind=='probable_abandoned_object' and hypot(p.x-anchor.x,p.y-anchor.y)>rule.stationary_radius:
                        entered=now; anchor=p; old=None
                    fired=old['fired'] if old else False
                    triggered=(not old if rule.kind=='intrusion' else now-entered>=rule.duration_seconds and not fired)
                    current[event.track_id]={'side':0,'point':p,'entered':entered,'anchor':anchor,'last':now,'fired':fired}
                if triggered and rule.kind!='count':
                    candidates.append((event,direction))
            if rule.kind=='count' and len(current)>=rule.threshold and len(previous)<rule.threshold:
                candidates=[(None,None)]
            for event,direction in candidates:
                if now-self.cooldowns.get(rule.rule_id,float('-inf'))<rule.cooldown_seconds:
                    continue
                track_id=event.track_id if event else None
                output.append({'schema_version':'1.0',**self.scope.model_dump(mode='json'),
                    'event_id':str(uuid5(NAMESPACE_URL,f'{session}/{rule.rule_id}/{timestamp.isoformat()}/{track_id}')),
                    'rule_id':str(rule.rule_id),'worker_session_id':str(session),'track_id':track_id,
                    'timestamp':timestamp.isoformat(),'event_type':rule.kind,'direction':direction,
                    'count':len(current),'review_status':'pending','evidence':None,
                    'description':'Posible objeto abandonado; requiere revisión humana' if rule.kind=='probable_abandoned_object' else 'Regla de visión; requiere revisión humana'})
                self.cooldowns[rule.rule_id]=now
                if track_id in current:
                    current[track_id]['fired']=True
            self.state[rule.rule_id]=current
        return output
