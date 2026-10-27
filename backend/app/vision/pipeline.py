"""Camera-scoped, opt-in detector/tracker adapter producing existing event v1."""
from collections import deque
import time
from uuid import NAMESPACE_URL, UUID, uuid5

from .contracts import CameraScope, DetectionEvent
from .detection import COCO_CLASSES, MODEL_VERSION
from .tracking import IoUTracker
from .rules import RuleEngine


class ObjectPipeline:
    def __init__(self, config, detector):
        self.config = config
        self.scope = CameraScope(camera_id=config.camera_id, owner_id=config.owner_id, organization_id=config.organization_id)
        self.rules = RuleEngine(self.scope, config.rules)
        self.detector = detector
        self.session = None
        self.tracker = IoUTracker()
        self.sequence = 0
        self.latencies = deque(maxlen=256)
        self.processed = 0
        self.last_counts = {}

    def process(self, frame):
        if frame.scope != self.scope:
            raise ValueError("frame tenant mismatch")
        if frame.session_id != self.session:
            self.session = frame.session_id
            self.tracker = IoUTracker()
            self.sequence = 0
        if frame.sequence <= self.sequence:
            raise ValueError("duplicate/out-of-order frame")
        start = time.perf_counter()
        detections = self.detector.detect(frame.pixels, classes=self.config.object_classes, confidence=self.config.detection_confidence)
        tracks = self.tracker.update(detections, frame.captured_monotonic)
        self.sequence = frame.sequence
        self.latencies.append((time.perf_counter()-start)*1000)
        self.processed += 1
        events=[]
        for track in tracks:
            event = DetectionEvent(**self.scope.model_dump(), schema_version="1.0",
                event_id=uuid5(NAMESPACE_URL,f"{self.session}/{self.scope.camera_id}/{frame.sequence}/{track.id}/{MODEL_VERSION}"),
                timestamp=frame.timestamp, model_version=MODEL_VERSION,
                **{"class":COCO_CLASSES[track.detection.class_id]}, confidence=track.detection.confidence,
                bbox=track.detection.bbox, worker_session_id=UUID(frame.session_id), track_id=track.id)
            event.require_scope(self.scope)
            events.append(event.model_dump(mode="json",by_alias=True))
        rule_events = self.rules.process(events, timestamp=frame.timestamp, session=UUID(frame.session_id)) if self.config.rules else []
        self.last_counts=self.tracker.counts(tracks)
        return {"type":"detections","schema_version":"1.0",**self.scope.model_dump(mode="json"),
                "worker_session_id":self.session,"frame_sequence":frame.sequence,"events":events,"rule_events":rule_events,
                "counts":self.last_counts,
                "trajectories":[{"track_id":t.id,"points":list(t.trajectory)} for t in tracks]}

    def metrics(self):
        values=sorted(self.latencies)
        return {"model_version":MODEL_VERSION,"processed_frames":self.processed,
                "latency_ms":{"samples":len(values),"p50":values[(len(values)-1)//2] if values else None,
                              "p95":values[int((len(values)-1)*.95)] if values else None},"counts":self.last_counts}
