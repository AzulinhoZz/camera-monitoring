"""Provisional temporal geometry, not trained action recognition or inferred intent."""
from collections import Counter
import math
from uuid import NAMESPACE_URL,uuid5

from .gestures import GestureSignal,HandsRaisedLab


def associated_person(packet,events):
    """Require one visible person and overlapping body before temporal analysis."""
    from .contracts import CameraScope,DetectionEvent
    scope=CameraScope(camera_id=packet.camera_id,owner_id=packet.owner_id,organization_id=packet.organization_id)
    if len(events)>100:raise ValueError('too many detections')
    parsed=[DetectionEvent.model_validate(e).require_scope(scope) for e in events]
    if any(e.timestamp!=packet.timestamp or e.worker_session_id!=packet.worker_session_id for e in parsed):raise ValueError('detection/pose frame mismatch')
    people=[e.model_dump(mode='json',by_alias=True) for e in parsed if e.class_name=='person' and e.track_id is not None]
    bodies=[b for b in packet.observations if b.kind=='pose_body']
    if len(people)!=1 or len(bodies)!=1:return None
    points=[p for p in bodies[0].points if p.reliable(.6)]
    if len(points)<6:return None
    a=(min(p.x for p in points),min(p.y for p in points),max(p.x for p in points),max(p.y for p in points))
    b=people[0]['bbox'];b=(b['x_min'],b['y_min'],b['x_max'],b['y_max'])
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return people[0]['track_id'] if area>0 and intersection/area>=.2 else None


def hand_shape(hand,width,height):
    points={p.index:(p.x*width,p.y*height) for p in hand.points}
    if any(not 0<=p.x<=1 or not 0<=p.y<=1 for p in hand.points):return None
    def distance(a,b):return math.hypot(points[a][0]-points[b][0],points[a][1]-points[b][1])
    palm=distance(0,9)
    if palm<.01*max(width,height):return None
    extended=[]
    folded=[]
    for mcp,pip,dip,tip in ((5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)):
        u=(points[mcp][0]-points[pip][0],points[mcp][1]-points[pip][1])
        v=(points[dip][0]-points[pip][0],points[dip][1]-points[pip][1])
        norm=math.hypot(*u)*math.hypot(*v)
        if norm<1e-8:return None
        angle=math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/norm))))
        extended.append(angle>=155 and distance(0,tip)>distance(0,pip)*1.1)
        folded.append(angle<115 or distance(0,tip)<distance(0,pip))
    if all(extended):return 'possible_open_palm'
    if all(folded):return 'possible_closed_fist'
    return None


class TemporalActions:
    def __init__(self,scope,*,gestures=False,falls=False):
        self.scope=scope;self.gestures=gestures;self.falls=falls
        self.session=None;self.sequence=0;self.timestamp=None;self.model=None;self.track=None
        self.raised=HandsRaisedLab(scope,enabled=gestures)
        self.fall_state=None;self.hand_state=None;self.cooldowns={};self.metrics=Counter()

    def reset_candidates(self):
        self.fall_state=None;self.hand_state=None
        self.raised=HandsRaisedLab(self.scope,enabled=self.gestures)

    def process(self,packet,*,person_track_id=None):
        packet.require_scope(self.scope)
        if packet.worker_session_id==self.session:
            if packet.frame_sequence<=self.sequence or packet.timestamp<=self.timestamp:raise ValueError('replayed action frame')
            if packet.model_version!=self.model:raise ValueError('model session changed')
        else:
            self.reset_candidates();self.cooldowns={};self.track=None
        now=packet.timestamp.timestamp()
        gap=self.timestamp is not None and (packet.timestamp-self.timestamp).total_seconds()>.75
        self.session=packet.worker_session_id;self.sequence=packet.frame_sequence;self.timestamp=packet.timestamp;self.model=packet.model_version
        self.metrics['frames']+=1
        if person_track_id is None or person_track_id!=self.track or gap:
            self.reset_candidates()
        self.track=person_track_id
        if person_track_id is None:
            self.metrics['unassociated_frames']+=1
            return []
        if not self.gestures and not self.falls:return []
        signals=[]
        if self.gestures:
            for signal in self.raised.process(packet):
                if self._allow(signal.label,now):signals.append(signal)
            hands=[b for b in packet.observations if b.kind=='hand']
            # Ambiguous/multiple hands do not share a temporal history.
            label=hand_shape(hands[0],packet.image_width,packet.image_height) if len(hands)==1 else None
            if label is None:self.hand_state=None
            else:
                center=(hands[0].points[0].x,hands[0].points[0].y)
                old=self.hand_state
                if old and (old['label']!=label or math.hypot(center[0]-old['center'][0],center[1]-old['center'][1])>.15):old=None
                self.hand_state={'label':label,'start':old['start'] if old else now,'samples':min(60,old['samples']+1) if old else 1,'center':center,'fired':old['fired'] if old else False}
                if not self.hand_state['fired'] and self.hand_state['samples']>=3 and now-self.hand_state['start']>=.6 and self._allow(label,now):
                    signals.append(self._signal(packet,label,None));self.hand_state['fired']=True
        if self.falls:
            bodies=[b for b in packet.observations if b.kind=='pose_body']
            required=(11,12,23,24,27,28)
            points={p.index:p for p in bodies[0].points} if len(bodies)==1 else {}
            if not points or not all(points[i].reliable(.6) for i in required):self.fall_state=None
            else:
                sx=(points[11].x+points[12].x)/2;sy=(points[11].y+points[12].y)/2
                hx=(points[23].x+points[24].x)/2;hy=(points[23].y+points[24].y)/2
                aspect=packet.image_width/packet.image_height
                upright=sy+.12<hy and abs(hx-sx)*aspect<abs(hy-sy)
                horizontal=abs(hx-sx)*aspect>max(.12,abs(hy-sy)*1.5)
                old=self.fall_state
                if upright:
                    if not old or old['phase']!='upright':old={'phase':'upright','start':now,'samples':0}
                    old.update(last=now,hip_y=hy,samples=min(60,old['samples']+1))
                    self.fall_state=old
                elif old and old['phase']=='upright' and horizontal and hy-old['hip_y']>=.18 and now-old['last']<=1.5 and old['samples']>=3 and old['last']-old['start']>=.6:
                    self.fall_state={'phase':'low','start':now,'samples':1}
                elif old and old['phase']=='low' and horizontal:
                    old['samples']=min(60,old['samples']+1)
                    if now-old['start']>=1 and old['samples']>=3 and self._allow('possible_fall',now):
                        quality=min(min(points[i].visibility,points[i].presence) for i in required)
                        signals.append(self._signal(packet,'possible_fall',quality))
                        self.fall_state={'phase':'emitted'}
                else:self.fall_state=None
        self.metrics['signals']+=len(signals)
        return signals

    def _allow(self,label,now):
        if now-self.cooldowns.get(label,float('-inf'))<30:return False
        self.cooldowns[label]=now
        return True

    def _signal(self,packet,label,quality):
        return GestureSignal(**self.scope.model_dump(),event_id=uuid5(NAMESPACE_URL,f'{self.session}/{self.track}/{self.sequence}/{label}'),worker_session_id=self.session,frame_sequence=self.sequence,landmark_set_id=0,timestamp=packet.timestamp,model_version=packet.model_version,label=label,input_quality=quality)
