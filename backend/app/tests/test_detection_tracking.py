import math
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

import numpy as np
import pytest
from pydantic import ValidationError

from app.vision.config import CameraConfig
from app.vision.contracts import BoundingBox, CameraScope
from app.vision.detection import ObjectDetection, YOLOXDetector, verify_model
from app.vision.pipeline import ObjectPipeline
from app.vision.source import synthetic_frame
from app.vision.tracking import IoUTracker
from app.vision.worker import Frame


def detection(class_id=0, x=.1):
    return ObjectDetection(class_id=class_id,confidence=.9,bbox=BoundingBox(x_min=x,y_min=.1,x_max=x+.2,y_max=.4))


def postprocessor():
    # Deliberately synthetic output adapter: does NOT validate ONNX inference.
    detector=YOLOXDetector.__new__(YOLOXDetector)
    detector.grids=np.zeros((8400,2),np.float32)
    detector.strides=np.full((8400,1),8.,np.float32)
    return detector


def test_yolox_confidence_class_filter_nms_and_normalized_boxes():
    detector=postprocessor()
    output=np.zeros((1,8400,85),np.float32)
    for index in (0,1,2):
        output[0,index,:4]=[40,32,math.log(16),math.log(16)]
        output[0,index,4]=.9
    output[0,0,7]=.8;output[0,1,7]=.8  # duplicate car
    output[0,2,5]=.8  # overlapping person must not be suppressed with car
    cars=detector.postprocess(output,640,480,1.,(2,),.7)
    assert len(cars)==1 and cars[0].class_id==2
    assert cars[0].confidence==pytest.approx(.72)
    assert cars[0].bbox.x_min==pytest.approx(.4)
    assert cars[0].bbox.x_max==pytest.approx(.6)
    assert len(detector.postprocess(output,640,480,1.,(0,2),.7))==2
    assert detector.postprocess(output,640,480,1.,(2,),.75)==[]
    output[0,0,0]=np.nan
    with pytest.raises(ValueError,match="output contract"):detector.postprocess(output,640,480,1.,(2,),.7)


def test_unverified_model_and_bad_class_config_fail_before_native_load(tmp_path):
    model=tmp_path/'untrusted.onnx';model.write_bytes(b'not an ONNX')
    with pytest.raises(ValueError,match="size mismatch"):verify_model(model)
    with pytest.raises(ValidationError):
        CameraConfig(camera_id=UUID(int=1),owner_id=UUID(int=2),object_classes=(80,))


def test_tracker_persists_ids_expires_and_counts_tracklets_not_people():
    tracker=IoUTracker(ttl_seconds=1)
    first=tracker.update([detection()],0)[0].id
    second=tracker.update([detection(x=.12)],.2)[0].id
    assert first==second
    assert tracker.counts(tracker.update([detection(x=.13)],.3))["tracklets_created_by_class"]=={0:1}
    after_gap=tracker.update([detection(x=.13)],2)[0].id
    assert after_gap!=first
    assert tracker.created_by_class[0]==2
    with pytest.raises(ValueError,match="out-of-order"):tracker.update([],1)


def test_tracker_class_separation_capacity_and_trajectory_bound():
    tracker=IoUTracker(max_tracks=2)
    visible=tracker.update([detection(0),detection(2)],0)
    assert len({track.id for track in visible})==2
    assert tracker.counts(visible)["visible_by_class"]=={0:1,2:1}
    assert tracker.update([detection(5,x=.7)],.1)==[]
    for index in range(40):visible=tracker.update([detection(0),detection(2)],.2+index*.01)
    assert len(visible[0].trajectory)==32
    assert len(tracker.tracks)<=2


def test_pipeline_tenant_scope_session_reset_events_and_replay_rejection():
    config=CameraConfig(camera_id=UUID(int=1),owner_id=UUID(int=2),vision_enabled=True,object_classes=(0,))
    class Detector:
        def detect(self,pixels,**kwargs):
            assert kwargs=={'classes':(0,),'confidence':.5}
            return [detection()]
    pipeline=ObjectPipeline(config,Detector())
    scope=CameraScope(camera_id=config.camera_id,owner_id=config.owner_id)
    frame=Frame(scope,str(UUID(int=3)),1,datetime.now(timezone.utc),0.,1.,synthetic_frame(0,160,120))
    result=pipeline.process(frame)
    assert result['events'][0]['class']=='person'
    assert result['events'][0]['track_id']==1
    assert result['events'][0]['organization_id'] is None
    assert result['counts']['visible_by_class']=={0:1}
    with pytest.raises(ValueError,match='duplicate'):pipeline.process(frame)
    with pytest.raises(ValueError,match='tenant mismatch'):
        pipeline.process(replace(frame,scope=CameraScope(camera_id=UUID(int=4),owner_id=UUID(int=2)),sequence=2))
    next_result=pipeline.process(replace(frame,sequence=2,captured_monotonic=.1))
    assert next_result['events'][0]['track_id']==1
    assert next_result['events'][0]['event_id']!=result['events'][0]['event_id']
    reset=pipeline.process(replace(frame,session_id=str(UUID(int=5)),sequence=1,captured_monotonic=.2))
    assert reset['events'][0]['worker_session_id']!=result['events'][0]['worker_session_id']
    assert reset['counts']['tracklets_created_by_class']=={0:1}
