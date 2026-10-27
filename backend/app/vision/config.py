"""Server-only configuration. RTSP is fail-closed unless explicit CIDRs are supplied."""
import ipaddress
import socket
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator

from .contracts import CameraScope, Contract


class CameraConfig(CameraScope):
    # Never serialize source into metrics/logs/errors shown to clients.
    source_kind: Literal["synthetic", "video", "rtsp"] = "synthetic"
    source: str = Field(default="", repr=False, exclude=True, max_length=2048)
    allowed_cidrs: tuple[str, ...] = ()
    allow_loopback: bool = False
    allowed_ports: tuple[int, ...] = (554, 8554)
    vision_enabled: bool = False
    object_classes: tuple[int, ...] = (0,)
    detection_confidence: float = Field(default=.5, ge=.01, le=1)
    capture_fps: float = Field(default=15, gt=0, le=60)
    recording_fps: float = Field(default=10, gt=0, le=60)
    inference_fps: float = Field(default=3, gt=0, le=60)
    queue_size: int = Field(default=2, ge=1, le=8)
    max_width: int = Field(default=640, ge=32, le=1280)
    max_height: int = Field(default=480, ge=32, le=720)
    open_timeout_seconds: float = Field(default=3, ge=0.1, le=30)
    read_timeout_seconds: float = Field(default=3, ge=0.1, le=30)
    shutdown_timeout_seconds: float = Field(default=1, ge=0.1, le=5)
    reconnect_initial_seconds: float = Field(default=0.25, ge=0.05, le=10)
    reconnect_max_seconds: float = Field(default=5, ge=0.05, le=30)
    stale_after_seconds: float = Field(default=2, ge=0.05, le=30)

    @field_validator("object_classes")
    @classmethod
    def valid_classes(cls, values):
        if len(values)>80 or len(set(values))!=len(values) or any(not 0<=value<80 for value in values):
            raise ValueError("invalid COCO class selection")
        return values

    @field_validator("allowed_cidrs")
    @classmethod
    def valid_networks(cls, values):
        for value in values:
            ipaddress.ip_network(value, strict=True)
        return values

    @field_validator("allowed_ports")
    @classmethod
    def valid_ports(cls, values):
        if not values or any(not 1 <= value <= 65535 for value in values):
            raise ValueError("invalid allowed RTSP ports")
        return values

    @model_validator(mode="after")
    def consistent(self):
        if max(self.recording_fps, self.inference_fps) > self.capture_fps:
            raise ValueError("consumer FPS cannot exceed capture FPS")
        if self.reconnect_max_seconds < self.reconnect_initial_seconds:
            raise ValueError("invalid reconnect bounds")
        if self.source_kind != "synthetic" and not self.source:
            raise ValueError("source required")
        if self.source_kind == "synthetic" and self.source:
            raise ValueError("synthetic source must not have a URL")
        if self.source_kind == "video":
            path = Path(self.source)
            if not path.is_absolute() or path.suffix.lower() not in (".avi", ".mp4") or not path.is_file():
                raise ValueError("video source must be an existing absolute AVI/MP4 path")
        return self


def checked_rtsp_url(config: CameraConfig) -> str:
    """Resolve in the disposable decoder process and pin every attempt to an allowed IP.

    Only unauthenticated RTSP over TCP is supported in phase 1. No TLS verification
    is bypassed: rtsps, userinfo, query strings and fragments are rejected rather
    than giving native decoders secrets they could print. A secure credential
    transport is a separate integration gate.
    """
    try:
        parsed = urlsplit(config.source)
        port = parsed.port or 554
        if (parsed.scheme != "rtsp" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or port not in config.allowed_ports or not config.allowed_cidrs
                or any(ord(c) < 32 for c in config.source)):
            raise ValueError
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(
            parsed.hostname, port, type=socket.SOCK_STREAM
        )})
        if not addresses:
            raise ValueError
        networks = [ipaddress.ip_network(cidr) for cidr in config.allowed_cidrs]
        for raw in addresses:
            address = ipaddress.ip_address(raw)
            # IPv4-mapped IPv6 must pass the same policy as IPv4.
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            if (address.is_link_local or address.is_multicast or address.is_unspecified
                    or (address.is_reserved and not address.is_loopback) or (address.is_loopback and not config.allow_loopback)
                    or not any(address.version == n.version and address in n for n in networks)):
                raise ValueError
        chosen = addresses[0]
        host = f"[{chosen}]" if ":" in chosen else chosen
        return urlunsplit(("rtsp", f"{host}:{port}", parsed.path, "", ""))
    except (ValueError, OSError):
        # Do not chain exceptions containing a raw URL or host.
        raise ValueError("RTSP source denied by server network policy") from None


class WorkerConfig(Contract):
    cameras: tuple[CameraConfig, ...] = Field(min_length=1, max_length=4)
    metrics_interval_seconds: float = Field(default=5, ge=0.1, le=60)

    @model_validator(mode="after")
    def unique_cameras(self):
        if len({c.camera_id for c in self.cameras}) != len(self.cameras):
            raise ValueError("duplicate camera configuration")
        # Budget shared slots, two lanes and two in-flight copies. Decoder/library
        # allocations are additionally bounded by the container memory limit.
        frame_bytes = sum(c.max_width * c.max_height * 3 * (3 + 2 * c.queue_size) for c in self.cameras)
        if frame_bytes > 64 * 1024 * 1024:
            raise ValueError("configured frame buffers exceed the 64 MiB budget")
        return self

    @classmethod
    def load(cls, filename: str):
        # Trusted operator file, never a client API payload. Bound input size.
        path = Path(filename)
        if path.stat().st_size > 64 * 1024:
            raise ValueError("worker config exceeds size limit")
        return cls.model_validate_json(path.read_text())
