"""Generated landmark sequences and explicit ambiguous counterexample, not real falls."""
from datetime import datetime,timedelta,timezone
from uuid import UUID
from app.vision.actions import TemporalActions
from app.vision.landmarks import Landmark,LandmarkSet,LandmarkFrame
from app.vision.contracts import CameraScope


def validate_sequences():
    scope=CameraScope(camera_id=UUID(int=1),owner_id=UUID(int=2))
    base=datetime(2026,10,27,tzinfo=timezone.utc)
    times=(0,.4,.8,1.2,1.6,2.,2.4)
    rows=[]
    cases=('rapid_fall_geometry','already_horizontal','walking','sitting','bend_without_drop','occlusion','gap','track_change','unassociated','fast_intentional_lie_down')
    for case in cases:
        action=TemporalActions(scope,falls=True);signals=[]
        for n,t in enumerate(times,1):
            xy={11:(.4,.4),12:(.6,.4),23:(.45,.65),24:(.55,.65),27:(.45,.95),28:(.55,.95)}
            horizontal=case=='already_horizontal' or (case not in ('walking','sitting') and n>3)
            if horizontal:xy={11:(.2,.8),12:(.3,.8),23:(.6,.87),24:(.7,.87),27:(.85,.9),28:(.9,.9)}
            if case=='bend_without_drop' and n>3:
                xy[11]=(.2,.6);xy[12]=(.3,.6);xy[23]=(.6,.65);xy[24]=(.7,.65)
            if case=='sitting' and n>3:
                xy[11]=(.4,.55);xy[12]=(.6,.55);xy[23]=(.45,.75);xy[24]=(.55,.75)
            quality=.1 if case=='occlusion' and n==4 else 1.
            body=LandmarkSet(kind='pose_body',landmark_set_id=0,points=tuple(Landmark(index=i,x=xy.get(i,(.5,.7))[0],y=xy.get(i,(.5,.7))[1],visibility=quality,presence=quality) for i in range(11,33)))
            if case=='gap' and n>3:t+=2
            packet=LandmarkFrame(**scope.model_dump(),worker_session_id=UUID(int=3),frame_sequence=n,timestamp=base+timedelta(seconds=t),model_version='generated-action-fixture-v1',observations=(body,))
            track=None if case=='unassociated' else 2 if case=='track_change' and n>3 else 1
            signals+=action.process(packet,person_track_id=track)
        candidate=any(s.label=='possible_fall' for s in signals)
        expected=case in ('rapid_fall_geometry','fast_intentional_lie_down')
        assert candidate==expected,(case,candidate)
        rows.append({'name':case,'expected_geometric_candidate':expected,'candidate':candidate,
                     'semantic_fall_label':case=='rapid_fall_geometry','known_ambiguity':case=='fast_intentional_lie_down'})
    return {'dataset':'generated landmark sequences, not real-world fall accuracy','sequences':rows,
            'geometric_checks_passed':len(rows),'semantic_false_positives':1,
            'limitations':'Fast intentional lying down has the same geometric signature and produces a possible event requiring review.'}
