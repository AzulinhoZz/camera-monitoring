from datetime import datetime, timedelta, timezone, time
from uuid import uuid4

import pytest

from app.vision.contracts import CameraScope, DetectionEvent
from app.vision.rules import Rule, RuleEngine

SCOPE=CameraScope(camera_id=uuid4(),owner_id=uuid4(),organization_id=uuid4())
SESSION=uuid4()
BASE=datetime(2026,10,26,12,tzinfo=timezone.utc)
POLY=({'x':.1,'y':.1},{'x':.9,'y':.1},{'x':.9,'y':.9},{'x':.1,'y':.9})


def rule(kind='intrusion', **kwargs):
    return Rule(**SCOPE.model_dump(),rule_id=uuid4(),kind=kind,enabled=True,polygon=POLY,**kwargs)


def event(second=0,x=.5,y=.5,track=1,label='person',scope=SCOPE,session=SESSION):
    return DetectionEvent(**scope.model_dump(),event_id=uuid4(),timestamp=BASE+timedelta(seconds=second),
        model_version='fixture',**{'class':label},confidence=.9,
        bbox={'x_min':x-.01,'x_max':x+.01,'y_min':y-.01,'y_max':y+.01},worker_session_id=session,track_id=track)


def step(engine,second=0,events=None,session=SESSION):
    return engine.process([event(second)] if events is None else events,timestamp=BASE+timedelta(seconds=second),session=session)


def test_intrusion_cooldown_reentry_and_duplicate():
    engine=RuleEngine(SCOPE,[rule(cooldown_seconds=5)])
    assert len(step(engine))==1
    assert step(engine,1)==[]
    with pytest.raises(ValueError): step(engine,1)
    step(engine,2,[])
    assert step(engine,3)==[]
    step(engine,4,[])
    assert len(step(engine,5))==1


@pytest.mark.parametrize('kind',['dwell','probable_abandoned_object'])
def test_temporal_rules_and_stationary_reset(kind):
    label='backpack' if kind.startswith('probable') else 'person'
    engine=RuleEngine(SCOPE,[rule(kind,classes=(label,),duration_seconds=2,cooldown_seconds=0)])
    assert step(engine,0,[event(label=label)])==[]
    assert step(engine,1,[event(1,label=label)])==[]
    result=step(engine,2,[event(2,label=label)])
    assert len(result)==1 and result[0]['review_status']=='pending'
    assert step(engine,3,[event(3,label=label)])==[]
    if kind.startswith('probable'):
        assert step(engine,4,[event(4,x=.6,label=label)])==[]
        step(engine,5,[event(5,x=.6,label=label)])
        assert len(step(engine,6,[event(6,x=.6,label=label)]))==1


def test_missing_track_resets_dwell():
    engine=RuleEngine(SCOPE,[rule('dwell',duration_seconds=2)])
    step(engine)
    assert step(engine,4)==[]
    step(engine,5)
    assert len(step(engine,6))==1


@pytest.mark.parametrize('direction,expected',[('both',1),('positive',1),('negative',0)])
def test_directed_finite_line_and_on_line(direction,expected):
    engine=RuleEngine(SCOPE,[rule('line_crossing',line=({'x':.5,'y':.2},{'x':.5,'y':.8}),direction=direction)])
    assert step(engine,0,[event(x=.6)])==[]
    assert step(engine,1,[event(1,x=.5)])==[]
    assert len(step(engine,2,[event(2,x=.4)]))==expected
    other=RuleEngine(SCOPE,engine.rules)
    step(other,0,[event(x=.6,y=.95)])
    assert step(other,1,[event(1,x=.4,y=.95)])==[]


def test_count_threshold_edge_and_reset():
    engine=RuleEngine(SCOPE,[rule('count',threshold=2,cooldown_seconds=0)])
    assert step(engine)==[]
    assert step(engine,1,[event(1),event(1,track=2)])[0]['count']==2
    assert step(engine,2,[event(2),event(2,track=2)])==[]
    step(engine,3,[])
    assert len(step(engine,4,[event(4),event(4,track=2)]))==1


