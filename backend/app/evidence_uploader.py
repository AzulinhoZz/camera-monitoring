import os
import cv2
import logging
import threading
import numpy as np
from supabase import create_client

logger = logging.getLogger("evidence_uploader")

BUCKET_NAME = "motion-evidence"

def upload_frame_to_supabase(
    event_id: str,
    user_id: str,
    camera_id: str,
    frame: np.ndarray
):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key or frame is None or frame.size == 0:
        return

    try:
        # Resize frame if resolution is large (> 1280px max dimension)
        h, w = frame.shape[:2]
        max_dim = max(h, w)
        if max_dim > 1280:
            scale = 1280.0 / max_dim
            new_w, new_h = int(w * scale), int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Compress frame to JPEG buffer
        success, encoded_img = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not success:
            logger.error("Failed to encode frame to JPEG")
            return

        image_bytes = encoded_img.tobytes()
        file_path = f"{user_id}/{camera_id}/{event_id}.jpg"

        client = create_client(url, key)

        # Upload image bytes to private bucket 'motion-evidence'
        try:
            client.storage.from_(BUCKET_NAME).upload(
                file_path,
                image_bytes,
                file_options={"content-type": "image/jpeg", "x-upsert": "true"}
            )
            # Update camera_events record with evidence_path
            client.table("camera_events").update({"evidence_path": file_path}).eq("id", event_id).execute()
            logger.info(f"Successfully uploaded evidence frame to {file_path}")
        except Exception as upload_err:
            logger.warning(f"Failed to upload evidence to Supabase Storage: {upload_err}")

    except Exception as e:
        logger.error(f"Error processing evidence frame: {e}")


def dispatch_evidence_upload(event_id: str, user_id: str, camera_id: str, frame: np.ndarray):
    """Dispatches frame upload in a background daemon thread so OpenCV processing loop is never blocked."""
    if frame is None or frame.size == 0:
        return
    frame_copy = frame.copy()
    threading.Thread(
        target=upload_frame_to_supabase,
        args=(event_id, user_id, camera_id, frame_copy),
        daemon=True
    ).start()
