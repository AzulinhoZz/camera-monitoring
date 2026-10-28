"""Real isolated model execution + scoped IPC/recovery + generated temporal corpus.

Inputs are an explicitly supplied permitted image and self-generated frames. No
Supabase, camera URL, FCM, database, live user data or automatic model download.
"""
import argparse
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import statistics
import sys
import time
from uuid import UUID,uuid4

import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.vision.contracts import CameraScope
from app.vision.pose_process import PoseProcess
from app.vision.pose_rendering import draw_skeleton
from app.vision.worker import Frame,process_resources
from action_sequences import validate_sequences


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hand-fixture',required=True);p.add_argument('--python',required=True);p.add_argument('--fixture',required=True);p.add_argument('--output',required=True)
    args=p.parse_args()
    fixture=Path(args.fixture)
    if not fixture.is_file() or fixture.stat().st_size>16*1024*1024:raise ValueError('invalid permitted fixture')
    image=cv2.imread(str(fixture))
    if image is None or image.shape[0]>720 or image.shape[1]>1280:raise ValueError('fixture dimensions exceed budget')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True,mode=0o700)
    origin=datetime.now(timezone.utc);measurements=[];positive_bodies=0;positive_hands=0
    for count in (1,2,4):
        clients=[]
        try:
            for i in range(count):
                scope=CameraScope(camera_id=UUID(int=10+i),owner_id=UUID(int=2),organization_id=UUID(int=3))
                clients.append(PoseProcess(scope,args.python))
            sessions=[str(uuid4()) for _ in clients]
            def frame(i,n,pixels=image):
                return Frame(clients[i].scope,sessions[i],n,origin+timedelta(seconds=n*.1),time.monotonic(),0.,pixels)
            for i,client in enumerate(clients):
                result=client.infer(frame(i,1));assert result is not None,dict(client.metrics)
                positive_bodies+=sum(o.kind=='pose_body' for o in result.observations)
                positive_hands+=sum(o.kind=='hand' for o in result.observations)
                assert any(o.kind=='pose_body' for o in result.observations),'expected permitted-image body positive'
                assert all(p.index>=11 for o in result.observations if o.kind=='pose_body' for p in o.points)
                if count==1:
                    cv2.imwrite(str(output/'body-overlay.png'),draw_skeleton(image,result,client.scope,show_unscored_hands=True))
            samples=[];started=time.perf_counter()
            for n in range(2,8):
                begin=time.perf_counter()
                for i,client in enumerate(clients):assert client.infer(frame(i,n)) is not None
                samples.append((time.perf_counter()-begin)*1000)
            elapsed=time.perf_counter()-started
            snapshots=[client.snapshot() for client in clients]
            measurements.append({'cameras':count,'warm_sequential_batches':len(samples),'inferences':6*count,
              'elapsed_seconds':elapsed,'batch_latency_ms':{'p50':statistics.median(samples),'max':max(samples)},
              'per_camera_fps':6/elapsed,'summed_child_rss_bytes':sum(s['resources']['rss_bytes'] for s in snapshots),'parent_resources':process_resources(),
              'scope':'Pose+hands only; excludes YOLOX/capture/evidence/DB, shared host CPU; RSS is sum, not PSS'})
            if count==1:
                blank=np.zeros_like(image)
                result=clients[0].infer(frame(0,8,blank));assert result is not None and not result.observations
                # Deliberate native death: fail closed, backoff, then recreate a new child.
                old_pid=clients[0].process.pid
                clients[0].process.kill();clients[0].process.wait(timeout=2)
                assert clients[0].infer(frame(0,9)) is None
                time.sleep(1.05)
                assert clients[0].infer(frame(0,10)) is not None and clients[0].process.pid!=old_pid
                # Deliberately bound a live native call more tightly than inference.
                clients[0].sock.settimeout(.000001)
                begin=time.monotonic();assert clients[0].infer(frame(0,11)) is None
                assert time.monotonic()-begin<3 and clients[0].process is None
                time.sleep(1.05)
                assert clients[0].infer(frame(0,12)) is not None
                hand_image=cv2.imread(args.hand_fixture)
                assert hand_image is not None and hand_image.shape[0]<=720 and hand_image.shape[1]<=1280
                hand_packet=clients[0].infer(frame(0,13,hand_image));assert hand_packet is not None
                hands=[o for o in hand_packet.observations if o.kind=='hand']
                assert len(hands)==2 and all(len(h.points)==21 for h in hands)
                positive_hands+=len(hands)
                cv2.imwrite(str(output/'hand-overlay.png'),draw_skeleton(hand_image,hand_packet,clients[0].scope,show_unscored_hands=True))
                from app.vision.actions import hand_shape,TemporalActions
                assert all(hand_shape(h,hand_packet.image_width,hand_packet.image_height)=='possible_open_palm' for h in hands)
                # Explicit annotated static-hand sequence, not person tracking accuracy.
                from dataclasses import replace
                signal_model=TemporalActions(clients[0].scope,gestures=True)
                real_hand_signals=[]
                for sequence,seconds in ((14,1.4),(15,1.8),(16,2.2)):
                    packet=clients[0].infer(replace(frame(0,sequence,hand_image[:,:hand_image.shape[1]//2]),timestamp=origin+timedelta(seconds=seconds)));assert packet is not None
                    assert sum(o.kind=='hand' for o in packet.observations)==1
                    selected_packet=packet
                    real_hand_signals+=signal_model.process(selected_packet,person_track_id=1)
                assert len(real_hand_signals)==1 and real_hand_signals[0].label=='possible_open_palm'
                (output/'hand-review-candidate.json').write_text(json.dumps(real_hand_signals[0].model_dump(mode='json'),indent=2)+'\n')
                wrong=frame(0,17)
                from dataclasses import replace
                try:clients[0].infer(replace(wrong,scope=wrong.scope.model_copy(update={'owner_id':uuid4()})))
                except ValueError:pass
                else:raise AssertionError('cross-tenant inference accepted')
        finally:
            for client in clients:client.close()
    corpus=validate_sequences()
    result={'real_model_runtime':True,'fixture':'explicit permitted image, positive body extraction; derived frames, not real fall sequences',
       'positive_body_warmups':positive_bodies,'positive_hand_warmups':positive_hands,'blank_negative':True,
       'kill_recovery':True,'timeout_recovery':True,'cross_tenant_rejected':True,'default_sensitive_alerts':False,
       'measurements':measurements,'action_corpus':corpus,'real_hand_sequence':'static published hand fixture repeated; single-hand association supplied explicitly, not a tracking accuracy test',
       'remaining_validation':'annotated real-world gesture/fall videos, target hardware and operational acceptance'}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'result':'PASS','body_positives':positive_bodies,'hand_positives':positive_hands,'synthetic_sequences':corpus['geometric_checks_passed'],'artifact_directory':str(output)}))

if __name__=='__main__':main()
