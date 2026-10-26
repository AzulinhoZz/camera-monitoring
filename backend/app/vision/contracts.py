"""Versioned internal contracts. Tenant scope comes from trusted server configuration."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CameraScope(Contract):
    camera_id: UUID
    owner_id: UUID
    # Personal cameras have no organization; owner_id is still mandatory.
    organization_id: UUID | None = None


class BoundingBox(Contract):
    x_min: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def positive_area(self):
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("bounding box must have positive area")
        return self


SafeLabel = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")]


class EvidenceReference(Contract):
    bucket: Literal["motion-evidence", "motion-clips"]
    # Relative object path, never a signed URL, token or RTSP credential.
    path: str = Field(min_length=1, max_length=240)

    @field_validator("path")
    @classmethod
    def relative_object(cls, value):
        if any(part in ("", ".", "..") for part in value.split("/")):
            raise ValueError("invalid object path")
        if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/._-" for c in value):
            raise ValueError("invalid object path")
        return value


class DetectionEvent(CameraScope):
    schema_version: Literal["1.0"] = "1.0"
    event_id: UUID
    timestamp: datetime
    model_version: SafeLabel
    class_name: SafeLabel = Field(alias="class")
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox
    # Scoped to camera + worker_session_id; never a persistent identity.
    worker_session_id: UUID
    track_id: int | None = Field(default=None, ge=0)
    rule_id: UUID | None = None
    evidence: EvidenceReference | None = None
    review_status: Literal["pending"] = "pending"

    @field_validator("timestamp")
    @classmethod
    def utc_timestamp(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def evidence_matches_scope(self):
        if self.evidence:
            prefix = f"{self.owner_id}/{self.camera_id}/"
            if not self.evidence.path.startswith(prefix):
                raise ValueError("evidence does not belong to the camera owner")
        return self

    def require_scope(self, scope: CameraScope):
        """Consumers must compare the full scope, not trust an incoming org ID."""
        if (self.camera_id, self.owner_id, self.organization_id) != (
            scope.camera_id, scope.owner_id, scope.organization_id
        ):
            raise ValueError("event scope mismatch")
        return self
