"""Experimental transient landmarks. No models, identity, persistence or network."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .contracts import CameraScope, Contract, SafeLabel


class Landmark(Contract):
    index: int = Field(ge=0, le=32)
    # MediaPipe can locate points outside the image. Rendering hides them.
    x: float = Field(ge=-2, le=3)
    y: float = Field(ge=-2, le=3)
    z: float = Field(default=0, ge=-10, le=10)
    # Missing quality is unknown, never an invented perfect confidence.
    visibility: float | None = Field(default=None, ge=0, le=1)
    presence: float | None = Field(default=None, ge=0, le=1)

    def reliable(self, minimum=.6):
        return (self.visibility is not None and self.presence is not None
                and min(self.visibility,self.presence)>=minimum
                and 0<=self.x<=1 and 0<=self.y<=1)


class LandmarkSet(Contract):
    kind: Literal['pose_body','hand']
    # Ephemeral index meaningful only for this camera/session, not a person ID.
    landmark_set_id: int = Field(ge=0, lt=200)
    quality_basis: Literal['per_landmark_scores','detector_presence_only'] = 'per_landmark_scores'
    points: tuple[Landmark, ...] = Field(min_length=21, max_length=22)

    @model_validator(mode='after')
    def topology(self):
        indices=[p.index for p in self.points]
        expected=set(range(11,33)) if self.kind=='pose_body' else set(range(21))
        if len(indices)!=len(set(indices)) or set(indices)!=expected:
            raise ValueError('invalid body/hand topology; facial pose indices are excluded')
        return self


class LandmarkFrame(CameraScope):
    schema_version: Literal['experimental-1.1']='experimental-1.1'
    worker_session_id: UUID
    frame_sequence: int = Field(ge=1)
    timestamp: datetime
    model_version: SafeLabel
    image_width: int = Field(default=1, ge=1, le=1280)
    image_height: int = Field(default=1, ge=1, le=720)
    observations: tuple[LandmarkSet, ...] = Field(default=(), max_length=12)

    @field_validator('timestamp')
    @classmethod
    def utc(cls,value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('timezone-aware timestamp required')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def bounded_observations(self):
        keys=[(o.kind,o.landmark_set_id) for o in self.observations]
        if len(keys)!=len(set(keys)):
            raise ValueError('duplicate landmark set')
        if sum(o.kind=='pose_body' for o in self.observations)>4 or sum(o.kind=='hand' for o in self.observations)>8:
            raise ValueError('too many body/hand observations')
        return self

    def require_scope(self,scope):
        if CameraScope(camera_id=self.camera_id,owner_id=self.owner_id,organization_id=self.organization_id)!=scope:
            raise ValueError('landmark tenant mismatch')
        return self
