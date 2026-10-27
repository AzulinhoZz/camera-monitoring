"""Original class-aware IoU tracklets: bounded, ephemeral, one camera/session.

This is not ByteTrack or a person reidentification algorithm. Occlusions/crossings
can change IDs; counts describe tracklets, not unique people or line crossings.
"""
from collections import Counter, deque
from dataclasses import dataclass
import math

from .detection import ObjectDetection


def intersection_over_union(a, b):
    intersection = max(0, min(a.x_max,b.x_max)-max(a.x_min,b.x_min)) * max(0,min(a.y_max,b.y_max)-max(a.y_min,b.y_min))
    area_a = (a.x_max-a.x_min)*(a.y_max-a.y_min)
    area_b = (b.x_max-b.x_min)*(b.y_max-b.y_min)
    return intersection / (area_a+area_b-intersection)


@dataclass
class Track:
    id: int
    detection: ObjectDetection
    last_seen: float
    trajectory: deque


class IoUTracker:
    def __init__(self, *, ttl_seconds=2., min_iou=.3, max_tracks=200):
        if not math.isfinite(ttl_seconds) or ttl_seconds<=0 or not 0<=min_iou<=1 or not 1<=max_tracks<=200:
            raise ValueError("invalid tracker limits")
        self.ttl = ttl_seconds
        self.min_iou = min_iou
        self.max_tracks = max_tracks
        self.tracks = {}
        self.created_by_class = Counter()
        self.next_id = 1
        self.last_timestamp = None

    def update(self, detections, timestamp):
        if not math.isfinite(timestamp) or (self.last_timestamp is not None and timestamp < self.last_timestamp):
            raise ValueError("out-of-order tracking timestamp")
        if len(detections)>100:
            raise ValueError("too many detections")
        self.last_timestamp = timestamp
        self.tracks = {key:t for key,t in self.tracks.items() if timestamp-t.last_seen<=self.ttl}
        candidates = []
        for key, track in self.tracks.items():
            for index, detection in enumerate(detections):
                if track.detection.class_id == detection.class_id:
                    overlap = intersection_over_union(track.detection.bbox, detection.bbox)
                    if overlap >= self.min_iou:
                        candidates.append((-overlap, key, index))
        matched_tracks, matched_detections, assignments = set(), set(), {}
        for _, key, index in sorted(candidates):
            if key not in matched_tracks and index not in matched_detections:
                matched_tracks.add(key); matched_detections.add(index); assignments[index]=key
        visible = []
        for index, detection in enumerate(detections):
            key = assignments.get(index)
            if key is None:
                if len(self.tracks)>=self.max_tracks:
                    continue
                key=self.next_id; self.next_id+=1
                self.created_by_class[detection.class_id]+=1
                self.tracks[key]=Track(key,detection,timestamp,deque(maxlen=32))
            track=self.tracks[key]
            track.detection=detection; track.last_seen=timestamp
            box=detection.bbox
            track.trajectory.append(((box.x_min+box.x_max)/2,(box.y_min+box.y_max)/2))
            visible.append(track)
        return visible

    def counts(self, visible):
        return {"visible_by_class":dict(Counter(t.detection.class_id for t in visible)),
                "tracklets_created_by_class":dict(self.created_by_class), "active_tracklets":len(self.tracks)}
