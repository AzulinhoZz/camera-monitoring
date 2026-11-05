import os
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import cv2
from supabase import create_client

from app.camera_config import config_store
from app.motion_detector import motion_manager

logger = logging.getLogger("connectivity_checker")


def check_rtsp_connection(rtsp_url: str, timeout_sec: float = 3.0) -> bool:
    """Check an RTSP stream using FFmpeg's bounded open/read timeout options."""
    if not rtsp_url or timeout_sec <= 0:
        return False

    cap = None
    timeout_ms = max(1, int(timeout_sec * 1000))
    params = [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms,
    ]
    try:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG, params)
        if not cap.isOpened():
            return False
        ret, frame = cap.read()
        return bool(ret and frame is not None and frame.size > 0)
    except Exception as e:
        logger.warning("Error checking RTSP stream %s: %s", rtsp_url, e)
        return False
    finally:
        if cap is not None:
            cap.release()


def update_camera_status_db(camera_id: str, status: str, last_seen_at: Optional[str] = None):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        return

    try:
        client = create_client(url, key)
        update_data = {"status": status}
        if last_seen_at:
            update_data["last_seen_at"] = last_seen_at
        client.table("cameras").update(update_data).eq("id", camera_id).execute()
    except Exception as e:
        logger.warning("Failed to update camera status in Supabase for %s: %s", camera_id, e)


def check_and_update_camera(camera_id: str, rtsp_url: str) -> Dict[str, Any]:
    is_online = check_rtsp_connection(rtsp_url)
    now_iso = datetime.now(timezone.utc).isoformat()
    if is_online:
        update_camera_status_db(camera_id, status="online", last_seen_at=now_iso)
        cfg = config_store.get_config(camera_id)
        if cfg.get("motion_enabled", True):
            motion_manager.start_detector(
                camera_id, rtsp_url, cfg.get("min_area", 1500),
                cfg.get("threshold", 25), cfg.get("cooldown_seconds", 5.0)
            )
        return {"camera_id": camera_id, "status": "online", "last_seen_at": now_iso}

    update_camera_status_db(camera_id, status="offline")
    return {"camera_id": camera_id, "status": "offline", "last_seen_at": None}


class CameraHealthChecker(threading.Thread):
    def __init__(self, check_interval_sec: float = 30.0):
        super().__init__(daemon=True)
        self.check_interval_sec = check_interval_sec
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        logger.info("Starting background CameraHealthChecker loop")
        while self.running:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SECRET_KEY")
            if url and key:
                try:
                    client = create_client(url, key)
                    res = client.table("cameras").select("id, rtsp_url").execute()
                    for cam in res.data or []:
                        if not self.running:
                            break
                        rtsp_url = cam.get("rtsp_url")
                        if rtsp_url:
                            check_and_update_camera(cam["id"], rtsp_url)
                except Exception as e:
                    logger.error("Error in CameraHealthChecker loop: %s", e)
            time.sleep(self.check_interval_sec)


health_checker = CameraHealthChecker()
