"""Short-lived camera-scoped playback credentials, never embedded in URLs/logs."""
import os
import re
from datetime import datetime, timedelta, timezone

import jwt

STREAM_TTL_SECONDS = 60


def stream_path(camera_id):
    value = str(camera_id)
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", value):
        raise ValueError("invalid camera identifier")
    return f"cam_{value}"


def signing_key():
    key = os.getenv("STREAM_TOKEN_SECRET", "")
    if len(key) < 32:
        raise RuntimeError("Streaming signing key is not configured")
    return key


def issue_stream(user_id, camera):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=STREAM_TTL_SECONDS)
    token = jwt.encode({"sub": str(user_id), "camera_id": camera["id"],
                        "owner_id": camera.get("user_id"), "organization_id": camera.get("organization_id"),
                        "path": stream_path(camera["id"]), "aud": "camera-stream", "iss": "camera-monitoring",
                        "iat": now, "exp": expires}, signing_key(), algorithm="HS256")
    return {"stream_token": token, "stream_expires_at": expires.isoformat(),
            "hls_url": f"{os.getenv('HLS_PUBLIC_BASE_URL', 'http://10.0.2.2:8000/streams').rstrip('/')}/{camera['id']}/index.m3u8"}


def verify_stream(token, path):
    claims = jwt.decode(token, signing_key(), algorithms=["HS256"], audience="camera-stream",
                        issuer="camera-monitoring", options={"require": ["exp", "iat", "sub", "camera_id", "path", "owner_id"]})
    if "organization_id" not in claims:
        raise ValueError("missing stream organization scope")
    if claims["path"] != path or stream_path(claims["camera_id"]) != path:
        raise ValueError("stream path mismatch")
    return claims
