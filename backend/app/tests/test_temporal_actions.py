from datetime import timedelta
from uuid import uuid4

import pytest
from app.tests.test_pose_lab import SCOPE,body,packet
from app.vision.actions import TemporalActions,associated_person,hand_shape
from app.vision.contracts import DetectionEvent
from app.vision.landmarks import Landmark,LandmarkSet
from app.vision.config import CameraConfig


def lying():
    b=body()
    xy={11:(.2,.8),12:(.3,.8),23:(.6,.87),24:(.7,.87),27:(.85,.9),28:(.9,.9)}
    return b.model_copy(update={'points':tuple(p.model_copy(update={'x':xy[p.index][0],'y':xy[p.index][1]}) if p.index in xy else p for p in b.points)})


def event(p,*,track=1,scope=SCOPE):
    return DetectionEvent(**scope.model_dump(),event_id=uuid4(),timestamp=p.timestamp,model_version='fixture',**{'class':'person'},confidence=.9,bbox={'x_min':.1,'y_min':.1,'x_max':.99,'y_max':.99},worker_session_id=p.worker_session_id,track_id=track).model_dump(mode='json',by_alias=True)


def test_association_rejects_cross_tenant_frame_and_ambiguous_people():
    p=packet()
    assert associated_person(p,[event(p)])==1
    assert associated_person(p,[event(p),event(p,track=2)]) is None
    assert associated_person(p,[]) is None
    with pytest.raises(ValueError):associated_person(p,[event(p,scope=SCOPE.model_copy(update={'owner_id':uuid4()}))])
    wrong=event(p);wrong['timestamp']=(p.timestamp+timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError):associated_person(p,[wrong])


def fall_sequence(engine,*,association=1):
    signals=[]
    for n,t in enumerate((0,.4,.8,1.2,1.6,2.,2.4),1):
        p=packet(n,t,observations=(body(raised=False),) if n<=3 else (lying(),))
        signals+=engine.process(p,person_track_id=association)
    return signals


def test_possible_fall_requires_transition_and_sustained_low_posture():
    actions=TemporalActions(SCOPE,falls=True)
    signals=fall_sequence(actions)
    assert len(signals)==1 and signals[0].label=='possible_fall' and signals[0].review_status=='pending'
    assert signals[0].basis=='temporal_geometry'
    for n,t in enumerate((2.8,3.2,3.6),8):assert actions.process(packet(n,t,observations=(lying(),)),person_track_id=1)==[]


@pytest.mark.parametrize('kind',['disabled','unassociated','already_lying','walking','occluded','gap','track_switch'])
def test_negative_fall_sequences(kind):
    a=TemporalActions(SCOPE,falls=kind!='disabled')
    if kind in ('disabled','unassociated'):
        assert fall_sequence(a,association=None if kind=='unassociated' else 1)==[]
        return
    signals=[]
    for n,t in enumerate((0,.4,.8,1.2,1.6,2.,2.4),1):
        observation=lying() if kind=='already_lying' or (kind not in ('walking',) and n>3) else body(raised=False)
        if kind=='occluded' and n==4:observation=body(quality=.1)
        if kind=='gap' and n>3:t+=2
        track=2 if kind=='track_switch' and n>3 else 1
        signals+=a.process(packet(n,t,observations=(observation,)),person_track_id=track)
    assert signals==[]


def hand(opened=True):
    xy={0:(.5,.9),1:(.3,.8),2:(.2,.7),3:(.15,.6),4:(.1,.5)}
    for mcp,x in ((5,.3),(9,.45),(13,.6),(17,.75)):
        xy.update({mcp:(x,.65),mcp+1:(x,.5),mcp+2:(x,.35),mcp+3:(x,.2 if opened else .8)})
    return LandmarkSet(kind='hand',landmark_set_id=0,quality_basis='detector_presence_only',points=tuple(Landmark(index=i,x=xy[i][0],y=xy[i][1]) for i in range(21)))


@pytest.mark.parametrize('opened,label',[(True,'possible_open_palm'),(False,'possible_closed_fist')])
def test_temporal_hand_gestures_do_not_invent_confidence(opened,label):
    h=hand(opened)
    assert hand_shape(h,640,480)==label
    a=TemporalActions(SCOPE,gestures=True)
    signals=[]
    for n,t in enumerate((0,.4,.8,1.2),1):signals+=a.process(packet(n,t,observations=(body(raised=False),h)),person_track_id=1)
    assert len(signals)==1 and signals[0].label==label and signals[0].input_quality is None
    assert signals[0].review_status=='pending'


def test_sensitive_configuration_off_and_requires_object_association():
    c=CameraConfig(**SCOPE.model_dump())
    assert not c.pose_enabled and not c.hand_gestures_enabled and not c.fall_candidates_enabled
    with pytest.raises(ValueError):CameraConfig(**SCOPE.model_dump(),pose_enabled=True,fall_candidates_enabled=True)
    with pytest.raises(ValueError):CameraConfig(**SCOPE.model_dump(),vision_enabled=True,pose_enabled=True,fall_candidates_enabled=True,inference_fps=1)