def test_scope_batch_and_session_validation():
    engine=RuleEngine(SCOPE,[rule()])
    wrong=SCOPE.model_copy(update={'owner_id':uuid4()})
    with pytest.raises(ValueError): step(engine,0,[event(scope=wrong)])
    with pytest.raises(ValueError): step(engine,0,[event(),event()])
    with pytest.raises(ValueError): step(engine,1,[event()])
    with pytest.raises(ValueError): RuleEngine(wrong,engine.rules)
    step(engine)
    session=uuid4()
    assert len(step(engine,1,[event(1,session=session)],session=session))==1


def test_geometry_and_disabled_and_overnight_schedule():
    with pytest.raises(ValueError): Rule(**{**rule().model_dump(), 'polygon': ()})
    with pytest.raises(ValueError): rule('probable_abandoned_object')
    overnight=rule(start=time(22),end=time(6),weekdays=(0,))
    assert overnight.active(datetime(2026,10,27,2,tzinfo=timezone.utc))
    assert not overnight.active(datetime(2026,10,26,2,tzinfo=timezone.utc))
    disabled=rule().model_copy(update={'enabled':False})
    assert step(RuleEngine(SCOPE,[disabled]))==[]


def test_pipeline_opt_in_and_rule_event_contract():
    from app.vision.config import CameraConfig
    from app.vision.pipeline import ObjectPipeline
    from app.vision.worker import Frame
    from app.vision.source import synthetic_frame
    from app.vision.detection import ObjectDetection
    r=rule()
    with pytest.raises(ValueError):
        CameraConfig(**SCOPE.model_dump(),rules=(r,))
    config=CameraConfig(**SCOPE.model_dump(),vision_enabled=True,rules=(r,))
    class Detector:
        def detect(self,*args,**kwargs):
            return [ObjectDetection(class_id=0,confidence=.9,bbox=event().bbox)]
    pipeline=ObjectPipeline(config,Detector())
    frame=Frame(SCOPE,str(SESSION),1,BASE,0.,1.,synthetic_frame(0,160,120))
    batch=pipeline.process(frame)
    assert batch['rule_events'][0]['rule_id']==str(r.rule_id)
    assert batch['rule_events'][0]['evidence'] is None
    assert len(batch['events'])==1


def test_polygon_boundary_self_intersection_and_batch_bounds():
    from app.vision.rules import Point, inside
    assert inside(Point(x=.1,y=.5),rule().polygon)
    with pytest.raises(ValueError):
        Rule(**{**rule().model_dump(),'polygon':({'x':.1,'y':.1},{'x':.9,'y':.8},{'x':.1,'y':.9},{'x':.8,'y':.1})})
    with pytest.raises(ValueError):
        RuleEngine(SCOPE,[rule() for _ in range(33)])
    with pytest.raises(ValueError):
        step(RuleEngine(SCOPE,[rule()]),events=[event(track=i) for i in range(101)])


def test_confidence_observation_gate_and_line_hysteresis():
    r=rule(min_confidence=.8,min_observations=2,cooldown_seconds=0)
    engine=RuleEngine(SCOPE,[r])
    assert step(engine,0,[event().model_copy(update={'confidence':.3})])==[]
    assert step(engine,1)==[]
    assert len(step(engine,2))==1
    assert step(engine,3)==[]
    line=RuleEngine(SCOPE,[rule('line_crossing',line=({'x':.5,'y':.2},{'x':.5,'y':.8}),line_margin=.02)])
    step(line,0,[event(x=.6)])
    assert step(line,1,[event(1,x=.499)])==[]
    assert step(line,2,[event(2,x=.501)])==[]
    assert len(step(line,3,[event(3,x=.4)]))==1


def test_class_and_timezone_configuration_validation():
    for fields in ({'classes':['invented']},{'timezone_name':'bad/timezone'},{'classes':['person','person']}):
        with pytest.raises(ValueError):Rule(**{**rule().model_dump(),**fields})
