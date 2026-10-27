"""Generated anatomical points only; these tests do not validate real perception."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import numpy as np
import pytest

from app.vision.contracts import CameraScope
from app.vision.landmarks import Landmark, LandmarkSet, LandmarkFrame
from app.vision.gestures import HandsRaisedLab
from app.vision.pose_rendering import lm_px, draw_skeleton, BODY_EDGES

SCOPE=CameraScope(camera_id=UUID(int=1),owner_id=UUID(int=2),organization_id=UUID(int=3))
SESSION=UUID(int=4)
BASE=datetime(2026,10,27,12,tzinfo=timezone.utc)


def body(*,raised=True,quality=1.,key=0):
    coordinates={11:(.4,.4),12:(.6,.4),13:(.3,.3 if raised else .55),14:(.7,.3 if raised else .55),
                 15:(.3,.2 if raised else .65),16:(.7,.2 if raised else .65),
                 23:(.45,.65),24:(.55,.65),25:(.45,.8),26:(.55,.8),27:(.45,.95),28:(.55,.95)}
    return LandmarkSet(kind='pose_body',landmark_set_id=key,points=tuple(Landmark(index=i,x=coordinates.get(i,(.5,.7))[0],y=coordinates.get(i,(.5,.7))[1],visibility=quality,presence=quality) for i in range(11,33)))


def packet(n=1,seconds=0,*,observations=None,scope=SCOPE,session=SESSION,model='synthetic-landmarks-v1'):
    return LandmarkFrame(**scope.model_dump(),worker_session_id=session,frame_sequence=n,timestamp=BASE+timedelta(seconds=seconds),model_version=model,observations=(body(),) if observations is None else observations)


def test_body_hand_topology_privacy_duplicates_and_bounds():
    b=body()
    assert len(b.points)==22 and all(p.index>=11 for p in b.points)
    with pytest.raises(ValueError):LandmarkSet(kind='pose_body',landmark_set_id=0,points=tuple(Landmark(index=i,x=.5,y=.5) for i in range(22)))
    with pytest.raises(ValueError):packet(observations=(b,b))
    with pytest.raises(ValueError):packet(observations=tuple(body(key=i) for i in range(5)))
    with pytest.raises(ValueError):Landmark(index=11,x=float('nan'),y=.5)
    hand=LandmarkSet(kind='hand',landmark_set_id=0,points=tuple(Landmark(index=i,x=.1+i*.02,y=.5) for i in range(21)))
    assert packet(observations=(b,hand)).observations[1].kind=='hand'


def test_timestamp_and_pixel_projection_edges():
    with pytest.raises(ValueError):LandmarkFrame(**{**packet().model_dump(),'timestamp':datetime(2026,10,27)})
    assert lm_px(Landmark(index=11,x=1,y=1),320,180)==(319,179)
    assert lm_px(Landmark(index=11,x=-.1,y=.5),320,180) is None
    with pytest.raises(ValueError):lm_px(body().points[0],0,180)
    assert not Landmark(index=11,x=.5,y=.5).reliable()


def test_render_nonmutation_quality_scope_and_effect():
    image=np.zeros((180,320,3),np.uint8)
    result=draw_skeleton(image,packet(),SCOPE)
    assert result.sum()>0 and image.sum()==0
    low=draw_skeleton(image,packet(observations=(body(quality=.2),)),SCOPE)
    assert np.array_equal(image,low)
    glow=draw_skeleton(image,packet(),SCOPE,energy_effect=True)
    assert not np.array_equal(result,glow)
    assert all(a>=11 and b>=11 for a,b in BODY_EDGES)
    with pytest.raises(ValueError):draw_skeleton(image,packet(),SCOPE.model_copy(update={'owner_id':uuid4()}))
    with pytest.raises(ValueError):draw_skeleton(np.zeros((10,10),np.uint8),packet(),SCOPE)


def test_hand_quality_unknown_is_not_fabricated():
    points=tuple(Landmark(index=i,x=.2+i*.02,y=.4) for i in range(21))
    hand=LandmarkSet(kind='hand',landmark_set_id=1,points=points)
    image=np.zeros((180,320,3),np.uint8)
    assert np.array_equal(image,draw_skeleton(image,packet(observations=(hand,)),SCOPE))
    reliable=hand.model_copy(update={'points':tuple(p.model_copy(update={'visibility':.9,'presence':.9}) for p in points)})
    assert draw_skeleton(image,packet(observations=(reliable,)),SCOPE).sum()>0


def test_disabled_by_default_and_single_frame_never_emits():
    disabled=HandsRaisedLab(SCOPE)
    for n in range(1,5):assert disabled.process(packet(n,(n-1)*.5))==[]
    assert disabled.metrics()['active_candidates']==0
    assert HandsRaisedLab(SCOPE,enabled=True).process(packet())==[]


def test_temporal_signal_pending_quality_and_cooldown():
    lab=HandsRaisedLab(SCOPE,enabled=True)
    assert lab.process(packet())==[]
    assert lab.process(packet(2,.5))==[]
    signals=lab.process(packet(3,1))
    assert len(signals)==1 and signals[0].label=='possible_hands_raised'
    assert signals[0].basis=='temporal_geometry' and signals[0].review_status=='pending'
    assert signals[0].input_quality==1 and signals[0].model_version=='synthetic-landmarks-v1'
    from app.vision.gestures import GestureSignal
    with pytest.raises(ValueError):
        GestureSignal(**{**signals[0].model_dump(),'timestamp':datetime(2026,10,27)})
    assert lab.process(packet(4,1.5))==[]
    lab.process(packet(5,2,observations=()))
    for n,seconds in [(6,2.5),(7,3),(8,3.5)]:assert lab.process(packet(n,seconds))==[]
    lab.process(packet(9,31,observations=()))
    lab.process(packet(10,31.5));lab.process(packet(11,32))
    assert len(lab.process(packet(12,32.5)))==1


@pytest.mark.parametrize('observations',[(body(raised=False),),(body(quality=.2),)])
def test_negative_geometry_and_uncertain_observations(observations):
    lab=HandsRaisedLab(SCOPE,enabled=True)
    for n in range(1,5):assert lab.process(packet(n,(n-1)*.5,observations=observations))==[]


def test_gap_replay_model_change_scope_and_session_reset():
    lab=HandsRaisedLab(SCOPE,enabled=True)
    lab.process(packet());lab.process(packet(2,.5))
    assert lab.process(packet(3,3))==[]
    with pytest.raises(ValueError):lab.process(packet(3,3))
    with pytest.raises(ValueError):lab.process(packet(4,3.5,model='other'))
    with pytest.raises(ValueError):lab.process(packet(4,3.5,scope=SCOPE.model_copy(update={'organization_id':uuid4()})))
    assert lab.process(packet(1,0,session=uuid4()))==[]
    assert lab.metrics()['cooldown_entries']<=200
