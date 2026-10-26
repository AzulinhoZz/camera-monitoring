import os
import time
import logging
import threading
import collections
import tempfile
from typing import List, Optional
import cv2
import numpy as np
from supabase import create_client

logger = logging.getLogger("clip_recorder")

BUCKET_NAME = "motion-clips"
MAX_CONCURRENT_RECORDINGS = 3
_active_recordings_semaphore = threading.Semaphore(MAX_CONCURRENT_RECORDINGS)


class FrameRingBuffer:
    """Thread-safe circular frame buffer preserving ~5 seconds of pre-event frames."""
    def __init__(self, maxlen: int = 75):
        self.buffer = collections.deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def append(self, frame: np.ndarray):
        if frame is None or frame.size == 0:
            return
        with self.lock:
            # Store a low-cost copy
            self.buffer.append(frame.copy())

    def get_frames_copy(self) -> List[np.ndarray]:
        with self.lock:
            return list(self.buffer)

    def clear(self):
        with self.lock:
            self.buffer.clear()


def record_and_upload_clip(
    event_id: str,
    user_id: str,
    camera_id: str,
    pre_event_frames: List[np.ndarray],
    post_event_provider,
    post_duration_sec: float = 10.0,
    fps: int = 10
):
    acquired = _active_recordings_semaphore.acquire(blocking=False)
    if not acquired:
        logger.warning(f"Max concurrent clip recordings reached ({MAX_CONCURRENT_RECORDINGS}). Skipping clip for event {event_id}.")
        return

    tmp_mp4_path = os.path.join(tempfile.gettempdir(), f"clip_{event_id}.mp4")
    video_writer = None

    try:
        # Collect post-event frames for ~10 seconds
        post_event_frames = []
        end_time = time.time() + post_duration_sec
        while time.time() < end_time:
            frame = post_event_provider()
            if frame is not None and frame.size > 0:
                post_event_frames.append(frame.copy())
            time.sleep(1.0 / fps)

        all_frames = pre_event_frames + post_event_frames
        if not all_frames:
            logger.warning(f"No frames captured for clip event {event_id}")
            return

        # Determine target resolution (max 1280x720)
        h, w = all_frames[0].shape[:2]
        if w > 1280 or h > 720:
            scale = min(1280.0 / w, 720.0 / h)
            w, h = int(w * scale), int(h * scale)

        # Robust VideoWriter initialization with codec fallbacks
        codecs_to_try = ['mp4v', 'avc1', 'MJPG']
        for codec in codecs_to_try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            video_writer = cv2.VideoWriter(tmp_mp4_path, fourcc, float(fps), (w, h))
            if video_writer.isOpened():
                logger.info(f"VideoWriter initialized using codec '{codec}' for event {event_id}")
                break
            else:
                video_writer.release()
                video_writer = None

        if video_writer is None or not video_writer.isOpened():
            logger.error(f"Failed to initialize VideoWriter for event {event_id} with any codec")
            return

        for f in all_frames:
            if f.shape[1] != w or f.shape[0] != h:
                f = cv2.resize(f, (w, h), interpolation=cv2.INTER_AREA)
            video_writer.write(f)

        video_writer.release()
        video_writer = None

        if not os.path.exists(tmp_mp4_path) or os.path.getsize(tmp_mp4_path) == 0:
            logger.error(f"Failed to create valid MP4 file for event {event_id}")
            return

        # Upload to Supabase Storage private bucket 'motion-clips'
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            logger.error("Supabase credentials not set for clip upload")
            return

        client = create_client(url, key)
        file_path = f"{user_id}/{camera_id}/{event_id}.mp4"

        with open(tmp_mp4_path, "rb") as video_file:
            video_bytes = video_file.read()

        client.storage.from_(BUCKET_NAME).upload(
            file_path,
            video_bytes,
            file_options={"content-type": "video/mp4", "x-upsert": "true"}
        )

        # Update database event with clip_path
        client.table("camera_events").update({"clip_path": file_path}).eq("id", event_id).execute()
        logger.info(f"Successfully recorded and uploaded motion clip to {file_path}")

    except Exception as e:
        logger.error(f"Error during motion clip recording/upload for event {event_id}: {e}")
    finally:
        if video_writer is not None:
            try:
                video_writer.release()
            except Exception:
                pass

        if os.path.exists(tmp_mp4_path):
            try:
                os.remove(tmp_mp4_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {tmp_mp4_path}: {e}")

        _active_recordings_semaphore.release()


def dispatch_clip_recording(
    event_id: str,
    user_id: str,
    camera_id: str,
    pre_event_frames: List[np.ndarray],
    latest_frame_provider
):
    """Dispatches clip recording and upload in a background daemon thread."""
    threading.Thread(
        target=record_and_upload_clip,
        args=(event_id, user_id, camera_id, pre_event_frames, latest_frame_provider),
        daemon=True
    ).start()
