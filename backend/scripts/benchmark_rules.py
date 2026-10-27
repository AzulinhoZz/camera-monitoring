"""Synthetic maximum rule/track load; excludes capture and neural inference."""
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median
from uuid import UUID

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.vision.contracts import CameraScope
from app.vision.rules import Rule, RuleEngine
from app.vision.worker import process_resources


def main():
    output=[]
    for cameras in (1,2,4):
        scope=CameraScope(camera_id=UUID(int=1),owner_id=UUID(int=2))
        rules=[Rule(**scope.model_dump(),rule_id=UUID(int=10+i),kind='dwell',enabled=True,
                    polygon=({'x':0,'y':0},{'x':1,'y':0},{'x':1,'y':1},{'x':0,'y':1})) for i in range(32)]
        engines=[RuleEngine(scope,rules) for _ in range(cameras)]
        base=datetime.now(timezone.utc)
        samples=[]
        for n in range(110):
            stamp=base+timedelta(seconds=n*.1)
            events=[{**scope.model_dump(mode='json'),'event_id':str(UUID(int=1000+i)),
                'timestamp':stamp,'model_version':'fixture','class':'person','confidence':.9,
                'bbox':{'x_min':.1,'y_min':.1,'x_max':.2,'y_max':.2},
                'worker_session_id':UUID(int=3),'track_id':i} for i in range(100)]
            start=time.perf_counter()
            for engine in engines:engine.process(events,timestamp=stamp,session=UUID(int=3))
            elapsed=(time.perf_counter()-start)*1000
            if n>=10:samples.append(elapsed)
        samples.sort()
        output.append({'cameras':cameras,'rules_per_camera':32,'tracks_per_camera':100,'samples':len(samples),
                       'sequential_batch_p50_ms':round(median(samples),3),'sequential_batch_p95_ms':round(samples[94],3),
                       'resources':process_resources()})
    print(json.dumps({'scope':'synthetic rules only; no decoder/model/storage/network','measurements':output},indent=2))

if __name__=='__main__':main()
