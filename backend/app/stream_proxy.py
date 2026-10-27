"""Authorize every HLS request, including segments not checked by native MediaMTX."""
import os
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import authorize_stream_read
from app.streaming import stream_path

router = APIRouter(prefix="/streams", tags=["Streams"])
bearer = HTTPBearer(auto_error=False)
MAX_MEDIA_BYTES = 16 * 1024 * 1024
MEDIA_TYPES = {"m3u8": "application/vnd.apple.mpegurl", "ts": "video/mp2t", "mp4": "video/mp4", "m4s": "video/mp4", "mp": "video/mp4"}


@router.get("/{camera_id}/{filename}")
def proxy_hls(camera_id: str, filename: str, request: Request,
              credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Stream token required")
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,199}", filename) or ".." in filename:
        raise HTTPException(status_code=404, detail="Unknown stream resource")
    suffix = filename.rsplit(".", 1)[-1]
    if suffix not in MEDIA_TYPES:
        raise HTTPException(status_code=404, detail="Unknown stream resource")
    try:
        path = stream_path(camera_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unknown camera") from None
    authorize_stream_read(credentials.credentials, path)
    params = {}
    for key in ("_HLS_msn", "_HLS_part"):
        value = request.query_params.get(key)
        if value is not None:
            if not value.isdigit() or len(value) > 12:
                raise HTTPException(status_code=422, detail="Invalid HLS parameter")
            params[key] = value
    skip = request.query_params.get("_HLS_skip")
    if skip in ("YES", "v2"):
        params["_HLS_skip"] = skip
    upstream_secret = os.getenv("MEDIAMTX_HLS_SECRET", "")
    if len(upstream_secret) < 32:
        raise HTTPException(status_code=503, detail="HLS proxy is not configured")
    base = os.getenv("MEDIAMTX_HLS_INTERNAL_URL", "http://mediamtx:8888").rstrip("/")
    try:
        # Never follow a native/compromised gateway redirect with credentials.
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", f"{base}/{path}/{filename}", params=params,
                               headers={"Authorization": "Bearer " + upstream_secret}) as response:
                if response.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"Stream upstream unavailable ({response.status_code})")
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_MEDIA_BYTES:
                        raise HTTPException(status_code=502, detail="Stream resource exceeds limit")
                    chunks.append(chunk)
                data = b"".join(chunks)
        if suffix == "m3u8":
            text = data.decode("utf-8")
            if "://" in text or ".." in text or 'URI="/' in text:
                raise HTTPException(status_code=502, detail="Invalid upstream playlist")
        return Response(content=data, media_type=MEDIA_TYPES[suffix], headers={"Cache-Control": "private, no-store"})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Stream upstream unavailable") from None
