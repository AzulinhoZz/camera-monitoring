"""Shared fail-closed camera destination policy for API, probes and legacy capture."""
import os

from app.vision.config import CameraConfig, checked_rtsp_url


def policy_rtsp_url(source):
    config = CameraConfig(camera_id="00000000-0000-0000-0000-000000000001",
                          owner_id="00000000-0000-0000-0000-000000000002", source_kind="rtsp", source=source,
                          allowed_cidrs=tuple(x.strip() for x in os.getenv("CAMERA_ALLOWED_CIDRS", "").split(",") if x.strip()),
                          allowed_ports=tuple(int(x) for x in os.getenv("CAMERA_ALLOWED_PORTS", "554,8554").split(",")),
                          allow_loopback=os.getenv("CAMERA_ALLOW_LOOPBACK", "false").lower() == "true")
    return checked_rtsp_url(config)
