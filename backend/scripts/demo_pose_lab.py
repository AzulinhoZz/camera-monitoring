"""Offline generated geometry only: no MediaPipe/MMAction inference or camera I/O."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from uuid import UUID

import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.vision.contracts import CameraScope
from app.vision.landmarks import Landmark, LandmarkSet, LandmarkFrame
from app.vision.pose_rendering import draw_skeleton
from app.vision.gestures import HandsRaisedLab


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/tmp/camera-pose-lab')
    args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True,mode=0o700)
    scope=CameraScope(camera_id=UUID(int=1),owner_id=UUID(int=2),organization_id=UUID(int=3))
    coords={11:(.42,.38),12:(.58,.38),13:(.30,.25),14:(.70,.25),15:(.25,.12),16:(.75,.12),
            17:(.23,.10),18:(.77,.10),19:(.24,.08),20:(.76,.08),21:(.27,.10),22:(.73,.10),
            23:(.45,.62),24:(.55,.62),25:(.44,.78),26:(.56,.78),27:(.43,.92),28:(.57,.92),
            29:(.42,.94),30:(.58,.94),31:(.39,.95),32:(.61,.95)}
    body=LandmarkSet(kind='pose_body',landmark_set_id=0,points=tuple(Landmark(index=i,
        x=coords.get(i,(.5,.65))[0],y=coords.get(i,(.5,.65))[1]*.85+.03,visibility=1,presence=1) for i in range(11,33)))
    hand_coords=[(.25,.12),(.23,.10),(.21,.08),(.20,.06),(.19,.04),
        (.24,.08),(.235,.055),(.23,.035),(.225,.015),(.26,.075),(.26,.05),(.26,.025),(.26,.005),
        (.28,.08),(.285,.055),(.29,.035),(.295,.015),(.30,.09),(.31,.07),(.32,.055),(.33,.045)]
    hand=LandmarkSet(kind='hand',landmark_set_id=1,points=tuple(Landmark(index=i,x=x,y=y*.85+.03,visibility=1,presence=1) for i,(x,y) in enumerate(hand_coords)))
    now=datetime.now(timezone.utc)
    def packet(n,seconds):
        return LandmarkFrame(**scope.model_dump(),worker_session_id=UUID(int=4),frame_sequence=n,
            timestamp=now+timedelta(seconds=seconds),model_version='synthetic-landmarks-v1',observations=(body,hand))
    image=np.zeros((360,640,3),np.uint8)
    cv2.putText(image,'SYNTHETIC LANDMARKS - NOT MODEL INFERENCE',(16,340),cv2.FONT_HERSHEY_SIMPLEX,.55,(200,200,200),1)
    p=packet(1,0)
    for name,effect in [('skeleton.png',False),('energy.png',True)]:
        if not cv2.imwrite(str(output/name),draw_skeleton(image,p,scope,energy_effect=effect)):
            raise RuntimeError('could not write lab artifact')
    disabled=HandsRaisedLab(scope);enabled=HandsRaisedLab(scope,enabled=True)
    signals=[]
    for n in range(1,4):
        frame=packet(n,(n-1)*.5)
        assert disabled.process(frame)==[]
        signals.extend(enabled.process(frame))
    assert len(signals)==1
    latencies=[]
    for _ in range(110):
        start=time.perf_counter();draw_skeleton(image,p,scope)
        latencies.append((time.perf_counter()-start)*1000)
    latencies=sorted(latencies[10:])
    (output/'gesture_signal.json').write_text(json.dumps([s.model_dump(mode='json') for s in signals],indent=2)+'\n')
    summary={'fixture':'generated body/hand points; no real model inference or human data',
        'model_integrated':False,'default_disabled':True,'generated_signals':len(signals),
        'signal_type':'possible_hands_raised','review_status':'pending','image_size':[640,360],
        'render_only_latency_ms':{'samples':len(latencies),'p50':latencies[49],'p95':latencies[94]},
        'artifacts':['skeleton.png','energy.png','gesture_signal.json'],'metrics':enabled.metrics()}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':main()
